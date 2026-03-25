"""Entry point for Streamlit Cloud - single page dashboard."""
import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="Bodegas - Red de Cuentas Coordinadas",
    page_icon="🔍",
    layout="wide",
)

html_path = Path(__file__).parent / "data" / "exports" / "index.html"

if html_path.exists():
    html = html_path.read_text(encoding="utf-8")
    st.components.v1.html(html, height=900, scrolling=True)
else:
    st.error("No se encontró el archivo index.html. Ejecuta build_page.py primero.")
