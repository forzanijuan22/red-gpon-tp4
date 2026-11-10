"""Apartado general: cómo hicimos los tres trabajos y qué reglas seguimos para que los resultados sean confiables."""
import plotly.graph_objects as go
import streamlit as st

from comun import PALETAS, c, encabezado, estilo, grafico, layout, metricas_json, pregunta

P = PALETAS["GEN"]
estilo(P)

M = metricas_json()
CH = {k: int(v["obtenido"]) for k, v in M["fase1_chequeos"]["detalle"].items()}
T3 = M["obj14_tp3"]["datos"]

st.markdown(f"""<style>
.pasos {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }}
.paso {{ background: {P['tarjeta']}; border: 1px solid {P['borde']}; border-radius: 14px; padding: 11px 13px; position: relative; }}
.paso .n {{ width: 26px; height: 26px; border-radius: 50%; background: {P['a1']}; color: {P['fondo']}; font-weight: 700;
           display: flex; align-items: center; justify-content: center; font-size: .85rem; margin-bottom: 6px; }}
.paso b {{ font-family: 'Poppins', sans-serif; font-size: .92rem; display: block; margin-bottom: 3px; color: {P['texto']}; }}
.paso p {{ font-size: .79rem; line-height: 1.4; color: {P['gris']}; margin: 0; }}
.paso:not(:last-child):after {{ content: "→"; position: absolute; right: -10px; top: 14px; color: {P['gris2']}; font-size: .9rem; }}
.reglas {{ background: {P['tarjeta']}; border: 1px solid {P['borde']}; border-radius: 16px; padding: 12px 16px; }}
.regla {{ display: flex; gap: 10px; padding: 7px 0; border-bottom: 1px solid {P['borde']}; }}
.regla:last-of-type {{ border-bottom: none; }}
.regla .ic {{ color: {P['a1']}; font-weight: 700; flex: none; width: 14px; }}
.regla b {{ font-size: .88rem; color: {P['texto']}; }}
.regla p {{ font-size: .8rem; line-height: 1.4; color: {P['gris']}; margin: 1px 0 0; }}
.herr {{ font-size: .76rem; color: {P['gris2']}; margin-top: 6px; letter-spacing: .04em; }}
</style>""", unsafe_allow_html=True)

encabezado(P, "Método", "Cómo lo hicimos",
           "El mismo proceso en los tres trabajos, con reglas para que los resultados sean confiables.")
pregunta(P, "¿Cómo nos aseguramos de que los resultados sean confiables?")

PASOS = [
    ("Juntar los datos", f"Inventario de {c(CH['Filas'], 0)} equipos y listado de la central ({c(CH['OLT: filas'], 0)} filas), "
                         f"cruzados por ubicación."),
    ("Limpiar y crear variables", f"{CH['Modelos (nombres originales)']} nombres de modelo → {CH['Modelos canónicos']} equipos "
                                  f"reales; firmware estándar; señal de los vecinos."),
    ("Separar para no hacer trampa", "80 % para aprender y 20 % de prueba. En el TP3, cada puerto entero va a un solo lado."),
    ("Comparar modelos", "Al menos 4 modelos contra una referencia que no aprende, ajustados con validación cruzada."),
    ("Medir y explicar", "Métricas que no engañan, qué memoriza cada modelo y qué datos pesan más."),
]
st.markdown('<div class="pasos">' + "".join(f'<div class="paso"><div class="n">{i}</div><b>{t}</b><p>{d}</p></div>'
                                           for i, (t, d) in enumerate(PASOS, 1)) + "</div>", unsafe_allow_html=True)

izq, der = st.columns([1.15, 1], gap="medium")
with izq:
    etapas = [("Listado de la central", CH["OLT: filas"]), ("Con ubicación válida", CH["OLT: con ubicación válida"]),
              ("Cruzan con el inventario", CH["OLT: que cruzan con el inventario"]), ("Online con señal medida (TP3)", T3["equipos"])]
    primero = etapas[0][1]
    fig = go.Figure(go.Funnel(y=[e for e, _ in etapas], x=[v for _, v in etapas], textinfo="text",
                              text=[f"{c(v, 0)} ({c(v / primero * 100, 0)} %)" for _, v in etapas],
                              textfont=dict(color=[P["texto"], P["texto"], P["texto"], P["fondo"]], size=14),
                              marker=dict(color=[P["gris2"], P["gris2"], P["a1_suave"], P["a1"]]),
                              connector=dict(line=dict(color=P["borde"])), hovertemplate="%{y}: %{x:,.0f}<extra></extra>"))
    layout(fig, P, 345, "De dónde salen los datos del TP3")
    fig.update_layout(margin=dict(l=10, r=10))
    grafico(fig)
    st.caption(f"El TP1 y el TP2 usan el inventario completo ({c(CH['Filas'], 0)} equipos; en el TP2, agrupados en "
               f"{CH['Puertos PON (Localidad+Slot+PON)']} puertos). Se verificaron {M['fase1_chequeos']['ok']} cifras "
               f"de control antes de empezar.")
with der:
    REGLAS = [
        ("Sin fuga de información", "Nada que contenga la respuesta entra al modelo. En el TP1 encontramos una: los 1.025 "
                                    "«Triplex» tienen TV."),
        ("Siempre contra una referencia", "Si un modelo no le gana a adivinar, no sirve."),
        ("La prueba se mira una sola vez", "Los modelos se eligen con validación cruzada, nunca mirando la prueba."),
        ("Todo reproducible", "run_all.py rehace todo desde cero; cada cifra sale de metrics.json."),
    ]
    st.markdown('<div class="reglas">' + "".join(f'<div class="regla"><span class="ic">✓</span><div><b>{t}</b><p>{d}</p></div></div>'
                                                for t, d in REGLAS) +
                '<div class="herr">Python · pandas · scikit-learn · Plotly · Streamlit</div></div>', unsafe_allow_html=True)
