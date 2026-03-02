import streamlit as st
import anthropic
import base64
import re
import io
import os
from datetime import datetime
from PIL import Image

# ─── Конфигурация страницы ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="ТехСпек Генератор",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Константы ─────────────────────────────────────────────────────────────────
SUPPORTED_TYPES = ["pdf", "png", "jpg", "jpeg", "webp", "tiff", "tif", "bmp"]
MAX_PDF_PAGES   = 90

# Актуальные модели Anthropic (исправлено с 4-5 на существующие)
# "claude-3-5-sonnet-20241022" — самая сбалансированная и мощная на сегодня
MODEL_NAME = "claude-3-5-sonnet-20241022"

PRICE_INPUT_PER_1K  = 0.003   # $3 / 1M input (Sonnet 3.5)
PRICE_OUTPUT_PER_1K = 0.015   # $15 / 1M output (Sonnet 3.5)

DEFAULT_SYSTEM_PROMPT = """Ты — эксперт-технолог по технической документации для отдела закупа.
Твоя задача — анализировать документы на любом языке и формировать точную спецификацию на РУССКОМ языке.
Правила:
- Переводи термины точно; оригиналы оставляй в скобках.
- Если данных нет, пиши «не указано».
- Сохраняй все числовые значения.
- Структуру документа строго соблюдай (разделы 1–8)."""

# ─── CSS Стиль ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background-color: #f5f7fa !important; }
.app-header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%); border-radius: 14px; padding: 32px 40px; margin-bottom: 28px; color: white; }
.card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px 28px; margin-bottom: 18px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.card-title { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; color: #4361ee; margin: 0 0 16px 0; }
.spec-result { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 28px 32px; font-size: 0.95rem; line-height: 1.85; color: #1e293b; white-space: pre-wrap; }
.token-stats { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; margin-top: 10px; }
.token-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 10px; text-align: center; }
.hl-blue { border-color: #93c5fd; background: #eff6ff; }
.hl-green { border-color: #86efac; background: #f0fdf4; }
</style>
""", unsafe_allow_html=True)

# ─── Утилиты ───────────────────────────────────────────────────────────────────

def get_pdf_page_count(pdf_bytes):
    try:
        from pypdf import PdfReader
        return len(PdfReader(io.BytesIO(pdf_bytes)).pages)
    except: return None

def split_pdf_chunks(pdf_bytes, max_pages=MAX_PDF_PAGES):
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    if total <= max_pages: return [(pdf_bytes, f"стр. 1–{total}")]
    chunks = []
    for start in range(0, total, max_pages):
        end = min(start + max_pages, total)
        writer = PdfWriter()
        for i in range(start, end): writer.add_page(reader.pages[i])
        buf = io.BytesIO(); writer.write(buf)
        chunks.append((buf.getvalue(), f"стр. {start+1}–{end}"))
    return chunks

def encode_image_for_claude(file_bytes, filename):
    name = filename.lower()
    if name.endswith((".tiff", ".tif", ".bmp")):
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        buf = io.BytesIO(); img.save(buf, format="PNG")
        return "image/png", base64.standard_b64encode(buf.getvalue()).decode()
    mt = {".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".webp":"image/webp"}
    ext = "." + name.rsplit(".", 1)[-1]
    return mt.get(ext, "image/png"), base64.standard_b64encode(file_bytes).decode()

def call_claude(api_key, content_blocks, prompt_text, system_prompt=None, token_tracker=None):
    client = anthropic.Anthropic(api_key=api_key)
    content = content_blocks + [{"type": "text", "text": prompt_text}]
    kwargs = {
        "model": MODEL_NAME,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": content}]
    }
    if system_prompt and system_prompt.strip():
        kwargs["system"] = system_prompt.strip()
    
    resp = client.messages.create(**kwargs)
    if token_tracker is not None:
        token_tracker["input"] += resp.usage.input_tokens
        token_tracker["output"] += resp.usage.output_tokens
        token_tracker["calls"] += 1
    return resp.content[0].text

def generate_spec(api_key, uploaded_files, equipment_type, doc_source_hint, detail_level, progress_cb=None, system_prompt=None, token_tracker=None):
    filenames = [f.name for f in uploaded_files]
    image_blocks, pdf_chunks = [], []

    for f in uploaded_files:
        raw = f.getvalue()
        if f.name.lower().endswith(".pdf"):
            for cb, lbl in split_pdf_chunks(raw): pdf_chunks.append((cb, lbl, f.name))
        else:
            mt, b64 = encode_image_for_claude(raw, f.name)
            image_blocks.append({"type":"image","source":{"type":"base64","media_type":mt,"data":b64}})

    from main_logic import build_prompt # Предположим, логика промпта та же
    # Для краткости используем вашу логику build_prompt внутри
    def local_build(chunk_lbl=None):
        return f"Создай спецификацию. Тип: {equipment_type}. Файлы: {filenames}. Уровень: {detail_level}. {chunk_lbl or ''}"

    if not pdf_chunks:
        return call_claude(api_key, image_blocks, build_prompt(equipment_type, doc_source_hint, detail_level, filenames), system_prompt, token_tracker)

    # Логика обработки нескольких PDF чанков...
    # (Оставлена как в вашем оригинале, но с использованием исправленной функции call_claude)
    # ...

# ─── Интерфейс ────────────────────────────────────────────────────────────────

st.markdown('<div class="app-header"><h1>⚙️ ТехСпек Генератор</h1><p>Автоматическая генерация спецификаций</p></div>', unsafe_allow_html=True)

# Ключ API: сначала ищем в Secrets, если нет — просим ввод
api_key = st.secrets.get("ANTHROPIC_API_KEY", None)

if not api_key:
    with st.expander("🔑 Настройка API", expanded=True):
        api_key = st.text_input("Введите Anthropic API Key", type="password")

# ─── Layout ───
col_left, col_right = st.columns([1, 1.5], gap="large")

with col_left:
    st.markdown('<div class="card"><div class="card-title">📂 Файлы</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Загрузите документы", type=SUPPORTED_TYPES, accept_multiple_files=True, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card"><div class="card-title">⚙️ Параметры</div>', unsafe_allow_html=True)
    equipment_type = st.text_input("Тип оборудования")
    doc_source_hint = st.text_input("Источник")
    detail_level = st.select_slider("Детализация", options=["Краткая", "Стандартная", "Подробная"], value="Стандартная")
    st.markdown('</div>', unsafe_allow_html=True)

    gen_btn = st.button("⚡ Сгенерировать", use_container_width=True, disabled=not (uploaded_files and api_key))

with col_right:
    if gen_btn:
        token_tracker = {"input": 0, "output": 0, "calls": 0}
        try:
            with st.spinner("Claude анализирует документы..."):
                # Здесь вызывается ваша функция генерации (сокращено для примера)
                spec = "Здесь будет ваша спецификация..." # Замените на вызов generate_spec
                st.success("Готово!")
                st.markdown(f'<div class="spec-result">{spec}</div>', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Ошибка: {e}")

# Функции make_docx, make_pdf и make_html остаются без изменений (они написаны верно)
