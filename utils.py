# utils.py
import os
import re
import tempfile
import shutil
import hashlib
from pathlib import Path
from typing import Optional, Union, BinaryIO, Any
from datetime import datetime
from logger import logger
from config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB


def validate_file_extension(filename: str) -> bool:
    """
    Dosya uzantısının .pdf olup olmadığını kontrol eder.

    Args:
        filename: Dosya adı

    Returns:
        bool: Geçerli ise True
    """
    if not filename:
        return False
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def validate_file_size(file_input: Any) -> bool:
    """
    Dosya boyutunun maksimum değeri aşıp aşmadığını kontrol eder.
    UploadedFile, bytes veya file object ile çalışır.

    Args:
        file_input: UploadedFile, bytes veya file object

    Returns:
        bool: Boyut uygunsa True
    """
    try:
        # UploadedFile ise (Streamlit)
        if hasattr(file_input, 'getbuffer'):
            size = len(file_input.getbuffer())
        # Bytes ise
        elif isinstance(file_input, bytes):
            size = len(file_input)
        # File object ise
        elif hasattr(file_input, 'read'):
            pos = file_input.tell()
            file_input.seek(0, 2)
            size = file_input.tell()
            file_input.seek(pos)
        else:
            # Diğer durumlar için len dene
            size = len(file_input)

        logger.info(
            f"Dosya boyutu: {size} bytes ({size / 1024 / 1024:.2f} MB), Maks: {MAX_FILE_SIZE_BYTES} bytes ({MAX_FILE_SIZE_MB} MB)")
        return size <= MAX_FILE_SIZE_BYTES

    except Exception as e:
        logger.error(f"Dosya boyutu kontrolü hatası: {e}")
        return False


def is_encrypted_pdf(file_input: Any) -> bool:
    """
    PDF'in şifreli olup olmadığını kontrol eder (ön kontrol).

    Args:
        file_input: UploadedFile, bytes veya file object

    Returns:
        bool: Şifreli ise True
    """
    try:
        # Bytes'e çevir
        if hasattr(file_input, 'getbuffer'):
            file_bytes = bytes(file_input.getbuffer())
        elif isinstance(file_input, bytes):
            file_bytes = file_input
        elif hasattr(file_input, 'read'):
            file_bytes = file_input.read()
            if hasattr(file_input, 'seek'):
                file_input.seek(0)
        else:
            file_bytes = bytes(file_input)

        # İlk 1000 byte'ı kontrol et
        content = file_bytes[:1000]
        text = content.decode('latin-1', errors='ignore')
        return "/Encrypt" in text

    except Exception as e:
        logger.warning(f"PDF şifre kontrolü hatası: {e}")
        return False


# clean_text fonksiyonu (DÜZELTİLMİŞ)
def clean_text(text: str) -> str:
    """
    Metni temizler, Türkçe karakterleri korur.
    Kelimeleri kesmez, sadece gereksiz boşlukları temizler.
    """
    if not text:
        return ""

    # Normalize edilmiş metin
    # 1. Satır sonlarını boşluğa çevir
    text = text.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')

    # 2. Birden fazla boşluğu tek boşluğa indir
    text = re.sub(r' +', ' ', text)

    # 3. Baştan ve sondan boşlukları sil
    text = text.strip()

    # 4. Gereksiz özel karakterleri temizle (Türkçe karakterleri koru)
    # Sadece alfa-numerik, Türkçe karakterler, noktalama işaretleri ve boşluk kalır
    text = re.sub(r'[^\w\sğüşıöçĞÜŞİÖÇ\.,;:!?()\-"\'/]', ' ', text)

    # 5. Tekrar birden fazla boşluğu temizle
    text = re.sub(r' +', ' ', text)

    return text.strip()


