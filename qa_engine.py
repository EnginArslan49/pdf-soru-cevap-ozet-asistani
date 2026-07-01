# qa_engine.py
import re
from typing import List, Dict, Any, Optional
from embeddings import EmbeddingEngine
from logger import logger
from config import CHUNK_SIZE


class QAEngine:
    """
    Kullanıcı sorusunu alır, embedding ile arama yapar,
    en alakalı chunk'ları cevap olarak döndürür.
    Kısa (1-2 cümle) ve uzun (detaylı) cevap üretir.
    """

    def __init__(self, embedding_engine: EmbeddingEngine, max_context_chunks: int = 5):
        self.embedding_engine = embedding_engine
        self.max_context_chunks = max_context_chunks

    def _extract_sentences(self, text: str, max_sentences: int = 3) -> str:
        """Metinden ilk max_sentences cümleyi çıkarır"""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        return ". ".join(sentences[:max_sentences])

    def _generate_short_answer(self, chunks: List[Dict[str, Any]]) -> str:
        """
        En alakalı chunk'lardan kısa cevap (1-2 cümle) üretir.
        Türkçe karakterleri korur.
        """
        if not chunks:
            return "Cevap bulunamadı."

        # İlk 2 chunk'u al
        best_chunks = chunks[:2]
        combined_text = " ".join([c["text"] for c in best_chunks])

        # Cümleleri bul (Türkçe karakterleri koru)
        sentences = re.split(r'[.!?]+', combined_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]

        if not sentences:
            # Eğer cümle bulunamazsa, ilk 200 karakteri al
            return combined_text[:200] + "..." if len(combined_text) > 200 else combined_text

        # En kısa 2 cümleyi al (genelde en öz olanlar)
        sentences.sort(key=len)
        short_answer = ". ".join(sentences[:2])

        # Sonunda nokta yoksa ekle
        if short_answer and not short_answer[-1] in '.!?':
            short_answer += "."

        # Çok uzunsa kısalt
        if len(short_answer) > 300:
            short_answer = short_answer[:297] + "..."

        return short_answer

    def _generate_long_answer(self, chunks: List[Dict[str, Any]]) -> str:
        """
        En alakalı chunk'lardan uzun cevap (detaylı) üretir.
        """
        if not chunks:
            return "Cevap bulunamadı."

        # İlk 3 chunk'u al
        best_chunks = chunks[:3]
        answer_parts = []

        for idx, chunk in enumerate(best_chunks, 1):
            page = chunk.get('page', '?')
            text = chunk.get('text', '')

            # Sayfa bilgisi ekle
            page_info = f"[Sayfa {page}]"
            answer_parts.append(f"{page_info} {text}")

        combined_answer = "\n\n---\n\n".join(answer_parts)

        # Çok uzunsa kısalt
        if len(combined_answer) > 2000:
            combined_answer = combined_answer[:1997] + "..."

        return combined_answer

    def answer(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Soruyu alır, en alakalı chunk'ları bulur ve kısa/uzun cevap oluşturur.

        Returns:
            Dict[str, Any]: {
                "short_answer": str,    # 1-2 cümle
                "long_answer": str,     # detaylı cevap
                "sources": List[dict],
                "found": bool,
                "question": str,
                "confidence": float
            }
        """
        if not question or not question.strip():
            return {
                "short_answer": "Lütfen geçerli bir soru girin.",
                "long_answer": "",
                "sources": [],
                "found": False,
                "question": question,
                "confidence": 0.0
            }

        index_info = self.embedding_engine.get_index_info()
        if not index_info["has_index"]:
            return {
                "short_answer": "Henüz bir PDF indekslenmemiş.",
                "long_answer": "Lütfen önce bir PDF yükleyin ve indeksleyin.",
                "sources": [],
                "found": False,
                "question": question,
                "confidence": 0.0
            }

        try:
            results = self.embedding_engine.search(question, k=top_k)

            if not results:
                return {
                    "short_answer": "Bu bilgi PDF içerisinde bulunamadı.",
                    "long_answer": "Lütfen başka bir soru deneyin veya sorunuzu daha net ifade edin.",
                    "sources": [],
                    "found": False,
                    "question": question,
                    "confidence": 0.0
                }

            # En alakalı chunk'ları seç
            best_chunks = results[:self.max_context_chunks]

            # Kısa ve uzun cevap üret
            short_answer = self._generate_short_answer(best_chunks)
            long_answer = self._generate_long_answer(best_chunks)

            # Güven skoru
            avg_similarity = sum(r.get('similarity', 0) for r in results[:3]) / min(3, len(results))
            confidence = round(avg_similarity * 100, 2)

            # Kaynaklar
            sources = [
                {
                    "page": r.get("page", "?"),
                    "text": r["text"][:300] + "..." if len(r["text"]) > 300 else r["text"],
                    "distance": r.get("distance", 0),
                    "similarity": r.get("similarity", 0)
                }
                for r in results[:5]
            ]

            logger.info(f"Soru cevaplandı: '{question[:50]}...' -> güven: {confidence}%")

            return {
                "short_answer": short_answer,
                "long_answer": long_answer,
                "sources": sources,
                "found": True,
                "question": question,
                "confidence": confidence,
                "total_results": len(results)
            }

        except Exception as e:
            logger.error(f"Soru cevaplama hatası: {e}")
            return {
                "short_answer": f"Cevap aranırken bir hata oluştu.",
                "long_answer": f"Hata detayı: {str(e)}",
                "sources": [],
                "found": False,
                "question": question,
                "confidence": 0.0,
                "error": str(e)
            }

    def get_related_chunks(self, question: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Sadece alakalı chunk'ları döndürür."""
        try:
            return self.embedding_engine.search(question, k=top_k)
        except Exception as e:
            logger.error(f"Alakalı chunk arama hatası: {e}")
            return []