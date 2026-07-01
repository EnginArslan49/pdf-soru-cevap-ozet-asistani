# logger.py
import logging
import os
import sys
from pathlib import Path


def get_base_dir():
    """EXE veya geliştirme ortamı için temel dizini döndürür."""
    if getattr(sys, 'frozen', False):
        # PyInstaller ile paketlenmiş exe
        return Path(sys._MEIPASS)
    else:
        # Normal geliştirme ortamı
        return Path(__file__).parent


def setup_logger(name: str = "pdf_assistant") -> logging.Logger:
    """
    Merkezi logger yapılandırması.
    Log seviyesi INFO, hem konsol hem dosya (logs/app.log) yazar.
    EXE ortamında logs klasörü çalışma dizininde oluşur.
    """
    # Çalışma dizininde logs klasörü oluştur (EXE için önemli)
    log_dir = Path(os.getcwd()) / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "app.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    # Dosya handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    # Konsol handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logger başlatıldı. Log dosyası: {log_file}")
    return logger


logger = setup_logger()