def generate_file_hash(file_input: Any) -> str:
    """
    Dosya içeriğinin SHA256 hash'ini oluşturur.

    Args:
        file_input: UploadedFile veya bytes

    Returns:
        str: SHA256 hash
    """
    try:
        if hasattr(file_input, 'getbuffer'):
            data = file_input.getbuffer()
        elif isinstance(file_input, bytes):
            data = file_input
        else:
            data = bytes(file_input)
        return hashlib.sha256(data).hexdigest()
    except Exception as e:
        logger.error(f"Hash oluşturma hatası: {e}")
        return ""


def save_uploaded_file(uploaded_file) -> Optional[Path]:
    """
    Streamlit'in UploadedFile nesnesini geçici bir dosyaya kaydeder.

    Args:
        uploaded_file: Streamlit UploadedFile nesnesi

    Returns:
        Optional[Path]: Kaydedilen dosyanın yolu, hata durumunda None
    """
    if uploaded_file is None:
        return None

    try:
        # Geçici klasör oluştur
        temp_dir = Path(tempfile.gettempdir()) / f"pdf_assistant_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(exist_ok=True, parents=True)

        # Dosya adını güvenli hale getir
        safe_filename = re.sub(r'[^\w\-_\. ]', '_', uploaded_file.name)
        temp_path = temp_dir / safe_filename

        # Dosyayı yaz
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        logger.info(f"Geçici dosya kaydedildi: {temp_path} (Boyut: {temp_path.stat().st_size} bytes)")
        return temp_path

    except Exception as e:
        logger.error(f"Dosya kaydetme hatası: {e}")
        return None


def cleanup_temp_file(path: Optional[Path]) -> None:
    """
    Geçici dosyayı ve klasörünü siler.

    Args:
        path: Silinecek dosyanın yolu
    """
    if path is None or not path.exists():
        return

    try:
        parent = path.parent
        # Önce dosyayı sil
        if path.exists():
            path.unlink()
        # Sonra klasörü sil (içi boşsa)
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
        logger.info(f"Geçici dosya temizlendi: {path}")
    except Exception as e:
        logger.warning(f"Temizleme hatası (önemsiz): {e}")


def get_file_size_str(size_bytes: int) -> str:
    """
    Dosya boyutunu okunabilir formata çevirir.

    Args:
        size_bytes: Byte cinsinden boyut

    Returns:
        str: Örn: "2.5 MB"
    """
    if size_bytes <= 0:
        return "0 B"

    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def get_file_size_mb(file_input: Any) -> float:
    """
    Dosya boyutunu MB cinsinden döndürür.

    Args:
        file_input: UploadedFile veya bytes

    Returns:
        float: MB cinsinden boyut
    """
    try:
        if hasattr(file_input, 'getbuffer'):
            size = len(file_input.getbuffer())
        elif isinstance(file_input, bytes):
            size = len(file_input)
        else:
            size = len(file_input)
        return size / (1024 * 1024)
    except Exception:
        return 0.0


def ensure_directory(path: Path) -> None:
    """
    Klasörün var olduğundan emin olur, yoksa oluşturur.

    Args:
        path: Oluşturulacak klasör yolu
    """
    try:
        path.mkdir(exist_ok=True, parents=True)
    except Exception as e:
        logger.error(f"Klasör oluşturma hatası: {e}")
        raise


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """
    Metni belirli uzunlukta kısaltır.

    Args:
        text: Kısaltılacak metin
        max_length: Maksimum uzunluk
        suffix: Eklenecek son ek

    Returns:
        str: Kısaltılmış metin
    """
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def is_valid_pdf(file_input: Any) -> bool:
    """
    Dosyanın geçerli bir PDF olup olmadığını kontrol eder.

    Args:
        file_input: UploadedFile veya bytes

    Returns:
        bool: Geçerli PDF ise True
    """
    try:
        # Bytes'e çevir
        if hasattr(file_input, 'getbuffer'):
            file_bytes = bytes(file_input.getbuffer())
        elif isinstance(file_input, bytes):
            file_bytes = file_input
        else:
            return False

        # PDF başlangıç işareti kontrolü (%PDF)
        return file_bytes[:4] == b'%PDF'

    except Exception as e:
        logger.error(f"PDF doğrulama hatası: {e}")
        return False