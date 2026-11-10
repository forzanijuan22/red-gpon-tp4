"""Piezas compartidas por los apartados del dashboard: rutas, paletas, estilo (CSS) y helpers de gráficos y tarjetas.
Cada apartado (y cada pestaña) responde una sola pregunta y entra en una pantalla, sin desplazarse.
Mismas paletas que las presentaciones: TP1 naranja y lima, TP2 ámbar y lila, TP3 jade y orquídea; lila neutro para
los apartados generales."""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

RAIZ = Path(__file__).resolve().parents[1]

PALETAS = {
    "TP1": dict(fondo="#121317", tarjeta="#1C1D23", borde="#2E3038", texto="#F2EFE8", gris="#A3A7B0", gris2="#7C808A",
                a1="#FF6B35", a2="#C8F031", a1_suave="#4A2A1E", a2_suave="#3B4419", ok="#C8F031", alerta="#F4B942",
                mal="#FF6B35", filtro="hue-rotate(106deg) saturate(3.8) brightness(1.04)"),
    "GEN": dict(fondo="#141319", tarjeta="#1F1D26", borde="#322F3B", texto="#F2EFE8", gris="#A7A4B0", gris2="#77737F",
                a1="#B9A3FF", a2="#D7CBFF", a1_suave="#3F3760", a2_suave="#2E2A3D", ok="#9BD67A", alerta="#F4B942",
                mal="#E58FB6", filtro="none"),
    "TP2": dict(fondo="#15131B", tarjeta="#211E29", borde="#34303F", texto="#F2EFE8", gris="#A7A4B0", gris2="#77737F",
                a1="#F4B942", a2="#B9A3FF", a1_suave="#5A4A22", a2_suave="#3F3760", ok="#9BD67A", alerta="#F4B942",
                mal="#E58FB6", filtro="hue-rotate(148deg) saturate(1.5) brightness(1.08)"),
    "TP3": dict(fondo="#0F1614", tarjeta="#18211E", borde="#2C3833", texto="#F0F2EE", gris="#A2ABA6", gris2="#6F7A75",
                a1="#3DDC97", a2="#E879C9", a1_suave="#1F4D3A", a2_suave="#57294C", ok="#3DDC97", alerta="#F4C95D",
                mal="#E879C9", filtro="hue-rotate(248deg) saturate(1.5) brightness(1.04)"),
}


@st.cache_data
def metricas_json():
    return json.loads((RAIZ / "results" / "metrics.json").read_text(encoding="utf-8"))


@st.cache_data
def csv(ruta):
    return pd.read_csv(RAIZ / ruta, encoding="utf-8-sig")


@st.cache_resource(show_spinner="Cargando el modelo…")
def modelo_guardado(nombre):
    """Modelo serializado con joblib por src/serializar_modelos.py: la aplicación lo usa tal cual, sin reentrenar."""
    import joblib
    return joblib.load(RAIZ / "modelos" / nombre)


def c(x, d=2):
    """Número con coma decimal y punto de miles, como en los informes."""
    if x is None or pd.isna(x):
        return "—"
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x, d=1):
    return f"{c(x * 100, d)} %"


ALTO_BASE = 620   # alto de ventana para el que están pensados los tamaños (notebook de 1366 × 768 con el navegador)

# El navegador guarda el alto y el ancho de la ventana en una cookie y recarga la página si cambiaron, así Python puede
# leerla y ajustar el alto de los gráficos para llenar la pantalla sin que haya que desplazarse.
_MEDIR_VENTANA = """<script>
const p = window.parent;
const medir = () => Math.floor(p.innerHeight / 20) * 20 + "x" + Math.floor(p.innerWidth / 40) * 40;   // para abajo
const guardado = () => (p.document.cookie.match(/(?:^|; )pantalla=([0-9x]+)/) || [])[1];
const actualizar = () => {
  const alto = medir();
  if (alto === guardado() || p.sessionStorage.getItem("alto_recargado") === alto) return;  // evita recargar en bucle
  p.document.cookie = "pantalla=" + alto + "; path=/; max-age=31536000; SameSite=Lax";
  p.sessionStorage.setItem("alto_recargado", alto);
  p.location.reload();
};
actualizar();
let espera;
p.addEventListener("resize", () => { clearTimeout(espera); espera = setTimeout(actualizar, 700); });
</script>"""


def ventana():
    """(alto, ancho) de la ventana del navegador; si todavía no se midió, una notebook de 1366 × 768."""
    try:
        alto, ancho = st.context.cookies.get("pantalla", "").split("x")
        return int(alto), int(ancho)
    except (TypeError, ValueError):
        return ALTO_BASE, 1366


