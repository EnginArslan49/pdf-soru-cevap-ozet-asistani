# summarizer.py
import re
from collections import Counter
from typing import List, Dict, Any, Optional
from embeddings import EmbeddingEngine
from config import SUMMARY_MAX_CHUNKS, TR_STOP_WORDS
from logger import logger


class Summarizer:
    """
    PDF'in profesyonel özetini çıkarır:
    - Giriş (amaç/konu)
    - İçerik (ana başlıklar/konular)
    - Sonuç (çıkarımlar)
    - Önemli maddeler
    """

    def __init__(self, embedding_engine: Optional[EmbeddingEngine] = None):
        self.embedding_engine = embedding_engine

    def _get_complete_sentences(self, text: str, max_sentences: int = 5) -> str:
        """
        Metinden tam cümleleri alır. Kesinlikle yarım cümle döndürmez.
        Nokta, ünlem veya soru işareti ile biten cümleleri alır.
        """
        if not text:
            return ""

        # Cümleleri ayır (nokta, ünlem, soru işareti ile biten)
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Boş cümleleri temizle
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]

        # Tam cümleler: Nokta, ünlem veya soru işareti ile bitenler
        complete_sentences = []
        for s in sentences:
            if s and s[-1] in '.!?':
                complete_sentences.append(s)
            elif len(s) > 30:
                # Nokta yoksa ama uzunsa, sonuna nokta ekle
                complete_sentences.append(s + ".")

        # max_sentences kadar al
        result = ". ".join(complete_sentences[:max_sentences])

        # Sonuna nokta yoksa ekle
        if result and result[-1] not in '.!?':
            result += "."

        return result

    def _get_first_complete_sentences(self, chunks: List[Dict[str, Any]], count: int = 3) -> str:
        """Chunk'lardan ilk tam cümleleri alır"""
        full_text = " ".join([c["text"] for c in chunks[:SUMMARY_MAX_CHUNKS]])
        return self._get_complete_sentences(full_text, count)

    def _get_last_complete_sentences(self, chunks: List[Dict[str, Any]], count: int = 3) -> str:
        """Chunk'lardan son tam cümleleri alır (sonuç bölümü)"""
        # Son chunk'ları al
        last_chunks = chunks[-5:] if len(chunks) >= 5 else chunks
        full_text = " ".join([c["text"] for c in last_chunks])
        return self._get_complete_sentences(full_text, count)

    def _get_topic_sentences(self, chunks: List[Dict[str, Any]], count: int = 4) -> str:
        """En önemli konuları içeren tam cümleleri alır"""
        # Tüm metin
        full_text = " ".join([c["text"] for c in chunks])

        # En sık geçen kelimeleri bul (ana konular)
        words = re.findall(r'[a-zA-ZğüşıöçĞÜŞİÖÇ]+', full_text.lower())
        filtered = [w for w in words if w not in TR_STOP_WORDS and len(w) > 3]
        word_freq = Counter(filtered)
        top_words = [w for w, c in word_freq.most_common(8)]

        # Tüm cümleleri al
        sentences = re.split(r'(?<=[.!?])\s+', full_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        # Her cümleyi skorla (içinde anahtar kelime varsa yüksek puan)
        scored = []
        for sent in sentences:
            sent_lower = sent.lower()
            score = sum(1 for w in top_words[:5] if w in sent_lower)
            if score > 0:
                scored.append((score, sent))

        # Skora göre sırala
        scored.sort(reverse=True)

        # En iyi cümleleri al (tam cümleler)
        result_sentences = []
        for score, sent in scored[:count]:
            if sent and sent[-1] in '.!?':
                result_sentences.append(sent)
            elif len(sent) > 20:
                result_sentences.append(sent + ".")

        result = ". ".join(result_sentences[:count])

        # Sonuna nokta yoksa ekle
        if result and result[-1] not in '.!?':
            result += "."

        return result

    def _get_key_points(self, chunks: List[Dict[str, Any]], count: int = 8) -> str:
        """Önemli maddeleri liste halinde çıkarır - CÜMLELERİ KESMEZ"""
        full_text = " ".join([c["text"] for c in chunks])

        # En sık geçen kelimeler
        words = re.findall(r'[a-zA-ZğüşıöçĞÜŞİÖÇ]+', full_text.lower())
        filtered = [w for w in words if w not in TR_STOP_WORDS and len(w) > 3]
        word_freq = Counter(filtered)
        top_words = [w for w, c in word_freq.most_common(count)]

        # Tüm tam cümleleri bul (nokta, ünlem, soru işareti ile biten)
        sentences = re.split(r'(?<=[.!?])\s+', full_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30 and s[-1] in '.!?']

        points = []
        used_sentences = set()

        for word in top_words:
            for sent in sentences:
                if word in sent.lower() and sent not in used_sentences:
                    # Cümleyi KESME, tamamen ekle
                    points.append(sent)
                    used_sentences.add(sent)
                    break

        # En az 5 madde olsun
        if len(points) < 5:
            for sent in sentences:
                if sent not in used_sentences:
                    points.append(sent)
                    used_sentences.add(sent)
                    if len(points) >= 5:
                        break

        # Maddele - cümleleri kesme
        result = ""
        for i, point in enumerate(points[:10], 1):
            # Başında sayı ve nokta varsa temizle
            clean_point = re.sub(r'^\d+\.\s*', '', point)
            # Cümle nokta ile bitmiyorsa ekle
            if clean_point and clean_point[-1] not in '.!?':
                clean_point += "."
            result += f"{i}. {clean_point}\n"

        return result.strip()

    def summarize(self, chunks: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Chunk'lardan profesyonel özet çıkarır.
        TÜM CÜMLELER TAM VE NOKTA İLE BİTER.
        """
        if not chunks:
            return self._empty_summary()

        try:
            # Sayfa sayısı
            pages = set(c.get("page", 0) for c in chunks)
            page_count = len(pages)

            # Kelime sayısı
            full_text = " ".join([c["text"] for c in chunks])
            words = re.findall(r'[a-zA-ZğüşıöçĞÜŞİÖÇ]+', full_text)
            word_count = len(words)

            # ============================================================
            # 1. GİRİŞ BÖLÜMÜ - İlk 3 tam cümle
            # ============================================================
            intro = self._get_first_complete_sentences(chunks, count=3)

            # ============================================================
            # 2. ANA KONULAR - En önemli 4 cümle
            # ============================================================
            content = self._get_topic_sentences(chunks, count=4)

            # ============================================================
            # 3. SONUÇ BÖLÜMÜ - Son 3 tam cümle
            # ============================================================
            conclusion = self._get_last_complete_sentences(chunks, count=3)

            # ============================================================
            # 4. ÖNEMLİ MADDELER
            # ============================================================
            key_points = self._get_key_points(chunks, count=8)

            # ============================================================
            # 5. TAM ÖZET (Giriş + İçerik + Sonuç)
            # ============================================================
            summary_parts = []

            if intro and len(intro) > 20:
                summary_parts.append(f"**📖 Giriş**\n\n{intro}")

            if content and len(content) > 20 and content != intro:
                summary_parts.append(f"**📌 Ana Konular**\n\n{content}")

            if conclusion and len(conclusion) > 20:
                summary_parts.append(f"**🔚 Sonuç**\n\n{conclusion}")

            # Eğer giriş ve içerik aynıysa, sadece birini göster
            if len(summary_parts) >= 2:
                # Giriş ve içerik aynı mı kontrol et
                if intro == content and len(summary_parts) >= 2:
                    summary_parts.pop(1)  # içeriği çıkar

            summary = "\n\n---\n\n".join(summary_parts)

            # Hiçbir yerde ... ile bitmesin
            summary = summary.replace('...', '')

            logger.info(f"Profesyonel özet oluşturuldu: {len(chunks)} chunk, {word_count} kelime")

            return {
                "summary": summary,
                "intro": intro,
                "content": content,
                "conclusion": conclusion,
                "key_points": key_points,
                "word_count": str(word_count),
                "page_count": str(page_count),
                "chunk_count": str(len(chunks))
            }

        except Exception as e:
            logger.error(f"Özet oluşturma hatası: {e}")
            return self._empty_summary()

    def _empty_summary(self) -> Dict[str, str]:
        """Boş özet döndürür"""
        return {
            "summary": "PDF içeriği boş veya okunamadı. Lütfen farklı bir PDF deneyin.",
            "intro": "Giriş bölümü oluşturulamadı.",
            "content": "Ana konular oluşturulamadı.",
            "conclusion": "Sonuç bölümü oluşturulamadı.",
            "key_points": "Önemli nokta bulunamadı.",
            "word_count": "0",
            "page_count": "0",
            "chunk_count": "0"
        }

    def extract_key_sentences(self, chunks: List[Dict[str, Any]], max_sentences: int = 10) -> List[str]:
        """En önemli tam cümleleri çıkarır"""
        if not chunks:
            return []

        try:
            full_text = " ".join([c["text"] for c in chunks])

            # Cümleleri ayır
            sentences = re.split(r'(?<=[.!?])\s+', full_text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 30 and s[-1] in '.!?']

            # Kelime frekansı
            words = re.findall(r'[a-zA-ZğüşıöçĞÜŞİÖÇ]+', full_text.lower())
            filtered = [w for w in words if w not in TR_STOP_WORDS and len(w) > 3]
            word_freq = Counter(filtered)

            # Cümleleri skorla
            scored = []
            for sent in sentences:
                sent_words = re.findall(r'[a-zA-ZğüşıöçĞÜŞİÖÇ]+', sent.lower())
                score = sum(word_freq.get(w, 0) for w in sent_words)
                scored.append((score, sent))

            scored.sort(reverse=True)

            # En iyi cümleleri döndür (tam cümleler)
            result = []
            for score, sent in scored[:max_sentences]:
                if sent and sent[-1] in '.!?':
                    result.append(sent)
                else:
                    result.append(sent + ".")

            return result

        except Exception as e:
            logger.error(f"Önemli cümle çıkarma hatası: {e}")
            return []