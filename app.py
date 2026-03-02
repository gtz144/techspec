import streamlit as st
import anthropic
import base64
import io
from datetime import datetime
from PIL import Image
# Библиотеки из вашего requirements.txt
from docx import Document
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

# ─── Настройки ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ТехСпек Генератор", layout="wide")

# ИСПРАВЛЕННОЕ НАЗВАНИЕ МОДЕЛИ (теперь ошибка 404 исчезнет)
MODEL_NAME = "claude-3-5-sonnet-latest" 

# ─── Функции создания файлов ──────────────────────────────────────────────────
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
    story = [Paragraph("Техническая спецификация", styles['Title']), Spacer(1, 12), Paragraph(text.replace('\n', '<br/>'), styles['Normal'])]
    doc.build(story)
    return buffer.getvalue()

# ─── Основная логика ──────────────────────────────────────────────────────────
api_key = st.secrets.get("ANTHROPIC_API_KEY", None)

st.markdown("""
<style>
    .app-header { background: #1a1a2e; padding: 25px; border-radius: 10px; color: white; margin-bottom: 20px; }
    .spec-result { background: white; padding: 20px; border: 1px solid #ddd; border-radius: 10px; }
</style>
<div class="app-header"><h1>⚙️ ТехСпек Генератор</h1><p>Используются библиотеки: docx, reportlab, pypdf, Pillow</p></div>
""", unsafe_allow_html=True)

if not api_key:
    api_key = st.text_input("Введите API ключ", type="password")

col1, col2 = st.columns([1, 1.5])

with col1:
    files = st.file_uploader("Загрузите документы (PDF/JPG)", type=["pdf", "jpg", "png"], accept_multiple_files=True)
    eq_name = st.text_input("Наименование оборудования")
    gen_button = st.button("⚡ Сгенерировать", use_container_width=True)

with col2:
    if gen_button and files and api_key:
        try:
            with st.spinner("Claude анализирует данные..."):
                client = anthropic.Anthropic(api_key=api_key)
                
                # Подготовка блоков контента (картинки + текст)
                content = []
                for f in files:
                    if f.name.lower().endswith(('.jpg', '.png')):
                        b64_img = base64.b64encode(f.getvalue()).decode('utf-8')
                        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_img}})
                
                content.append({"type": "text", "text": f"Составь ТТХ для: {eq_name}. Используй русский язык."})
                
                # Запрос к API
                msg = client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=4000,
                    messages=[{"role": "user", "content": content}]
                )
                
                res_text = msg.content[0].text
                st.session_state['res'] = res_text
                st.markdown(f'<div class="spec-result">{res_text}</div>', unsafe_allow_html=True)
                
                # Кнопки скачивания (используем ваши библиотеки)
                st.download_button("Скачать Word", create_docx(res_text), f"{eq_name}.docx")
                st.download_button("Скачать PDF", create_pdf(res_text), f"{eq_name}.pdf")
                
        except Exception as e:
            st.error(f"Ошибка: {e}")
