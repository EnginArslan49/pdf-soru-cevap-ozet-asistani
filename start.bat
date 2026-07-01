@echo off
title E.ARSLAN PDF Soru-Cevap Asistani
echo ========================================
echo   E.ARSLAN PDF Soru-Cevap Asistani
echo   Versiyon 1.0.0
echo ========================================
echo.
echo Uygulama baslatiliyor...
echo.

:: Sanal ortamı aktifleştir
call .\venv\Scripts\activate.bat

:: Streamlit'i python -m ile çalıştır
python -m streamlit run app.py --server.port=8501 --server.address=localhost --browser.gatherUsageStats=false --server.enableCORS=false --server.enableXsrfProtection=false

echo.
echo Uygulama kapatildi.
pause