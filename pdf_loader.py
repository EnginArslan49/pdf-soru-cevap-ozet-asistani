# pdf_loader.py
import io
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from logger import logger
from config import CHUNK_SIZE, CHUNK_OVERLAP
from utils import clean_text

# PDF okuma kütüphaneleri
try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.warning("pdfplumber yüklü değil. pip install pdfplumber")

try:
    import easyocr
    from PIL import Image
    import numpy as np

    OCR_AVAILABLE = True
    logger.info("EasyOCR yüklü, resim tabanlı PDF'ler için hazır")
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("easyocr yüklü değil. pip install easyocr")


class PDFLoader:
    """
    PDF dosyasını yükler. Önce metin tabanlı okumayı dener,
    başarısız olursa EasyOCR ile okur (harici program gerektirmez).
    """

    def __init__(self, file_bytes: bytes, filename: str = "unknown.pdf"):
        self.file_bytes = file_bytes
        self.filename = filename
        self.pages_text: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []
        self.total_pages: int = 0
        self._is_loaded: bool = False
        self.used_ocr: bool = False
        self.extraction_method: str = "unknown"
        self._ocr_reader = None

    def _get_ocr_reader(self):
        """EasyOCR okuyucuyu lazy initialize et"""
        if self._ocr_reader is None and OCR_AVAILABLE:
            try:
                # Türkçe ve İngilizce destekli
                self._ocr_reader = easyocr.Reader(['tr', 'en'], gpu=False)
                logger.info("EasyOCR okuyucu başlatıldı")
            except Exception as e:
                logger.error(f"EasyOCR başlatma hatası: {e}")
                self._ocr_reader = None
        return self._ocr_reader

    def load(self) -> bool:
        """
        PDF'i okur. Önce pdfplumber ile dener, başarısız olursa EasyOCR ile dener.
        """
        # 1. Önce pdfplumber ile dene (en iyi sonuç)
        if PDFPLUMBER_AVAILABLE:
            logger.info("📖 pdfplumber ile PDF okunuyor...")
            if self._load_with_pdfplumber():
                self.extraction_method = "pdfplumber"
                self._is_loaded = True
                return True
            logger.warning("pdfplumber ile okuma başarısız, diğer yöntemler deneniyor...")

        # 2. pypdf ile dene (eski yöntem)
        logger.info("📖 pypdf ile PDF okunuyor...")
        if self._load_with_pypdf():
            self.extraction_method = "pypdf"
            self._is_loaded = True
            return True

        # 3. EasyOCR ile dene (resim tabanlı PDF, harici program gerektirmez)
        if OCR_AVAILABLE:
            logger.info("📖 EasyOCR ile PDF okunuyor (resim tabanlı)...")
            if self._load_with_easyocr():
                self.extraction_method = "easyocr"
                self._is_loaded = True
                self.used_ocr = True
                return True
            logger.warning("EasyOCR ile okuma başarısız")

        logger.error(f"PDF okunamadı: {self.filename}. Tüm yöntemler başarısız.")
        return False

    # pdf_loader.py - Metin çıkarma bölümü (DÜZELTİLMİŞ)

    def _load_with_pdfplumber(self) -> bool:
        """pdfplumber ile PDF okuma - Türkçe karakterleri korur"""
        try:
            with pdfplumber.open(io.BytesIO(self.file_bytes)) as pdf:
                self.total_pages = len(pdf.pages)
                self.pages_text = []

                for page_num, page in enumerate(pdf.pages, start=1):
                    try:
                        # Metni al, temizleme yapma (sadece gereksiz boşlukları temizle)
                        text = page.extract_text() or ""

                        # Sadece fazla boşlukları temizle, kelimeleri kesme
                        text = re.sub(r'\s+', ' ', text)
                        text = text.strip()

                        if text:
                            self.pages_text.append({
                                "page_num": page_num,
                                "text": text,
                                "char_count": len(text)
                            })
                    except Exception as e:
                        logger.warning(f"pdfplumber sayfa {page_num} hatası: {e}")
                        continue

                if not self.pages_text:
                    logger.warning("pdfplumber metin çıkaramadı")
                    return False

                total_chars = sum(p["char_count"] for p in self.pages_text)
                logger.info(f"pdfplumber: {len(self.pages_text)} sayfa, {total_chars} karakter")
                return True

        except Exception as e:
            logger.error(f"pdfplumber hatası: {e}")
            return False

    def _load_with_pypdf(self) -> bool:
        """pypdf ile PDF okuma - Türkçe karakterleri korur"""
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(self.file_bytes))

            if reader.is_encrypted:
                logger.warning("PDF şifreli")
                return False

            self.total_pages = len(reader.pages)
            self.pages_text = []

            for page_num, page in enumerate(reader.pages, start=1):
                try:
                    text = page.extract_text() or ""

                    # Sadece fazla boşlukları temizle, kelimeleri kesme
                    text = re.sub(r'\s+', ' ', text)
                    text = text.strip()

                    if text:
                        self.pages_text.append({
                            "page_num": page_num,
                            "text": text,
                            "char_count": len(text)
                        })
                except Exception as e:
                    logger.warning(f"pypdf sayfa {page_num} hatası: {e}")
                    continue

            if not self.pages_text:
                logger.warning("pypdf metin çıkaramadı")
                return False

            total_chars = sum(p["char_count"] for p in self.pages_text)
            logger.info(f"pypdf: {len(self.pages_text)} sayfa, {total_chars} karakter")
            return True

        except Exception as e:
            logger.error(f"pypdf hatası: {e}")
            return False

    def _load_with_easyocr(self) -> bool:
        """EasyOCR ile PDF okuma (resim tabanlı PDF'ler için, harici program gerektirmez)"""
        try:
            # PDF'yi resimlere çevir (Pillow ile)
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(
                self.file_bytes,
                dpi=200,  # Daha düşük DPI = daha hızlı
                fmt='jpeg'
            )

            self.total_pages = len(images)
            self.pages_text = []

            # EasyOCR okuyucuyu al
            reader = self._get_ocr_reader()
            if reader is None:
                logger.error("EasyOCR okuyucu başlatılamadı")
                return False

            for page_num, image in enumerate(images, start=1):
                try:
                    # Resmi numpy array'e çevir
                    import numpy as np
                    image_np = np.array(image)

                    # OCR ile metin çıkar (Türkçe + İngilizce)
                    results = reader.readtext(image_np, detail=0, paragraph=True)
                    text = " ".join(results)
                    text = clean_text(text)

                    if text:
                        self.pages_text.append({
                            "page_num": page_num,
                            "text": text,
                            "char_count": len(text)
                        })
                    else:
                        logger.warning(f"EasyOCR sayfa {page_num} metin çıkaramadı")

                except Exception as e:
                    logger.warning(f"EasyOCR sayfa {page_num} hatası: {e}")
                    continue

            if not self.pages_text:
                logger.warning("EasyOCR metin çıkaramadı")
                return False

            total_chars = sum(p["char_count"] for p in self.pages_text)
            logger.info(f"EasyOCR: {len(self.pages_text)} sayfa, {total_chars} karakter")
            return True

        except ImportError as e:
            logger.error(f"pdf2image veya easyocr import hatası: {e}")
            logger.info("Lütfen şunu yükleyin: pip install easyocr pdf2image pillow")
            return False
        except Exception as e:
            logger.error(f"EasyOCR hatası: {e}")
            return False

    def chunk_pages(self) -> List[Dict[str, Any]]:
        """
        Sayfaları CHUNK_SIZE ve CHUNK_OVERLAP ile böler.
        Kelimeleri kesmeden böler (kelime sınırlarına dikkat eder).
        """
        if not self._is_loaded or not self.pages_text:
            logger.warning("Chunk oluşturmak için sayfa yok.")
            return []

        chunks = []
        chunk_id = 0

        for page_info in self.pages_text:
            page_num = page_info["page_num"]
            text = page_info["text"]
            text_len = len(text)

            if text_len == 0:
                continue

            # Sliding window ile chunk oluştur
            start = 0
            while start < text_len:
                end = min(start + CHUNK_SIZE, text_len)

                # Eğer son chunk değilse, kelime sınırında kes
                if end < text_len:
                    # Bir sonraki boşluğa kadar git (kelimeyi kesme)
                    space_pos = text.find(' ', end)
                    if space_pos != -1:
                        end = space_pos
                    else:
                        # Boşluk bulunamazsa, bir önceki boşluğa git
                        last_space = text.rfind(' ', start, end)
                        if last_space != -1:
                            end = last_space

                chunk_text = text[start:end]

                if chunk_text.strip():
                    chunks.append({
                        "chunk_id": chunk_id,
                        "text": chunk_text,
                        "page": page_num,
                        "start_char": start,
                        "end_char": end,
                        "char_count": len(chunk_text)
                    })
                    chunk_id += 1

                # Bir sonraki başlangıç pozisyonu
                start += CHUNK_SIZE - CHUNK_OVERLAP
                if start >= text_len:
                    break

        self.chunks = chunks

        if not chunks:
            logger.error("Hiç chunk oluşturulamadı!")
            if self.pages_text:
                first_text = self.pages_text[0]["text"][:200]
                logger.error(f"İlk sayfa metni (ilk 200 karakter): {first_text}")
        else:
            method_text = f" (Yöntem: {self.extraction_method})"
            if self.used_ocr:
                method_text += " [OCR KULLANILDI]"
            logger.info(f"{len(chunks)} chunk oluşturuldu.{method_text}")

        return chunks

    def get_extraction_info(self) -> Dict[str, Any]:
        """Hangi yöntemle okunduğunu döndürür"""
        return {
            "extraction_method": self.extraction_method,
            "used_ocr": self.used_ocr,
            "total_pages": self.total_pages,
            "extracted_pages": len(self.pages_text),
            "chunk_count": len(self.chunks)
        }

    def get_page_count(self) -> int:
        return self.total_pages

    def get_chunk_count(self) -> int:
        return len(self.chunks)

    def get_summary_stats(self) -> Dict[str, Any]:
        if not self._is_loaded:
            return {
                "filename": self.filename,
                "loaded": False,
                "error": "PDF yüklenmemiş"
            }

        total_chars = sum(p["char_count"] for p in self.pages_text)
        avg_chars_per_page = total_chars / len(self.pages_text) if self.pages_text else 0

        return {
            "filename": self.filename,
            "loaded": True,
            "extraction_method": self.extraction_method,
            "used_ocr": self.used_ocr,
            "total_pages": self.total_pages,
            "extracted_pages": len(self.pages_text),
            "total_chars": total_chars,
            "avg_chars_per_page": round(avg_chars_per_page, 2),
            "chunk_count": len(self.chunks),
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP
        }