def escala():
    """Cuánto agrandar los gráficos: crece con el alto de la ventana y se achica un poco si es angosta (con el panel
    lateral, los textos se parten en más renglones y ocupan más alto)."""
    alto, ancho = ventana()
    angosto = max(0, 1600 - ancho) / 2000
    return min(max(0.86 + (alto - ALTO_BASE + 28) / 430 - angosto, 0.78), 1.8)


def estilo(p):
    """CSS de toda la página: compacto y sin el encabezado de Streamlit, para que entre en una pantalla.
    El panel lateral toma los colores del apartado abierto."""
    components.html(_MEDIR_VENTANA, height=0)
    alto, _ = ventana()
    aire = .5 if alto < 700 else .75   # espacio entre bloques: un poco más en pantallas altas
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, p, li, label {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}
.stApp {{ background: radial-gradient(1100px 420px at 90% -15%, {p['a2_suave']}44, transparent 60%), {p['fondo']}; color: {p['texto']}; }}
[data-testid="stHeader"] {{ background: transparent; height: 0; }}
[data-testid="stDecoration"], [data-testid="stToolbarActions"], [data-testid="stMainMenu"],
[data-testid="stHeaderActionElements"] {{ display: none; }}
/* el botón que vuelve a abrir el menú vive en la barra de Streamlit: se deja visible, fijo arriba a la izquierda */
[data-testid="stToolbar"] {{ background: transparent; }}
[data-testid="stExpandSidebarButton"] {{ position: fixed !important; top: 10px; left: 12px; z-index: 999990; display: flex;
    align-items: center; gap: 4px; background: {p['tarjeta']} !important; border: 1.5px solid {p['a1']} !important;
    border-radius: 10px; padding: 4px 12px 4px 6px !important; }}
[data-testid="stExpandSidebarButton"] * {{ color: {p['a1']} !important; fill: {p['a1']} !important; }}
[data-testid="stExpandSidebarButton"]::after {{ content: "Menú"; color: {p['a1']}; font-size: .86rem; font-weight: 600; }}
.stApp:has([data-testid="stSidebar"][data-collapsed="true"]) .block-container {{ padding-left: 7.4rem; }}
[data-testid="stSidebar"] {{ background: {p['tarjeta']}; border-right: 1px solid {p['borde']}; }}
[data-testid="stSidebar"][data-collapsed="false"] {{ width: 250px !important; min-width: 250px !important;
                                                  max-width: 250px !important; }}   /* solo abierto: cerrado no ocupa lugar */
