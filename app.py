# app.py

import sys
import os

# Streamlit metadata hatasını çözmek için
try:
    import importlib.metadata
    import streamlit
    # Streamlit versiyonunu manuel ayarla
    if not hasattr(streamlit, '__version__'):
        streamlit.__version__ = '1.35.0'
except:
    pass

import time
import re
from pathlib import Path
import streamlit as st

# Config'den başlığı al
from config import APP_TITLE, APP_VERSION, MAX_FILE_SIZE_MB, CHUNK_SIZE, CHUNK_OVERLAP, KEYWORD_OPTIONS

# Sayfa ayarları
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ana başlık
st.title(f"📄 {APP_TITLE}")
st.caption(f"Versiyon {APP_VERSION} | Geliştirici: E.ARSLAN")

# EXE ortamında çalışıyorsak bilgi ver
if getattr(sys, 'frozen', False):
    st.info("🔒 Uygulama EXE olarak çalışıyor. Veriler çalışma dizininde saklanır.")

# Modülleri import et
from logger import logger
from utils import (
    validate_file_extension,
    validate_file_size,
    is_encrypted_pdf,
    save_uploaded_file,
    cleanup_temp_file,
    get_file_size_str,
    truncate_text
)
from pdf_loader import PDFLoader
from embeddings import EmbeddingEngine
from qa_engine import QAEngine
from summarizer import Summarizer
from keyword_extractor import KeywordExtractor
from search_engine import SearchEngine


# ============================================================================
# OTURUM DURUMU BAŞLATMA (Streamlit State)
# ============================================================================
def init_session_state():
    """Oturum durumunu başlatır"""
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.embedding_engine = None
        st.session_state.chunks = []
        st.session_state.pdf_loaded = False
        st.session_state.pdf_name = ""
        st.session_state.history = []
        st.session_state.summary_data = None
        st.session_state.keywords = []
        st.session_state.search_results = []
        st.session_state.indexing_in_progress = False
        st.session_state.uploaded_file = None
        st.session_state.index_success = False
        st.session_state.error_message = ""


init_session_state()


# ============================================================================
# TÜM TÜRKÇE KARAKTERLERİ LATİN'E DÖNÜŞTÜR (PDF İÇİN)
# ============================================================================
def clean_for_pdf(text: str) -> str:
    """
    Metni PDF için temizler:
    - TÜM Türkçe karakterleri Latin karşılıklarına çevirir
    - Emojileri temizler
    - Kontrol karakterlerini temizler
    - Özel karakterleri temizler
    """
    if not text:
        return ""

    # TÜM Türkçe karakter dönüşüm tablosu (büyük/küçük)
    turkish_map = {
        'ğ': 'g', 'Ğ': 'G',
        'ü': 'u', 'Ü': 'U',
        'ş': 's', 'Ş': 'S',
        'ı': 'i', 'I': 'I',
        'ö': 'o', 'Ö': 'O',
        'ç': 'c', 'Ç': 'C',
        'İ': 'I',
        'â': 'a', 'Â': 'A',
        'î': 'i', 'Î': 'I',
        'û': 'u', 'Û': 'U',
        'ô': 'o', 'Ô': 'O'
    }

    # Tüm Türkçe karakterleri dönüştür
    for turkish, latin in turkish_map.items():
        text = text.replace(turkish, latin)

    # Emojileri temizle
    text = re.sub(
        r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]',
        ' ', text)

    # Özel karakterleri temizle (sadece ASCII harf, sayı, noktalama ve boşluk bırak)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)

    # Kontrol karakterlerini temizle
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Fazla boşlukları temizle
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


