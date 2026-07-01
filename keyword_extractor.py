# keyword_extractor.py
from collections import Counter
import re
from typing import List, Dict, Any, Optional
from config import TR_STOP_WORDS, KEYWORD_OPTIONS
from logger import logger


class KeywordExtractor:
    """
    PDF metninden en sık geçen anlamlı kelimeleri çıkarır.
    Türkçe stop-word desteği ile.
    """

    def __init__(self, min_word_length: int = 3, max_keywords: int = 30):
        """
        KeywordExtractor'ı başlatır.

        Args:
            min_word_length: Minimum kelime uzunluğu
            max_keywords: Maksimum anahtar kelime sayısı
        """
        self.min_word_length = min_word_length
        self.max_keywords = max_keywords

    def extract(self, chunks: List[Dict[str, Any]], top_n: int = 20) -> List[str]:
        """
        Tüm chunk'lardan metin birleştir, stop-word'leri temizle,
        en sık geçen top_n kelimeyi döndürür.

        Args:
            chunks: Chunk listesi (her biri "text" anahtarına sahip)
            top_n: Döndürülecek kelime sayısı (10, 20 veya 30)

        Returns:
            List[str]: Anahtar kelime listesi
        """
        if not chunks:
            logger.warning("Anahtar kelime çıkarmak için chunk yok.")
            return []

        # top_n geçerli mi kontrol et
        if top_n not in KEYWORD_OPTIONS:
            logger.warning(f"Geçersiz top_n değeri: {top_n}, varsayılan 20 kullanılıyor.")
            top_n = 20

        try:
            # Tüm metni birleştir
            full_text = " ".join([c.get("text", "") for c in chunks])

            # Sadece harf içeren kelimeleri al (Türkçe karakterler dahil)
            words = re.findall(r'[a-zA-ZğüşıöçĞÜŞİÖÇ]+', full_text.lower())

            # Stop-word'leri ve kısa kelimeleri filtrele
            filtered_words = [
                w for w in words
                if w not in TR_STOP_WORDS
                   and len(w) >= self.min_word_length
                   and not w.isdigit()
            ]

            if not filtered_words:
                logger.warning("Filtrelenmiş kelime bulunamadı.")
                return []

            # Frekans hesapla
            word_freq = Counter(filtered_words)

            # En sık geçenleri al
            most_common = word_freq.most_common(top_n)

            # Sadece kelimeleri döndür
            keywords = [word for word, count in most_common]

            logger.info(f"{len(keywords)} anahtar kelime çıkarıldı (top_n={top_n})")
            return keywords

        except Exception as e:
            logger.error(f"Anahtar kelime çıkarma hatası: {e}")
            return []

    def extract_with_scores(self, chunks: List[Dict[str, Any]], top_n: int = 20) -> List[Dict[str, Any]]:
        """
        Anahtar kelimeleri frekans skorları ile birlikte döndürür.

        Args:
            chunks: Chunk listesi
            top_n: Döndürülecek kelime sayısı

        Returns:
            List[Dict[str, Any]]: Her biri {"keyword": str, "count": int, "score": float}
        """
        if not chunks:
            return []

        try:
            # Metni birleştir
            full_text = " ".join([c.get("text", "") for c in chunks])
            words = re.findall(r'[a-zA-ZğüşıöçĞÜŞİÖÇ]+', full_text.lower())

            # Filtrele
            filtered_words = [
                w for w in words
                if w not in TR_STOP_WORDS
                   and len(w) >= self.min_word_length
                   and not w.isdigit()
            ]

            if not filtered_words:
                return []

            # Frekans hesapla
            word_freq = Counter(filtered_words)
            total_words = len(filtered_words)

            # En sık geçenleri al
            most_common = word_freq.most_common(top_n)

            # Skorlu sonuç
            results = []
            for word, count in most_common:
                score = round(count / total_words * 100, 2) if total_words > 0 else 0
                results.append({
                    "keyword": word,
                    "count": count,
                    "score": score
                })

            return results

        except Exception as e:
            logger.error(f"Skorlu anahtar kelime çıkarma hatası: {e}")
            return []

    def get_keyword_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Metin hakkında kelime istatistikleri döndürür.

        Args:
            chunks: Chunk listesi

        Returns:
            Dict[str, Any]: İstatistikler
        """
        if not chunks:
            return {
                "total_words": 0,
                "unique_words": 0,
                "stop_word_count": 0,
                "avg_word_length": 0
            }

        try:
            full_text = " ".join([c.get("text", "") for c in chunks])
            words = re.findall(r'[a-zA-ZğüşıöçĞÜŞİÖÇ]+', full_text.lower())

            total_words = len(words)
            unique_words = len(set(words))

            # Stop-word sayısı
            stop_words = [w for w in words if w in TR_STOP_WORDS]
            stop_word_count = len(stop_words)

            # Ortalama kelime uzunluğu
            avg_length = sum(len(w) for w in words) / total_words if total_words > 0 else 0

            return {
                "total_words": total_words,
                "unique_words": unique_words,
                "stop_word_count": stop_word_count,
                "avg_word_length": round(avg_length, 2),
                "word_diversity": round(unique_words / total_words * 100, 2) if total_words > 0 else 0
            }

        except Exception as e:
            logger.error(f"Kelime istatistikleri hatası: {e}")
            return {
                "total_words": 0,
                "unique_words": 0,
                "stop_word_count": 0,
                "avg_word_length": 0
            }