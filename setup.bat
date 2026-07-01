@echo off
echo ========================================
echo   E.ARSLAN PDF Soru-Cevap Asistani
echo   KURULUM ASISTANI
echo ========================================
echo.
echo Python kontrol ediliyor...
python --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi!
    echo Lutfen Python 3.12 veya ustunu kurun.
    echo https://www.python.org/downloads/
    pause
    exit /b
)

echo.
echo Sanal ortam olusturuluyor...
python -m venv venv

echo.
echo Bagimliliklar yukleniyor...
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ========================================
echo   KURULUM TAMAMLANDI!
echo ========================================
echo.
echo Uygulamayi baslatmak icin start.bat dosyasina cift tiklayin.
echo.
pause