# ============================================================================
# PDF RAPOR OLUŞTURMA (CÜMLELERİ KESMEZ)
# ============================================================================
def create_pdf_report(content: str, title: str, pdf_name: str, output_suffix: str) -> str:
    """PDF raporu oluşturur - Cümleleri kesmez, noktaya kadar yazar"""
    from fpdf import FPDF
    import datetime

    # Dosya adı
    pdf_name_clean = re.sub(r'[^\w\-_. ]', '_', pdf_name)
    pdf_name_clean = pdf_name_clean.replace('.pdf', '')
    output_name = f"{pdf_name_clean}_{output_suffix}.pdf"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    # Başlık
    pdf.set_font("Helvetica", size=16)
    pdf.cell(190, 10, txt=f"E.ARSLAN PDF Soru-Cevap Asistani - {title}", ln=True, align="C")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(190, 8, txt=f"PDF: {pdf_name}", ln=True, align="C")
    pdf.cell(190, 8, txt=f"Tarih: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, align="C")
    pdf.ln(8)

    # Temizle
    clean_content = clean_for_pdf(content)

    # Satırları böl ve yaz (cümleleri kesme)
    pdf.set_font("Helvetica", size=10)
    lines = clean_content.split('\n')

    for line in lines:
        if not line.strip():
            pdf.ln(4)
            continue

        # Satır çok uzunsa böl ama cümle ortasında kesme
        if len(line) > 100:
            parts = []
            current = ""
            for char in line:
                current += char
                if char in '.!?' and len(current) > 30:
                    parts.append(current.strip())
                    current = ""
            if current:
                parts.append(current.strip())

            for part in parts:
                if part:
                    pdf.multi_cell(185, 6, txt=part)
        else:
            pdf.multi_cell(185, 6, txt=line)

    # Footer
    pdf.ln(5)
    pdf.set_font("Helvetica", size=8)
    pdf.cell(190, 6, txt=f"Olusturulma Tarihi: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True,
             align="C")
    pdf.cell(190, 6, txt="(c) 2026 E.ARSLAN | E.ARSLAN PDF Soru-Cevap Asistani", ln=True, align="C")

    pdf.output(output_name)
    return output_name


# ============================================================================
# SOL PANEL - PDF YÜKLEME VE ARAÇLAR
# ============================================================================
with st.sidebar:
    st.header("📤 PDF Yükle")

    # PDF yükleme alanı
    uploaded_file = st.file_uploader(
        "PDF dosyası seçin (max 50 MB)",
        type=["pdf"],
        key="pdf_uploader",
        help="Sadece PDF formatı desteklenir. Şifreli PDF'ler açılamaz."
    )

    # Dosya yüklendiyse işle
    if uploaded_file is not None:
        # Dosya adını ve boyutunu göster
        file_size_mb = len(uploaded_file.getbuffer()) / (1024 * 1024)
        st.info(f"📎 {uploaded_file.name} ({file_size_mb:.2f} MB)")

        # Doğrulamalar
        valid = True
        error_msg = ""

        if not validate_file_extension(uploaded_file.name):
            error_msg = "❌ Desteklenmeyen dosya tipi. Lütfen PDF yükleyin."
            valid = False
        elif not validate_file_size(uploaded_file):
            error_msg = f"❌ Dosya boyutu {file_size_mb:.2f} MB, maksimum {MAX_FILE_SIZE_MB} MB."
            valid = False
        elif is_encrypted_pdf(uploaded_file):
            error_msg = "❌ Bu PDF şifreli. Lütfen şifresiz bir PDF yükleyin."
            valid = False

        if not valid:
            st.error(error_msg)
        else:
            # İndeksleme butonu
            col1, col2 = st.columns([3, 1])
            with col1:
                if st.button("📥 PDF'i İndeksle", use_container_width=True, type="primary"):
                    st.session_state.indexing_in_progress = True
                    st.session_state.uploaded_file = uploaded_file
                    st.session_state.index_success = False
                    st.session_state.error_message = ""
                    st.rerun()

            # İndeksleme işlemi (sayfa yenilendiğinde çalışır)
            if st.session_state.indexing_in_progress and st.session_state.uploaded_file is not None:
                with st.spinner("📄 PDF işleniyor..."):
                    try:
                        # Progress bar
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        # PDF yükle
                        status_text.text("📖 PDF okunuyor...")
                        progress_bar.progress(20)

                        loader = PDFLoader(
                            st.session_state.uploaded_file.getbuffer(),
                            st.session_state.uploaded_file.name
                        )

                        if loader.load():
                            progress_bar.progress(40)
                            status_text.text("✂️ Metin chunk'lara bölünüyor...")

                            chunks = loader.chunk_pages()
                            st.session_state.chunks = chunks

                            # Chunk kontrolü
                            if not chunks:
                                st.session_state.error_message = "❌ PDF'den metin çıkarılamadı. PDF resim tabanlı olabilir."
                                logger.error("Hiç chunk oluşturulamadı")
                                progress_bar.empty()
                                status_text.empty()
                                st.session_state.indexing_in_progress = False
                                st.rerun()

                            progress_bar.progress(60)
                            status_text.text("🧠 Embedding oluşturuluyor...")

                            # Embedding indeksi oluştur
                            engine = EmbeddingEngine()
                            if engine.build_index(chunks):
                                engine.save_index()
                                st.session_state.embedding_engine = engine
                                st.session_state.pdf_loaded = True
                                st.session_state.pdf_name = st.session_state.uploaded_file.name
                                st.session_state.index_success = True

                                progress_bar.progress(100)
                                status_text.text("✅ İşlem tamamlandı!")

                                # Hangi yöntemle okunduğunu göster
                                extraction_info = loader.get_extraction_info()
                                method = extraction_info.get("extraction_method", "unknown")
                                used_ocr = extraction_info.get("used_ocr", False)

                                logger.info(
                                    f"PDF indekslendi: {st.session_state.uploaded_file.name}, {len(chunks)} chunk")

                                # Başarılı mesajı göster
                                st.success(f"✅ PDF başarıyla indekslendi! {len(chunks)} chunk oluşturuldu.")
                                if used_ocr:
                                    st.info("🔍 OCR kullanıldı (resim tabanlı PDF)")
                                else:
                                    st.info(f"📖 Okuma yöntemi: {method}")
                                st.info(f"📊 Chunk: {CHUNK_SIZE} karakter, Overlap: {CHUNK_OVERLAP}")
                            else:
                                st.session_state.error_message = "❌ Embedding oluşturulamadı."
                                logger.error("Embedding oluşturulamadı")
                        else:
                            st.session_state.error_message = "❌ PDF okunamadı. Dosya bozuk olabilir."
                            logger.error(f"PDF okuma hatası: {st.session_state.uploaded_file.name}")

                        # Progress bar'ı temizle
                        progress_bar.empty()
                        status_text.empty()

                        # İndeksleme durumunu sıfırla
                        st.session_state.indexing_in_progress = False

                        # Hata varsa göster
                        if st.session_state.error_message and not st.session_state.index_success:
                            st.error(st.session_state.error_message)
                            st.info("💡 Log dosyasını kontrol edin: logs/app.log")

                        # Sayfayı yenile
                        time.sleep(1)
                        st.rerun()

                    except Exception as e:
                        logger.error(f"İndeksleme hatası: {e}")
                        st.error(f"❌ Beklenmeyen hata: {str(e)}")
                        st.session_state.indexing_in_progress = False
                        st.rerun()

    st.divider()

    # PDF durumu
    if st.session_state.pdf_loaded:
        st.success(f"✅ PDF indekslendi: {st.session_state.pdf_name}")

        # PDF istatistikleri
        if st.session_state.chunks:
            total_pages = len(set(c.get("page", 0) for c in st.session_state.chunks))
            total_chunks = len(st.session_state.chunks)
            st.caption(f"📊 {total_pages} sayfa, {total_chunks} chunk")

        if st.button("🗑️ PDF'i Temizle", use_container_width=True):
            st.session_state.pdf_loaded = False
            st.session_state.chunks = []
            st.session_state.history = []
            st.session_state.summary_data = None
            st.session_state.keywords = []
            st.session_state.search_results = []
            st.session_state.embedding_engine = None
            st.session_state.pdf_name = ""
            st.session_state.uploaded_file = None
            st.session_state.index_success = False
            logger.info("PDF temizlendi")
            st.rerun()
    else:
        st.info("📭 Henüz bir PDF indekslenmedi.")

    # ========================================================================
    # ARAÇLAR BÖLÜMÜ (PDF indekslendiğinde göster)
    # ========================================================================
    st.divider()

    if st.session_state.pdf_loaded:
        st.subheader("🛠️ Araçlar")

        # 1. Özet Oluştur
        if st.button("📝 Özet Oluştur", use_container_width=True):
            if st.session_state.chunks:
                with st.spinner("Özet oluşturuluyor..."):
                    try:
                        summarizer = Summarizer(st.session_state.embedding_engine)
                        summary_data = summarizer.summarize(st.session_state.chunks)
                        st.session_state.summary_data = summary_data
                        st.success("✅ Özet oluşturuldu!")
                        logger.info("Özet oluşturuldu")
                    except Exception as e:
                        logger.error(f"Özet hatası: {e}")
                        st.error(f"❌ Özet hatası: {e}")

        # 2. Anahtar Kelimeler
        st.markdown("---")
        st.caption("🔑 Anahtar Kelimeler")

        top_n = st.selectbox(
            "Kelime sayısı",
            KEYWORD_OPTIONS,
            index=0,
            key="kw_select",
            label_visibility="collapsed"
        )

        if st.button("🔑 Anahtar Kelimeleri Çıkar", use_container_width=True):
            if st.session_state.chunks:
                with st.spinner("Anahtar kelimeler çıkarılıyor..."):
                    try:
                        extractor = KeywordExtractor()
                        keywords = extractor.extract(st.session_state.chunks, top_n=top_n)
                        st.session_state.keywords = keywords
                        st.success(f"✅ {len(keywords)} anahtar kelime bulundu.")
                        logger.info(f"Anahtar kelimeler çıkarıldı: {len(keywords)}")
                    except Exception as e:
                        logger.error(f"Anahtar kelime hatası: {e}")
                        st.error(f"❌ Anahtar kelime hatası: {e}")

        st.divider()

        # 3. Kelime Arama
        st.subheader("🔍 Kelime Ara")
        search_query = st.text_input("Aranacak kelime:", placeholder="Örn: Python", key="search_input")
        if st.button("🔎 Ara", use_container_width=True):
            if search_query and search_query.strip():
                with st.spinner("Aranıyor..."):
                    try:
                        search_engine = SearchEngine()
                        results = search_engine.search(st.session_state.chunks, search_query.strip())
                        st.session_state.search_results = results
                        if results:
                            st.success(f"✅ {len(results)} sonuç bulundu.")
                        else:
                            st.warning("⚠️ Sonuç bulunamadı.")
                        logger.info(f"Arama: '{search_query}' -> {len(results)} sonuç")
                    except Exception as e:
                        logger.error(f"Arama hatası: {e}")
                        st.error(f"❌ Arama hatası: {e}")
            else:
                st.warning("⚠️ Lütfen bir kelime girin.")

        # ========================================================================
        # RAPOR OLUŞTUR / YAZDIR (PDF) - SADECE ÖZET VARSA GÖSTER
        # ========================================================================
        if st.session_state.summary_data:
            st.divider()
            st.subheader("📄 Rapor Oluştur")

            col_r1, col_r2, col_r3 = st.columns(3)

            with col_r1:
                if st.button("📄 Özet PDF", use_container_width=True):
                    if st.session_state.summary_data:
                        try:
                            s = st.session_state.summary_data

                            # Özet içeriğini düzenle (başlıkları temizle)
                            summary_text = s.get('summary', '')
                            summary_text = re.sub(r'\*\*', '', summary_text)
                            summary_text = re.sub(r'#', '', summary_text)

                            key_text = s.get('key_points', '')
                            key_lines = key_text.split('\n')
                            clean_key_lines = []
                            for line in key_lines:
                                if line.strip():
                                    if line.strip() and line.strip()[-1] not in '.!?':
                                        line = line.strip() + '.'
                                    clean_key_lines.append(line)
                            key_text = '\n'.join(clean_key_lines)

                            content = f"""
GENEL OZET:
{summary_text}

ONEMLI MADDELER:
{key_text}

SONUC:
{s.get('conclusion', '')}
"""
                            output_name = create_pdf_report(
                                content=content,
                                title="OZET RAPORU",
                                pdf_name=st.session_state.pdf_name,
                                output_suffix="OzetRaporu"
                            )
                            st.success(f"✅ Rapor '{output_name}' olarak kaydedildi.")
                            with open(output_name, "rb") as f:
                                st.download_button("📥 İndir", data=f, file_name=output_name, mime="application/pdf")
                        except Exception as e:
                            st.error(f"❌ PDF hatası: {str(e)}")

            with col_r2:
                if st.button("💬 Sohbet PDF", use_container_width=True):
                    if st.session_state.history:
                        try:
                            content = ""
                            for idx, item in enumerate(st.session_state.history[-15:], 1):
                                q = item.get("question", "")
                                a = item.get("short_answer", "") or item.get("answer", "")
                                content += f"""
SORU {idx}:
{q}

CEVAP:
{a}

"""
                            output_name = create_pdf_report(
                                content=content,
                                title="SOHBET RAPORU",
                                pdf_name=st.session_state.pdf_name,
                                output_suffix="SohbetRaporu"
                            )
                            st.success(f"✅ Rapor '{output_name}' olarak kaydedildi.")
                            with open(output_name, "rb") as f:
                                st.download_button("📥 İndir", data=f, file_name=output_name, mime="application/pdf")
                        except Exception as e:
                            st.error(f"❌ PDF hatası: {str(e)}")
                    else:
                        st.warning("⚠️ Henüz sohbet yok.")

            with col_r3:
                if st.button("🧾 Tam Rapor", use_container_width=True):
                    try:
                        content = ""

                        if st.session_state.summary_data:
                            s = st.session_state.summary_data
                            summary_text = re.sub(r'\*\*', '', s.get('summary', ''))
                            key_text = s.get('key_points', '')
                            content += f"""
--- OZET BOLUMU ---
{summary_text}

--- ONEMLI MADDELER ---
{key_text}

--- SONUC ---
{s.get('conclusion', '')}

"""

                        if st.session_state.history:
                            content += """
--- SOHBET GECMISI ---
"""
                            for idx, item in enumerate(st.session_state.history[-15:], 1):
                                q = item.get("question", "")
                                a = item.get("short_answer", "") or item.get("answer", "")
                                content += f"""
SORU {idx}:
{q}

CEVAP:
{a}

"""

                        output_name = create_pdf_report(
                            content=content,
                            title="TAM RAPOR",
                            pdf_name=st.session_state.pdf_name,
                            output_suffix="TamRapor"
                        )
                        st.success(f"✅ Rapor '{output_name}' olarak kaydedildi.")
                        with open(output_name, "rb") as f:
                            st.download_button("📥 İndir", data=f, file_name=output_name, mime="application/pdf")
                    except Exception as e:
                        st.error(f"❌ PDF hatası: {str(e)}")
    else:
        st.info("📭 PDF indekslendikten sonra araçlar burada görünecek.")

# ============================================================================
# ANA ALAN - SADECE PDF İNDEKSİ VARSA GÖSTER
# ============================================================================
if st.session_state.pdf_loaded:
    col1, col2 = st.columns([3, 2], gap="large")

    # ========================================================================
    # SOL SÜTUN - SORU-CEVAP
    # ========================================================================
    with col1:
        st.subheader("💬 Soru-Cevap")

        question = st.text_input(
            "PDF hakkında bir soru sorun:",
            placeholder="Örn: Bu dokümanın amacı nedir?",
            key="question_input"
        )

        col_q1, col_q2 = st.columns([3, 1])
        with col_q1:
            ask_button = st.button("🔍 Soru Sor", use_container_width=True, type="primary")
        with col_q2:
            clear_button = st.button("🗑️ Temizle", use_container_width=True)

        if clear_button:
            st.session_state.history = []
            st.rerun()

        if ask_button:
            if not st.session_state.pdf_loaded:
                st.warning("⚠️ Lütfen önce bir PDF indeksleyin.")
            elif not question or not question.strip():
                st.warning("⚠️ Lütfen bir soru girin.")
            else:
                with st.spinner("🤔 Cevap aranıyor..."):
                    try:
                        engine = st.session_state.embedding_engine
                        if engine is None:
                            st.error("❌ Embedding motoru başlatılmamış.")
                        else:
                            qa_engine = QAEngine(engine)
                            result = qa_engine.answer(question, top_k=5)

                            if result["found"]:
                                st.session_state.history.append({
                                    "question": question,
                                    "short_answer": result["short_answer"],
                                    "long_answer": result["long_answer"],
                                    "sources": result["sources"],
                                    "confidence": result.get("confidence", 0)
                                })

                                confidence = result.get("confidence", 0)
                                st.success(f"✅ Cevap bulundu! (Güven: %{confidence})")
                                st.markdown("**📝 Kısa Cevap:**")
                                st.info(result["short_answer"])

                                with st.expander("📖 Detaylı Cevabı Göster"):
                                    st.markdown(result["long_answer"])
                                    if result["sources"]:
                                        st.markdown("**📚 Kaynaklar:**")
                                        for src in result["sources"][:3]:
                                            st.markdown(
                                                f"- Sayfa {src.get('page', '?')}: {src.get('text', '')[:150]}...")

                                logger.info(f"Soru soruldu: {question[:50]}...")
                            else:
                                st.warning(result["short_answer"])

                    except Exception as e:
                        logger.error(f"Soru işleme hatası: {e}")
                        st.error(f"❌ Hata: {str(e)}")

        if st.session_state.history:
            st.subheader("📜 Sohbet Geçmişi")
            for i, item in enumerate(reversed(st.session_state.history)):
                q = item["question"]
                short_a = item.get("short_answer", "")
                long_a = item.get("long_answer", "")
                sources = item.get("sources", [])
                confidence = item.get("confidence", 0)

                with st.expander(f"💬 Soru {len(st.session_state.history) - i}: {q[:60]}... (Güven: %{confidence})"):
                    st.markdown(f"**Soru:** {q}")
                    st.markdown("**📝 Kısa Cevap:**")
                    st.info(short_a)
                    with st.expander("📖 Detaylı Cevap"):
                        st.markdown(long_a)
                        if sources:
                            st.markdown("**📚 Kaynaklar:**")
                            for src in sources[:3]:
                                st.markdown(f"- Sayfa {src.get('page', '?')}: {src.get('text', '')[:150]}...")

    # ========================================================================
    # SAĞ SÜTUN - BİLGİ PANELİ
    # ========================================================================
    with col2:
        st.subheader("📋 Bilgi Paneli")

        if st.session_state.summary_data:
            with st.expander("📝 Özet", expanded=True):
                summary = st.session_state.summary_data
                st.markdown(summary["summary"])
                st.divider()
                if summary.get("key_points") and len(summary["key_points"]) > 10:
                    st.markdown("**📌 Önemli Maddeler**")
                    st.markdown(summary["key_points"])
                    st.divider()
                st.caption(
                    f"📊 {summary.get('word_count', '0')} kelime, {summary.get('page_count', '0')} sayfa, {summary.get('chunk_count', '0')} chunk")

        if st.session_state.keywords:
            with st.expander("🔑 Anahtar Kelimeler", expanded=True):
                keywords = st.session_state.keywords
                st.caption(f"Toplam {len(keywords)} anahtar kelime bulundu:")
                cols = st.columns(4)
                for idx, keyword in enumerate(keywords):
                    with cols[idx % 4]:
                        st.markdown(f"🏷️ {keyword}")

        if st.session_state.search_results:
            with st.expander("🔍 Arama Sonuçları", expanded=True):
                results = st.session_state.search_results
                st.caption(f"{len(results)} sonuç bulundu.")
                for idx, result in enumerate(results[:10]):
                    page = result.get("page", "?")
                    snippet = result.get("snippet", result.get("text", ""))
                    match_count = result.get("match_count", 1)
                    st.markdown(f"**Sayfa {page}** (Eşleşme: {match_count})")
                    st.caption(snippet)
                    if idx < len(results) - 1:
                        st.divider()

        if st.session_state.pdf_loaded and st.session_state.chunks:
            with st.expander("📊 PDF İstatistikleri"):
                chunks = st.session_state.chunks
                total_chunks = len(chunks)
                total_pages = len(set(c.get("page", 0) for c in chunks))
                total_chars = sum(len(c.get("text", "")) for c in chunks)
                st.metric("📄 Toplam Sayfa", total_pages)
                st.metric("📦 Toplam Chunk", total_chunks)
                st.metric("🔤 Toplam Karakter", f"{total_chars:,}")
                avg_chunk = total_chars // total_chunks if total_chunks > 0 else 0
                st.metric("📏 Ort. Chunk Uzunluğu", f"{avg_chunk} karakter")

        with st.expander("ℹ️ Sistem Bilgisi"):
            st.caption(f"**Uygulama:** {APP_TITLE} v{APP_VERSION}")
            st.caption(f"**Python:** {sys.version.split()[0]}")
            st.caption(f"**Embedding Modeli:** sentence-transformers/all-MiniLM-L6-v2")
            st.caption(f"**Chunk Boyutu:** {CHUNK_SIZE} karakter")
            st.caption(f"**Chunk Overlap:** {CHUNK_OVERLAP} karakter")
            if st.session_state.embedding_engine:
                info = st.session_state.embedding_engine.get_index_info()
                st.caption(f"**Vektör Boyutu:** {info.get('dimension', 0)}")
                st.caption(f"**Vektör Sayısı:** {info.get('vector_count', 0)}")
            st.caption(f"**Log Dosyası:** logs/app.log")

else:
    st.info("📄 Lütfen önce bir PDF yükleyin ve indeksleyin.")
    st.markdown("""
    ### 🚀 Nasıl başlanır?
    1. **Sol panelden** bir PDF dosyası seçin
    2. **📥 PDF'i İndeksle** butonuna tıklayın
    3. İşlem tamamlandıktan sonra soru sorabilirsiniz

    ### 💡 Özellikler
    - 📝 **Özet Çıkarma:** PDF'in genel özetini, önemli maddelerini ve sonuç bölümünü görün
    - 🔑 **Anahtar Kelimeler:** PDF'de en sık geçen 10, 20 veya 30 kelimeyi çıkarın
    - 🔍 **Kelime Arama:** PDF içinde belirli kelimeleri arayın
    - 📜 **Sohbet Geçmişi:** Sorduğunuz soruları ve cevapları görüntüleyin
    """)

# ============================================================================
# FOOTER
# ============================================================================
st.divider()
st.caption(f"© 2026 E.ARSLAN | {APP_TITLE} v{APP_VERSION} | Tüm hakları saklıdır.")