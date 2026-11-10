"""Dashboard único de los tres trabajos prácticos sobre la red GPON.
Un panel a la izquierda lleva a cada apartado; cada uno responde una sola pregunta y entra en una pantalla.
Correr desde la raíz del proyecto:  python dashboards/lanzar.py"""
from pathlib import Path

import streamlit as st

AQUI = Path(__file__).resolve().parent

st.set_page_config(page_icon=str(AQUI / "icono.png"), layout="wide", initial_sidebar_state="expanded")

PAGINAS = [
    st.Page(AQUI / "paginas" / "tp1.py", title="Resumen del TP1", icon=":material/travel_explore:", url_path="tp1"),
    st.Page(AQUI / "paginas" / "trabajos.py", title="Los tres trabajos", icon=":material/timeline:", url_path="trabajos"),
    st.Page(AQUI / "paginas" / "metodo.py", title="Cómo lo hicimos", icon=":material/account_tree:", url_path="como"),
    st.Page(AQUI / "paginas" / "tp2.py", title="TP2 · Regresión", icon=":material/system_update:", url_path="tp2"),
    st.Page(AQUI / "paginas" / "tp3.py", title="TP3 · Clasificación", icon=":material/signal_cellular_alt:", url_path="tp3"),
]


def _inicio():
    """La dirección raíz lleva al resumen del TP1; así cada apartado tiene su propia dirección (/tp1, /tp2, /tp3...)."""
    st.switch_page(PAGINAS[0])


INICIO = st.Page(_inicio, title="Inicio", url_path="inicio", default=True)
pagina = st.navigation([INICIO] + PAGINAS, position="hidden")   # el menú lo armamos a mano, con encabezado y separador

with st.sidebar:
    st.markdown('<div class="app-marca"><span></span><div><b>Red GPON</b><small>Aprendizaje Automático y Grandes Datos · '
                'UNRaf</small></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="app-grupo">El proyecto</div>', unsafe_allow_html=True)
    for p in PAGINAS[:3]:
        st.page_link(p)
    st.markdown('<div class="app-grupo">Los modelos</div>', unsafe_allow_html=True)
    for p in PAGINAS[3:]:
        st.page_link(p)
    st.markdown('<div class="app-pie">Forzani · Racca · Cesano<br>Noviembre de 2026</div>', unsafe_allow_html=True)

pagina.run()
