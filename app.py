import streamlit as st
import anthropic
import base64
import io
import re
from datetime import datetime
from PIL import Image

# Импорт библиотек для генерации документов (из вашего requirements.txt)
from docx import Document
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

# ─── Конфигурация страницы ─────────────────────────────────────────────────────
st.set_page_config(page_title="ТехСпек Генератор 2.0", layout="wide")

# Список моделей для автоматического перебора (от новых к старым)
MODELS_TO_TRY = [
    "claude-3-5-sonnet-latest",
    "claude-3-5-sonnet-20240620",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307"
]

# ─── Функции работы с файлами ──────────────────────────────────────────────────

def get_docx_file(text, title):
    doc = Document()
    doc.add_heading(title, 0)
    doc.add_paragraph(text)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()

def get_pdf_file(text, title):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    clean_text = text.replace('\n', '<br/>')
    story = [Paragraph(title, styles['Title']), Spacer(1, 12), Paragraph(clean_text, styles['Normal'])]
    doc.build(story)
    return buffer.getvalue()

# ─── Логика взаимодействия с Claude ───────────────────────────────────────────

def call_claude_safe(api_key, content_blocks):
    """Пробует вызвать Claude, перебирая доступные модели при ошибке 404."""
    client = anthropic.Anthropic(api_key=api_key)
    last_error = ""
    
    for model in MODELS_TO_TRY:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system="Ты технический писатель. Пиши строго по существу на русском языке.",
                messages=[{"role": "user", "content": content_blocks}]
            )
            return response.content[0].text, model
        except anthropic.NotFoundError:
            last_error = f"Модель {model} не найдена."
            continue
        except Exception as e:
            return None, str(e)
            
    return None, f"Ни одна из моделей не доступна. Последняя ошибка: {last_error}"

# ─── Интерфейс ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main-header { background: #1a1a2e; color: white; padding: 2rem; border-radius: 15px; margin-bottom: 2rem; }
    .stButton>button { background: #4361ee !important; color: white !important; border-radius: 8px; }
</style>
<div class="main-header">
    <h1>⚙️ ТехСпек Генератор: Профессиональный закуп</h1>
    <p>Автоматический перевод и структурирование данных из фото и PDF</p>
</div>
""", unsafe_allow_html=True)

# Получение ключа из Secrets
api_key_secret = st.secrets.get("ANTHROPIC_API_KEY", None)

if not api_key_secret:
    api_key_input = st.sidebar.text_input("Введите Anthropic API Key", type="password")
    current_key = api_key_input
else:
    current_key = api_key_secret
    st.sidebar.success("Ключ загружен из настроек Streamlit")

col_input, col_output = st.columns([1, 1.5], gap="large")

with col_input:
    st.subheader("📂 Исходные данные")
    uploaded_files = st.file_uploader("Загрузите файлы (PDF, JPG, PNG)", type=["pdf", "jpg", "png", "jpeg"], accept_multiple_files=True)
    
    equipment = st.text_input("Что за оборудование?", placeholder="Например: Ступица для грузовика")
    
    if st.button("🚀 Начать анализ", use_container_width=True):
        if not current_key:
            st.error("Ключ API не найден!")
        elif not uploaded_files:
            st.warning("Загрузите хотя бы один файл.")
        else:
            st.
