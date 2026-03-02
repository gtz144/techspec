import streamlit as st
import anthropic
import base64
import re
import io
from datetime import datetime
from PIL import Image

# ─── Конфигурация страницы ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="ТехСпек Генератор",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Константы и настройки ─────────────────────────────────────────────────────
SUPPORTED_TYPES = ["pdf", "png", "jpg", "jpeg", "webp", "tiff", "tif", "bmp"]
MAX_PDF_PAGES   = 90
# Используем самую мощную доступную модель
MODEL_NAME      = "claude-3-5-sonnet-20241022"

DEFAULT_SYSTEM_PROMPT = """Ты — эксперт-технолог по технической документации для отдела закупа.
Твоя задача — анализировать документы на любом языке и формировать точную спецификацию на РУССКОМ языке.
Правила:
- Переводи технические термины точно; оригинальные обозначения оставляй в скобках.
- Не придумывай данные; пиши «не указано».
- Сохраняй все числовые значения и единицы измерения.
- Структуру документа строго соблюдай (разделы 1–8)."""

# ─── CSS — профессиональный интерфейс ──────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background-color: #f5f7fa !important; }
.app-header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%); border-radius: 14px; padding: 32px; margin-bottom: 24px; color: white; }
.card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.spec-result { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px; white-space: pre-wrap; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# ─── Логика API ключа ──────────────────────────────────────────────────────────
# Сначала ищем в Secrets (для Streamlit Cloud), если нет — просим ввести
api_key = st.secrets.get("ANTHROPIC_API_KEY", None)

# ─── Утилиты ───────────────────────────────────────────────────────────────────
def encode_image(file_bytes):
    return base64.b64encode(file_bytes).decode('utf-8')

def call_claude(api_key, content_blocks, system_prompt):
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": content_blocks}]
    )
    return response.content[0].text

# ─── Интерфейс ─────────────────────────────────────────────────────────────────
st.markdown('<div class="app-header"><h1>⚙️ ТехСпек Генератор</h1><p>Автоматизация документации для закупа</p></div>', unsafe_allow_html=True)

if not api_key:
    api_key = st.text_input("Введите Anthropic API Key", type="password")

col_left, col_right = st.columns([1, 1.5], gap="large")

with col_left:
    st.markdown('<div class="card"><b>📂 Загрузка</b>', unsafe_allow_html=True)
    files = st.file_uploader("Загрузите файлы (PDF/Изображения)", type=SUPPORTED_TYPES, accept_multiple_files=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="card"><b>⚙️ Параметры</b>', unsafe_allow_html=True)
    eq_type = st.text_input("Тип оборудования", placeholder="Например: Свеча зажигания")
    detail = st.select_slider("Детализация", ["Краткая", "Стандартная", "Подробная"], value="Стандартная")
    st.markdown('</div>', unsafe_allow_html=True)
    
    generate_btn = st.button("⚡ Сгенерировать спецификацию", use_container_width=True, disabled=not (files and api_key))

with col_right:
    if generate_btn:
        try:
            with st.spinner("Claude анализирует документы..."):
                content_blocks = []
                # Добавляем изображения/PDF в запрос
                for f in files:
                    file_bytes = f.getvalue()
                    if f.name.lower().endswith('.pdf'):
                        content_blocks.append({
                            "type": "document",
                            "source": {"type": "base64", "media_type": "application/pdf", "data": encode_image(file_bytes)}
                        })
                    else:
                        content_blocks.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": encode_image(file_bytes)}
                        })
                
                # Добавляем текстовый промпт
                content_blocks.append({
                    "type": "text", 
                    "text": f"Создай техническую спецификацию для: {eq_type}. Уровень детализации: {detail}."
                })
                
                result = call_claude(api_key, content_blocks, DEFAULT_SYSTEM_PROMPT)
                st.markdown(f'<div class="spec-result">{result}</div>', unsafe_allow_html=True)
                st.success("✅ Готово!")
        except Exception as e:
            st.error(f"Ошибка при вызове API: {e}")
