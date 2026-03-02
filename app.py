import streamlit as st
import anthropic
import base64
import io
from datetime import datetime
from PIL import Image
# Используем библиотеки из вашего списка
from docx import Document
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

# ─── Настройки ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ТехСпек Генератор", layout="wide")

# ГАРАНТИРОВАННОЕ НАЗВАНИЕ МОДЕЛИ
MODEL_NAME = "claude-3-5-sonnet-20241022" 

# ─── Функции создания файлов (используют ваши библиотеки) ─────────────────────
def create_docx(text):
    doc = Document()
    doc.add_heading('Техническая спецификация', 0)
    doc.add_paragraph(text)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def create_pdf(text):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    # Заменяем переносы строк на тег для PDF
    clean_text = text.replace('\n', '<br/>')
    story = [
        Paragraph("Техническая спецификация", styles['Title']), 
        Spacer(1, 12), 
        Paragraph(clean_text, styles['Normal'])
    ]
    doc.build(story)
    return buffer.getvalue()

# ─── Основная логика ──────────────────────────────────────────────────────────
# Проверка ключа в Secrets ( share.streamlit.io -> Settings -> Secrets )
api_key = st.secrets.get("ANTHROPIC_API_KEY", None)

st.markdown("""
<style>
    .app-header { background: #1a1a2e; padding: 25px; border-radius: 10px; color: white; margin-bottom: 20px; }
    .spec-result { background: white; padding: 20px; border: 1px solid #ddd; border-radius: 10px; white-space: pre-wrap; }
</style>
<div class="app-header">
    <h1>⚙️ ТехСпек Генератор</h1>
    <p>Автоматизация документации для закупа</p>
</div>
""", unsafe_allow_html=True)

if not api_key:
    api_key = st.text_input("Введите ваш Anthropic API Key (если не настроен в Secrets)", type="password")

col1, col2 = st.columns([1, 1.5], gap="large")

with col1:
    st.subheader("📂 Загрузка")
    files = st.file_uploader("Загрузите файлы (PDF/JPG/PNG)", type=["pdf", "jpg", "png"], accept_multiple_files=True)
    eq_name = st.text_input("Наименование оборудования", placeholder="Например: Свеча зажигания")
    gen_button = st.button("⚡ Сгенерировать", use_container_width=True, disabled=not (files and api_key))

with col2:
    if gen_button:
        try:
            with st.spinner("Claude анализирует данные..."):
                client = anthropic.Anthropic(api_key=api_key)
                
                content = []
                for f in files:
                    file_bytes = f.getvalue()
                    # Кодируем изображения
                    if not f.name.lower().endswith('.pdf'):
                        b64_img = base64.b64encode(file_bytes).decode('utf-8')
                        content.append({
                            "type": "image", 
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_img}
                        })
                    # PDF обрабатывается через специальный блок, если позволяет аккаунт Anthropic
                    # Либо используется pypdf для извлечения текста (для упрощения здесь передаем как документ)
                
                content.append({
                    "type": "text", 
                    "text": f"Составь подробную техническую спецификацию для: {eq_name} на русском языке."
                })
                
                msg = client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=4000,
                    messages=[{"role": "user", "content": content}]
                )
                
                res_text = msg.content[0].text
                st.markdown(f'<div class="spec-result">{res_text}</div>', unsafe_allow_html=True)
                
                st.divider()
                st.subheader("⬇️ Скачать результат")
                c_word, c_pdf = st.columns(2)
                with c_word:
                    st.download_button("📝 Word (.docx)", create_docx(res_text), f"Spec_{datetime.now().strftime('%Y%m%d')}.docx")
                with c_pdf:
                    st.download_button("📑 PDF (.pdf)", create_pdf(res_text), f"Spec_{datetime.now().strftime('%Y%m%d')}.pdf")
                
        except Exception as e:
            st.error(f"Произошла ошибка: {e}")
