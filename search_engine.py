# search_engine.py
import re
from typing import List, Dict, Any, Optional
from collections import defaultdict
from logger import logger


class SearchEngine:
    """
    PDF içinde belirli bir kelime veya kelime grubunu arar,
    sayfa numarası ve bağlamıyla birlikte döndürür.

    Attributes:
        case_sensitive: Büyük/küçük harf duyarlılığı
        context_chars: Sonuçlarda gösterilecek bağlam karakter sayısı
    """

    def __init__(self, case_sensitive: bool = False, context_chars: int = 100):
        """
        SearchEngine'i başlatır.

        Args:
            case_sensitive: Büyük/küçük harf duyarlılığı
            context_chars: Sonuçlarda gösterilecek bağlam karakter sayısı
        """
        self.case_sensitive = case_sensitive
        self.context_chars = context_chars

    def search(self, chunks: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Tüm chunk'larda query kelimesini arar.

        Args:
            chunks: Chunk listesi (her biri "text" ve "page" anahtarlarına sahip)
            query: Aranacak kelime veya kelime grubu

        Returns:
            List[Dict[str, Any]]: Her sonuç {
                "page": int,
                "text": str,
                "snippet": str,
                "position": int,
                "match_count": int
            }
        """
        if not chunks:
            logger.warning("Arama yapmak için chunk yok.")
            return []

        if not query or not query.strip():
            logger.warning("Boş sorgu.")
            return []

        try:
            query = query.strip()
            results = []

            # Büyük/küçük harf duyarlılığı
            if not self.case_sensitive:
                query_lower = query.lower()
            else:
                query_lower = query

            for chunk in chunks:
                text = chunk.get("text", "")
                page = chunk.get("page", 0)

                if not text:
                    continue

                # Metni kontrol et
                text_for_search = text if self.case_sensitive else text.lower()

                # Kaç tane eşleşme var?
                matches = re.findall(re.escape(query_lower), text_for_search)
                match_count = len(matches)

                if match_count > 0:
                    # İlk eşleşmenin pozisyonunu bul
                    position = text_for_search.find(query_lower)

                    # Bağlam (context) oluştur
                    start = max(0, position - self.context_chars)
                    end = min(len(text), position + len(query) + self.context_chars)

                    snippet = text[start:end]

                    # Eğer snippet uzunsa kısalt
                    if len(snippet) > 250:
                        snippet = snippet[:247] + "..."

                    results.append({
                        "page": page,
                        "text": text[:300] + "..." if len(text) > 300 else text,
                        "snippet": snippet,
                        "position": position,
                        "match_count": match_count,
                        "chunk_id": chunk.get("chunk_id", 0)
                    })

            # Sonuçları sayfa numarasına göre sırala
            results.sort(key=lambda x: (x["page"], x["position"]))

            logger.info(f"Arama tamamlandı: '{query}' -> {len(results)} sonuç bulundu.")
            return results

        except Exception as e:
            logger.error(f"Arama hatası: {e}")
            return []

    def search_exact(self, chunks: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Tam eşleşme araması yapar (kelime sınırlarına dikkat eder).

        Args:
            chunks: Chunk listesi
            query: Aranacak kelime

        Returns:
            List[Dict[str, Any]]: Sonuçlar
        """
        if not chunks or not query:
            return []

        try:
            pattern = r'\b' + re.escape(query) + r'\b'
            results = []

            for chunk in chunks:
                text = chunk.get("text", "")
                page = chunk.get("page", 0)

                if not text:
                    continue

                # Büyük/küçük harf duyarlılığı
                flags = 0 if self.case_sensitive else re.IGNORECASE
                matches = re.finditer(pattern, text, flags)

                match_count = 0
                positions = []

                for match in matches:
                    match_count += 1
                    positions.append(match.start())

                if match_count > 0:
                    # İlk eşleşme için snippet
                    position = positions[0]
                    start = max(0, position - self.context_chars)
                    end = min(len(text), position + len(query) + self.context_chars)
                    snippet = text[start:end]

                    if len(snippet) > 250:
                        snippet = snippet[:247] + "..."

                    results.append({
                        "page": page,
                        "text": text[:300] + "..." if len(text) > 300 else text,
                        "snippet": snippet,
                        "position": position,
                        "match_count": match_count,
                        "positions": positions[:10],  # İlk 10 pozisyon
                        "chunk_id": chunk.get("chunk_id", 0)
                    })

            results.sort(key=lambda x: (x["page"], x["position"]))
            logger.info(f"Tam eşleşme araması: '{query}' -> {len(results)} sonuç")
            return results

        except Exception as e:
            logger.error(f"Tam eşleşme arama hatası: {e}")
            return []

    def search_multiple(self, chunks: List[Dict[str, Any]], queries: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Birden fazla kelime için arama yapar.

        Args:
            chunks: Chunk listesi
            queries: Aranacak kelime listesi

        Returns:
            Dict[str, List[Dict[str, Any]]]: Her sorgu için sonuçlar
        """
        results = {}
        for query in queries:
            if query and query.strip():
                results[query] = self.search(chunks, query)
        return results

    def get_search_stats(self, chunks: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
        """
        Arama hakkında istatistikler döndürür.

        Args:
            chunks: Chunk listesi
            query: Aranacak kelime

        Returns:
            Dict[str, Any]: İstatistikler
        """
        if not chunks:
            return {
                "query": query,
                "total_chunks": 0,
                "total_matches": 0,
                "unique_pages": 0,
                "matches_per_page": {}
            }

        try:
            results = self.search(chunks, query)

            # Sayfalara göre dağılım
            page_counts = defaultdict(int)
            for r in results:
                page_counts[r["page"]] += r["match_count"]

            return {
                "query": query,
                "total_chunks": len(chunks),
                "total_matches": sum(r["match_count"] for r in results),
                "unique_pages": len(set(r["page"] for r in results)),
                "matches_per_page": dict(page_counts),
                "result_count": len(results)
            }

        except Exception as e:
            logger.error(f"Arama istatistikleri hatası: {e}")
            return {
                "query": query,
                "error": str(e)
            }