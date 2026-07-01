# embeddings.py
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import time
from sentence_transformers import SentenceTransformer
import faiss
from logger import logger
from config import (
    EMBEDDING_MODEL_NAME,
    FAISS_INDEX_PATH,
    FAISS_METADATA_PATH,
    CHUNK_SIZE
)


class EmbeddingEngine:
    """
    Embedding modelini yönetir, metinleri vektöre çevirir,
    FAISS indeksi oluşturur/kaydeder/yükler.

    Attributes:
        model: SentenceTransformer modeli
        index: FAISS indeksi (IndexFlatL2)
        metadata: Her vektör için chunk bilgileri
        dimension: Embedding boyutu
        is_initialized: Model yüklü mü?
    """

    def __init__(self):
        """EmbeddingEngine'i başlatır, modeli yükler."""
        self.model: Optional[SentenceTransformer] = None
        self.index: Optional[faiss.Index] = None
        self.metadata: List[Dict[str, Any]] = []
        self.dimension: int = 0
        self.is_initialized: bool = False
        self._load_model()

    def _load_model(self) -> bool:
        """
        SentenceTransformer modelini yükler.

        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info(f"Embedding modeli yükleniyor: {EMBEDDING_MODEL_NAME}")
            start_time = time.time()

            self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)

            # Test embedding ile boyut öğren
            test_embedding = self.model.encode(["test"], convert_to_numpy=True)
            self.dimension = test_embedding.shape[1]

            self.is_initialized = True
            elapsed = time.time() - start_time
            logger.info(
                f"Embedding modeli yüklendi: {EMBEDDING_MODEL_NAME} (Boyut: {self.dimension}, Süre: {elapsed:.2f}s)")
            return True

        except Exception as e:
            logger.error(f"Model yüklenemedi: {e}")
            self.is_initialized = False
            raise RuntimeError(f"Embedding modeli yüklenirken hata oluştu: {e}") from e

    def embed_texts(self, texts: List[str], show_progress: bool = False) -> np.ndarray:
        """
        Metin listesini embedding vektörlerine dönüştürür.

        Args:
            texts: Metin listesi
            show_progress: İlerleme gösterilsin mi?

        Returns:
            np.ndarray: Embedding vektörleri (float32)
        """
        if not self.is_initialized:
            raise RuntimeError("Model yüklenmemiş. Önce _load_model() çağırın.")

        if not texts:
            logger.warning("Boş metin listesi gönderildi.")
            return np.array([], dtype=np.float32)

        try:
            start_time = time.time()
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=show_progress,
                normalize_embeddings=True  # Cosine similarity için normalize
            )
            elapsed = time.time() - start_time

            logger.info(f"{len(texts)} metin embedding oluşturuldu. (Süre: {elapsed:.2f}s)")
            return embeddings.astype(np.float32)

        except Exception as e:
            logger.error(f"Embedding hatası: {e}")
            raise

    def build_index(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        Chunk listesinden embedding oluşturup FAISS indeksine ekler.
        Metadata listesini de günceller.

        Args:
            chunks: Chunk listesi (her biri "text" anahtarına sahip olmalı)

        Returns:
            bool: Başarılı ise True
        """
        if not chunks:
            logger.warning("İndeks oluşturmak için chunk yok.")
            return False

        try:
            texts = [c["text"] for c in chunks]

            # Embedding oluştur
            embeddings = self.embed_texts(texts, show_progress=True)

            if embeddings.size == 0:
                logger.error("Embedding oluşturulamadı.")
                return False

            # FAISS indeksi oluştur
            self.index = faiss.IndexFlatL2(self.dimension)
            self.index.add(embeddings)

            # Metadata'yı güncelle
            self.metadata = chunks.copy()

            logger.info(f"FAISS indeksi oluşturuldu: {len(chunks)} vektör, Boyut: {self.dimension}")
            return True

        except Exception as e:
            logger.error(f"İndeks oluşturma hatası: {e}")
            return False

    def save_index(self) -> bool:
        """
        FAISS indeksini ve metadata'yı diske kaydeder.

        Returns:
            bool: Başarılı ise True
        """
        if self.index is None:
            logger.warning("Kaydedilecek indeks yok.")
            return False

        try:
            # Klasörleri oluştur
            FAISS_INDEX_PATH.parent.mkdir(exist_ok=True, parents=True)

            # FAISS indeksini kaydet
            faiss.write_index(self.index, str(FAISS_INDEX_PATH))

            # Metadata'yı kaydet
            with open(FAISS_METADATA_PATH, "wb") as f:
                pickle.dump(self.metadata, f)

            logger.info(f"İndeks kaydedildi: {FAISS_INDEX_PATH} ({len(self.metadata)} vektör)")
            return True

        except Exception as e:
            logger.error(f"İndeks kaydetme hatası: {e}")
            return False

    def load_index(self) -> bool:
        """
        Diske kaydedilmiş indeksi ve metadata'yı yükler.

        Returns:
            bool: Başarılı ise True
        """
        if not FAISS_INDEX_PATH.exists():
            logger.warning("Kayıtlı indeks dosyası bulunamadı.")
            return False

        if not FAISS_METADATA_PATH.exists():
            logger.warning("Kayıtlı metadata dosyası bulunamadı.")
            return False

        try:
            # FAISS indeksini yükle
            self.index = faiss.read_index(str(FAISS_INDEX_PATH))

            # Metadata'yı yükle
            with open(FAISS_METADATA_PATH, "rb") as f:
                self.metadata = pickle.load(f)

            logger.info(f"İndeks yüklendi: {len(self.metadata)} vektör, Boyut: {self.dimension}")
            return True

        except Exception as e:
            logger.error(f"İndeks yükleme hatası: {e}")
            return False

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Sorgu metnini embedding'e çevirir, en yakın k chunk'u döndürür.

        Args:
            query: Sorgu metni
            k: Döndürülecek sonuç sayısı

        Returns:
            List[Dict[str, Any]]: Her sonuç {"text": str, "page": int, "chunk_id": int, "distance": float}
        """
        if self.index is None:
            logger.warning("Arama yapılamıyor, indeks yok.")
            return []

        if not query.strip():
            return []

        try:
            # Sorguyu embedding'e çevir
            query_vec = self.embed_texts([query])

            # FAISS'de ara
            distances, indices = self.index.search(query_vec, min(k, len(self.metadata)))

            results = []
            for i, idx in enumerate(indices[0]):
                if idx == -1 or idx >= len(self.metadata):
                    continue

                meta = self.metadata[idx]
                results.append({
                    "text": meta["text"],
                    "page": meta["page"],
                    "chunk_id": meta.get("chunk_id", idx),
                    "distance": float(distances[0][i]),
                    "similarity": 1.0 / (1.0 + float(distances[0][i]))  # Basit similarity skoru
                })

            logger.info(f"Arama tamamlandı: '{query[:50]}...' -> {len(results)} sonuç bulundu.")
            return results

        except Exception as e:
            logger.error(f"Arama hatası: {e}")
            return []

    def get_index_info(self) -> Dict[str, Any]:
        """
        Mevcut indeks hakkında bilgi döndürür.

        Returns:
            Dict[str, Any]: İndeks bilgileri
        """
        if self.index is None:
            return {
                "initialized": self.is_initialized,
                "has_index": False,
                "vector_count": 0,
                "dimension": self.dimension
            }

        return {
            "initialized": self.is_initialized,
            "has_index": True,
            "vector_count": self.index.ntotal,
            "dimension": self.dimension,
            "metadata_count": len(self.metadata)
        }