[data-testid="stSidebarContent"] {{ padding: 0 !important; }}
[data-testid="stSidebarUserContent"] {{ padding: .3rem .8rem 1rem; }}
[data-testid="stSidebarHeader"] {{ height: 1.6rem; padding: .4rem .8rem 0; }}
.app-marca {{ display: flex; gap: 10px; align-items: center; padding-bottom: 12px; border-bottom: 1px solid {p['borde']}; }}
.app-marca span {{ width: 30px; height: 30px; flex: none; border-radius: 50%; border: 7px solid {p['a1']}; }}
.app-marca b {{ font-family: 'Poppins', sans-serif; font-size: 1.02rem; color: {p['texto']}; display: block; line-height: 1.2; }}
.app-marca small {{ color: {p['gris']}; font-size: .72rem; line-height: 1.3; display: block; }}
.app-grupo {{ font-size: .68rem; letter-spacing: .16em; text-transform: uppercase; color: {p['gris2']}; font-weight: 600;
             margin: 14px 0 2px 4px; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a {{ border-radius: 10px; padding: 6px 10px; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a p {{ color: {p['gris']}; font-size: .92rem; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a span {{ color: {p['gris']}; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{ background: {p['borde']}; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] {{ background: {p['a1']}; }}
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] p,
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] span {{ color: {p['fondo']}; font-weight: 600; }}
/* el color del tema es lila: los controles toman el color del apartado (la barra del slider, con un filtro calculado) */
[data-testid="stSlider"] [role="group"] > div > div:first-child {{ filter: {p['filtro']}; }}
[data-testid="stSlider"] [data-rac][style*="position: absolute"] {{ background-color: {p['a1']} !important; }}
[data-testid="stSliderThumbValue"] p {{ color: {p['a1']} !important; }}
button[data-variant="segmented_control"][aria-checked="true"] {{ color: {p['a1']} !important; border-color: {p['a1']} !important;
                                                                 background: {p['a1']}1A !important; }}
.app-pie {{ color: {p['gris2']}; font-size: .74rem; line-height: 1.5; margin-top: 18px; padding-top: 10px;
           border-top: 1px solid {p['borde']}; }}
.block-container {{ padding: .55rem 2.2rem .3rem; max-width: none; }}
[data-testid="stVerticalBlock"] {{ gap: {aire}rem; }}
@media (max-width: 1500px) {{   /* notebook: panel y márgenes más angostos (va después para ganarle a la regla general) */
  [data-testid="stSidebar"][data-collapsed="false"] {{ width: 212px !important; min-width: 212px !important;
                                                    max-width: 212px !important; }}
  [data-testid="stSidebar"] [data-testid="stPageLink"] a p {{ font-size: .86rem; }}
  .block-container {{ padding-left: 1.2rem; padding-right: 1.2rem; }}
}}
.stElementContainer:has(iframe[height="0"]) {{ display: none; }}
h1, h2, h3, h4 {{ font-family: 'Poppins', 'Segoe UI', sans-serif !important; color: {p['texto']} !important; letter-spacing: -.01em; }}
.cab {{ display: flex; align-items: center; gap: 16px; border-bottom: 1px solid {p['borde']}; padding-bottom: 6px; margin-bottom: 2px; }}
.cab .pill {{ border: 1.5px solid {p['a1']}; color: {p['a1']}; border-radius: 99px; padding: 3px 12px; font-size: .7rem;
             font-weight: 600; letter-spacing: .16em; text-transform: uppercase; white-space: nowrap; }}
.cab h1 {{ font-size: 1.35rem !important; line-height: 1.2; margin: 0; padding: 0; }}
.cab p {{ color: {p['gris']}; font-size: .84rem; margin: 1px 0 0; }}
.cab p b {{ color: {p['a1']}; }}
.kpi, .nota {{ margin-bottom: 8px; }}
[data-testid="stCaptionContainer"] p {{ margin-bottom: 0; line-height: 1.35; }}
.kpi {{ background: {p['tarjeta']}; border: 1px solid {p['borde']}; border-radius: 16px; padding: 10px 15px 9px; position: relative;
       overflow: hidden; }}
.kpi:before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--acento); }}
.kpi .rot {{ font-size: .7rem; letter-spacing: .13em; text-transform: uppercase; color: {p['gris']}; font-weight: 600; }}
.kpi .val {{ font-family: 'Poppins', sans-serif; font-size: clamp(1.3rem, 1.8vw, 1.8rem); font-weight: 700; color: var(--color-val);
            line-height: 1.15; margin: 3px 0 1px; }}
.kpi .sub {{ font-size: .82rem; color: {p['gris']}; line-height: 1.35; }}
.nota {{ background: {p['tarjeta']}; border: 1px solid {p['borde']}; border-left: 4px solid var(--acento); border-radius: 14px;
        padding: 9px 13px; color: {p['texto']}; font-size: .84rem; line-height: 1.45; }}
.nota b {{ color: var(--acento); }}
.stTabs [data-baseweb="tab-list"] {{ gap: 3px; border-bottom: 1px solid {p['borde']}; }}
.stTabs [data-baseweb="tab"] {{ background: {p['tarjeta']}; border-radius: 12px 12px 0 0; padding: 5px 12px; color: {p['gris']};
                                font-size: .9rem; border: 1px solid {p['borde']}; border-bottom: none; }}
.stTabs [aria-selected="true"] {{ color: {p['fondo']} !important; background: {p['a1']} !important; font-weight: 600; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ background: transparent; }}
.stTabs [data-baseweb="tab-panel"] {{ padding-top: .35rem; }}
.preg {{ font-size: .95rem; color: {p['gris']}; margin-bottom: 6px; line-height: 1.45; }}
.preg b {{ font-family: 'Poppins', sans-serif; color: {p['texto']}; font-size: 1.05rem; margin-right: 8px; }}
.minis {{ display: grid; gap: 8px; margin-bottom: 10px; }}
.mini {{ background: {p['tarjeta']}; border: 1px solid {p['borde']}; border-radius: 12px; padding: 8px 11px; min-width: 0; }}
.mini .rot {{ font-size: .76rem; color: {p['gris']}; }}
.mini .val {{ font-family: 'Poppins', sans-serif; font-size: 1.35rem; font-weight: 600; color: {p['texto']}; white-space: nowrap; }}
.leyenda {{ display: flex; gap: 14px; flex-wrap: wrap; font-size: .8rem; color: {p['gris']}; margin-top: 6px; }}
.leyenda span:before {{ content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px;
                       background: var(--c); vertical-align: -1px; }}
</style>""", unsafe_allow_html=True)


def encabezado(p, etiqueta, titulo, bajada):
    """Una línea: el TP, el tema del tablero y para qué sirve."""
    st.markdown(f"""<div class="cab"><div class="pill">{etiqueta}</div>
<div><h1>{titulo}</h1><p>{bajada}</p></div></div>""", unsafe_allow_html=True)


def pregunta(p, texto):
    """La pregunta que responde la pestaña, en una línea."""
    st.markdown(f'<div class="preg"><b>{texto}</b></div>', unsafe_allow_html=True)


def mini(p, items, columnas=2):
    """Tarjetitas de cifras. items = [(rótulo, valor)]."""
    celdas = "".join(f'<div class="mini"><div class="rot">{a}</div><div class="val">{b}</div></div>' for a, b in items)
    st.markdown(f'<div class="minis" style="grid-template-columns:repeat({columnas},minmax(0,1fr))">{celdas}</div>',
                unsafe_allow_html=True)


def kpi(p, rotulo, valor, sub="", acento=None, color_valor=None):
    st.markdown(f"""<div class="kpi" style="--acento:{acento or p['a1']};--color-val:{color_valor or p['texto']}">
<div class="rot">{rotulo}</div><div class="val">{valor}</div><div class="sub">{sub}</div></div>""", unsafe_allow_html=True)


def nota(p, html, acento=None):
    st.markdown(f'<div class="nota" style="--acento:{acento or p["a1"]}">{html}</div>', unsafe_allow_html=True)


def leyenda(items):
    """items = [(texto, color)]: leyenda de semáforo en una línea."""
    st.markdown('<div class="leyenda">' + "".join(f'<span style="--c:{col}">{t}</span>' for t, col in items) + "</div>",
                unsafe_allow_html=True)


def layout(fig, p, alto=380, titulo=None, leyenda=False):
    """Estilo común de los gráficos de Plotly: fondo transparente, grilla suave, coma decimal."""
    fig.update_layout(
        height=int(alto * escala()), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", dragmode=False,
        font=dict(family="Inter, Segoe UI, sans-serif", color=p["texto"], size=13),
        margin=dict(l=10, r=10, t=(76 if leyenda else 44) if titulo else (34 if leyenda else 10), b=10), separators=",.",
        title=dict(text=titulo, font=dict(family="Poppins, Segoe UI", size=15, color=p["texto"]), x=0.01, xanchor="left",
                   y=0.98, yanchor="top", yref="container") if titulo else None,
        showlegend=leyenda, legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0, bgcolor="rgba(0,0,0,0)", title_text=""),
        hoverlabel=dict(bgcolor=p["tarjeta"], bordercolor=p["borde"], font=dict(color=p["texto"])),
    )
    fig.update_xaxes(gridcolor=p["borde"], zerolinecolor=p["borde"], linecolor=p["borde"])
    fig.update_yaxes(gridcolor=p["borde"], zerolinecolor=p["borde"], linecolor=p["borde"])
    return fig


def grafico(fig):
    """Muestra el gráfico. Los textos de las barras nunca se recortan: se dibujan fuera del área y se deja margen."""
    barras = [t for t in fig.data if t.type == "bar"]
    if barras:
        fig.update_traces(cliponaxis=False, selector=dict(type="bar"))
        if any(t.orientation == "h" and t.text is not None for t in barras):
            fig.update_layout(margin=dict(r=max(fig.layout.margin.r or 0, 70)))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "locale": "es"})


def pesas(p, filas, titulo, x_titulo, rango):
    """Gráfico de pesas: con lo que ya vio (a2) contra datos nuevos (a1). filas = [(nombre, ya_visto, nuevo)].
    La barra entre los dos puntos es lo que el modelo memorizó; la diferencia va en una columna aparte a la derecha."""
    fig = go.Figure()
    for nombre, ent, nuevo in filas:
        fig.add_trace(go.Scatter(x=[nuevo, ent], y=[nombre, nombre], mode="lines", line=dict(color=p["gris2"], width=6),
                                 showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[f[1] for f in filas], y=[f[0] for f in filas], mode="markers", name="con lo que ya vio",
                             marker=dict(size=16, color=p["a2"]), hovertemplate="%{y}<br>ya vistos: %{x:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[f[2] for f in filas], y=[f[0] for f in filas], mode="markers", name="con datos nuevos",
                             marker=dict(size=16, color=p["a1"]), hovertemplate="%{y}<br>nuevos: %{x:.2f}<extra></extra>"))
    layout(fig, p, 120 + 46 * len(filas), titulo, leyenda=True)
    for nombre, ent, nuevo in filas:
        fig.add_annotation(x=1.0, xref="paper", xanchor="left", xshift=10, y=nombre, text=f"−{c(ent - nuevo)}", showarrow=False,
                           font=dict(color=p["texto"] if ent - nuevo > 0.15 else p["gris"], size=13))
    fig.update_layout(margin=dict(r=58))
    fig.update_xaxes(title=x_titulo, range=rango)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig
