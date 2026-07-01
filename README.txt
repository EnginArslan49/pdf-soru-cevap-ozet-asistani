========================================
  E.ARSLAN PDF Soru-Cevap Asistani
  Versiyon 1.0.0
  İletişim: arslanengin3175@gmail.com
========================================

   📌 PROJENİN AMACI
Bu uygulama, kullanıcıların PDF dosyalarını yüklemesine, içeriğini analiz etmesine ve PDF hakkında sorular sormasına olanak tanır. Tüm cevaplar yalnızca yüklenen PDF içeriğine dayanır, model bilgi uydurmaz.

KURULUM (SADECE 1 KEZ):
1. Öncelikle bilgisayarınızda Python sürümünü kontrol edin. 
	Kontrol etmek için: 
	• Windows Başlat menüsüne "cmd" yazıp Komut İstemi'ni açın. 
	• Aşağıdaki komutu yazıp Enter tuşuna basın: 
		python --version 
	Eğer çalışmazsa aşağıdaki komutu deneyin: 
		py --version 

2. Sonuç aşağıdaki gibiyse kuruluma devam edin: 
		Python 3.12.x veya Python 3.13.x 
	✅ Python sürümünüz 3.12 veya üzeriyse: 

	• setup.bat dosyasına çift tıklayın. 
	• Kurulumun tamamlanmasını bekleyin (yaklaşık 5-10 dakika). 
	• Kurulum sırasında internet bağlantısı gereklidir. 

3. Python yüklü değilse veya sürümü 3.12'nin altındaysa: 
	1. İnternet tarayıcınızı açın. 
	2. https://www.python.org/downloads/ adresine gidin. 
	3. En güncel Python 3.12 veya daha yeni sürümü indirin. 
	4. İndirilen kurulum dosyasını çalıştırın. 
	5. Açılan pencerede mutlaka ✔ Add Python to PATH kutucuğunu işaretleyin. 
	6. Install Now butonuna tıklayın. 
	7. Kurulum tamamlandıktan sonra bilgisayarınızı yeniden başlatmanız önerilir. 
	8. Tekrar Komut İstemi'ni açıp aşağıdaki komutu çalıştırın: python --version veya py --version 
	9. Python sürümü 3.12 veya üzeri görünüyorsa setup.bat dosyasını çalıştırın.

KULLANIM (HER SEFERİNDE):
1. start.bat dosyasına çift tıklayın
2. Tarayıcınızda http://localhost:8501 adresi otomatik olarak açılacaktır
3. PDF dosyanızı yükleyip "PDF indeksle" butonuna basın
4. Belge hakkında soru sormaya başlayın.

   🚀 Özellikler

- PDF Yükleme:   PDF dosyalarını yükleyin ve indeksleyin
- Soru-Cevap:   PDF içeriği hakkında sorular sorun
- Özet Çıkarma:   PDF'in genel özetini, önemli maddelerini ve sonuç bölümünü görün
- Anahtar Kelimeler:   PDF'de en sık geçen kelimeleri çıkarın (10, 20, 30)
- Kelime Arama:   PDF içinde belirli kelimeleri arayın
- Sohbet Geçmişi:   Sorduğunuz soruları ve cevapları görüntüleyin

   🛠️ Kullanılan Teknolojiler

- Python 3.12+
- Streamlit   – Web arayüzü
- LangChain   – Embedding ve vektör işlemleri
- FAISS   – Hızlı benzerlik arama
- Sentence-Transformers   – Ücretsiz embedding modeli (all-MiniLM-L6-v2)
- PyPDF   – PDF okuma

SİSTEM GEREKSİNİMLERİ:
- Windows 10/11
- Python 3.12 veya üstü
- 8 GB RAM (önerilen)
- 2 GB boş disk alanı

SORUN MU YAŞIYORSUNUZ?
• logs/app.log dosyasını kontrol edin. 
• setup.bat dosyasını tekrar çalıştırın. 
• Python sürümünüzün 3.12 veya üzeri olduğundan emin olun.

© 2026 E.ARSLAN | Tüm hakları saklıdır.