import streamlit as st
import anthropic
import base64
import io
from datetime import datetime
from PIL import Image

# Импорт библиотек для документов
from docx import Document
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

# ─── Конфигурация страницы ─────────────────────────────────────────────────────
st.set_page_config(page_title="ТехСпек Генератор 2.0", layout="wide")

# Список моделей для автоматического перебора
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

def call_claude_safe(api_key, content_blocks):
    client = anthropic.Anthropic(api_key=api_key)
    for model in MODELS_TO_TRY:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system="Ты технический писатель. Пиши на русском языке.",
                messages=[{"role": "user", "content": content_blocks}]
            )
            return response.content[0].text, model
        except anthropic.NotFoundError:
            continue
        except Exception as e:
            return None, str(e)
    return None, "Ни одна из моделей не доступна в вашем аккаунте."

# ─── Интерфейс ────────────────────────────────────────────────────────────────

st.title("⚙️ ТехСпек Генератор")

# Ключ из Secrets
api_key = st.secrets.get("ANTHROPIC_API_KEY", None)

if not api_key:
    api_key = st.sidebar.text_input("Введите Anthropic API Key", type="password")

col_input, col_output = st.columns([1, 1.5], gap="large")

with col_input:
    st.subheader("📂 Исходные данные")
    uploaded_files = st.file_uploader("Загрузите файлы", type=["pdf", "jpg", "png", "jpeg"], accept_multiple_files=True)
    equipment = st.text_input("Наименование оборудования")
    
    # Кнопка запуска
    start_analysis = st.button("🚀 Начать анализ", use_container_width=True)

with col_output:
    if start_analysis:
        if not api_key:
            st.error("Ключ API не найден!")
        elif not uploaded_files:
            st.warning("Загрузите хотя бы один файл.")
        else:
            try:
                with st.spinner("Claude анализирует данные..."):
                    blocks = []
                    for f in uploaded_files:
                        f_bytes = f.getvalue()
                        if f.name.lower().endswith(('.jpg', '.jpeg', '.png')):
                            encoded = base64.b64encode(f_bytes).decode('utf-8')
                            blocks.append({
                                "type": "image",
                                "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded}
                            })
                    
                    blocks.append({
                        "type": "text", 
                        "text": f"Составь подробную спецификацию для: {equipment}. На русском языке."
                    })
                    
                    result_text, used_model = call_claude_safe(api_key, blocks)
                    
                    if result_text:
                        st.success(f"Использована модель: {used_model}")
                        st.markdown(result_text)
                        
                        st.divider()
                        st.download_button("⬇️ Скачать Word", get_docx_file(result_text, equipment), f"{equipment}.docx")
                        st.download_button("⬇️ Скачать PDF", get_pdf_file(result_text, equipment), f"{equipment}.pdf")
                    else:
                        st.error(used_model)
            except Exception as e:
                st.error(f"Сбой: {e}")
