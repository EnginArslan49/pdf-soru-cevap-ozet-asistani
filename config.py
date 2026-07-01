# config.py
import os
import sys
from pathlib import Path

# Uygulama başlığı
APP_TITLE = "E.ARSLAN PDF Soru Cevap Asistanı"
APP_VERSION = "1.0.0"

def get_base_dir():
    """EXE veya geliştirme ortamı için temel dizini döndürür."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).parent

# Veri klasörü (çalışma dizininde oluştur)
WORKING_DIR = Path(os.getcwd())
DATA_DIR = WORKING_DIR / "data"
FAISS_INDEX_DIR = DATA_DIR / "faiss_index"

# Klasörleri oluştur
DATA_DIR.mkdir(exist_ok=True)
FAISS_INDEX_DIR.mkdir(exist_ok=True)

# Chunk parametreleri
CHUNK_SIZE = 1000          # karakter
CHUNK_OVERLAP = 200        # karakter

# Embedding modeli (ücretsiz, yerel)
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# FAISS indeks dosyaları
FAISS_INDEX_PATH = FAISS_INDEX_DIR / "pdf_index.faiss"
FAISS_METADATA_PATH = FAISS_INDEX_DIR / "metadata.pkl"

# Maksimum dosya boyutu (50 MB)
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Desteklenen uzantılar
ALLOWED_EXTENSIONS = {".pdf"}

# Özet için max chunk sayısı
SUMMARY_MAX_CHUNKS = 10

# Anahtar kelime sayısı seçenekleri
KEYWORD_OPTIONS = [10, 20, 30]

# Türkçe stop-word listesi
TR_STOP_WORDS = {
    "ve", "ile", "için", "bu", "bir", "de", "da", "ki", "ben", "sen", "o",
    "biz", "siz", "onlar", "mı", "mi", "mu", "mü", "nasıl", "neden", "ne",
    "ama", "fakat", "ancak", "çünkü", "yani", "şöyle", "böyle", "öyle",
    "kadar", "gibi", "hem", "çok", "az", "biraz", "daha", "en", "çok",
    "artık", "hala", "şimdi", "sonra", "önce", "bugün", "yarın", "dün",
    "acaba", "yoksa", "belki", "keşke", "ne", "nasıl", "niye", "nerede"
}