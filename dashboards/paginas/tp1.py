"""Apartado del TP1 (exploración del inventario): un resumen en una pantalla.
Pregunta: ¿dónde está el cuello de botella de la red? Las tres columnas son las tres conclusiones de la presentación."""
import plotly.graph_objects as go
import streamlit as st

from comun import PALETAS, c, csv, encabezado, estilo, grafico, kpi, layout, metricas_json, nota, pregunta

P = PALETAS["TP1"]
estilo(P)

M = metricas_json()
O1, O2, O6 = M["obj01"], M["obj02"], M["obj06"]
# solo resúmenes (src/serializar_modelos.py): equipos por modelo y por localidad, sin el inventario equipo por equipo
TOP = csv("data/app/tp1_modelos.csv").set_index("Modelo_canonico")["equipos"].sort_values(ascending=False)
LOCS = csv("data/app/tp1_localidades.csv").set_index("Localidad")
TOTAL = int(TOP.sum())
WIFI4 = O2["total"]["Wi-Fi 4"]["equipos"]
MODERNO = O2["equipos_wifi_moderno"]
CON_FE = O1["equipos_con_algun_puerto_fe"]
EG = int(TOP["EG8141A5"])
HOY, META = MODERNO / TOTAL * 100, (MODERNO + EG) / TOTAL * 100   # reemplazar todos los EG8141A5 por equipos Wi-Fi 5 o más
PILOTO = int(LOCS.loc["Localidad H", "eg8141a5"])
wifi4_loc = LOCS["pct_wifi4"]

st.markdown(f"""<style>
.meta-barra {{ position: relative; height: 16px; border-radius: 99px; background: {P['borde']}; margin: 10px 0 4px; }}
.meta-barra div {{ position: absolute; left: 0; top: 0; bottom: 0; border-radius: 99px; }}
.meta-ejes {{ display: flex; justify-content: space-between; font-size: .72rem; color: {P['gris']}; margin-bottom: 8px; }}
</style>""", unsafe_allow_html=True)

encabezado(P, "TP1 · Exploración", "Análisis del inventario de una red GPON",
           "El primer trabajo: qué equipos tienen instalados los clientes y dónde está el límite del servicio.")
pregunta(P, "¿Dónde está el cuello de botella de la red?")

izq, centro, der = st.columns([1, 1.5, 1.15], gap="medium")
with izq:
    kpi(P, "El inventario", f"{c(TOTAL, 0)} equipos",
        f"en {len(LOCS)} localidades y {O6['tarjetas']} tarjetas de la central; todos de una sola marca (Huawei)",
        P["gris"])
    kpi(P, "Wi-Fi viejo", f"{round(WIFI4 / TOTAL * 100)} de cada 100",
        f"{c(WIFI4, 0)} equipos solo tienen Wi-Fi 4, en una sola banda (2,4 GHz)")
    kpi(P, "Cable lento", f"{round(CON_FE / TOTAL * 100)} de cada 100",
        f"{c(CON_FE, 0)} equipos tienen puertos de red de 100 Mb/s, aunque la fibra da mucho más")
    nota(P, "<b>Conclusión:</b> la red es de fibra, pero el límite está en el módem que cada cliente tiene en su casa.")

with centro:
    principales = TOP.head(7)
    otros = TOP.iloc[7:]
    nombres = list(principales.index) + [f"Otros {len(otros)} modelos"]
    valores = list(principales.values) + [int(otros.sum())]
    tres = principales.head(3).sum() / TOTAL * 100
    fig = go.Figure(go.Bar(
        x=valores[::-1], y=nombres[::-1], orientation="h",
        marker_color=[P["a1"] if i < 3 else P["gris2"] for i in range(len(valores))][::-1],
        text=[f"{c(v, 0)} ({c(v / TOTAL * 100, 1)} %)" for v in valores][::-1], textposition="outside",
        hovertemplate="%{y}: %{x} equipos<extra></extra>"))
    layout(fig, P, 450, f"Tres modelos son el {c(tres, 0)} % de los equipos")
    fig.update_xaxes(title="equipos instalados", range=[0, max(valores) * 1.38])
    grafico(fig)
    st.caption(f"En las 9 localidades, entre {c(wifi4_loc.min(), 1)} % y {c(wifi4_loc.max(), 0)} % de los equipos tiene Wi-Fi 4: "
               f"el problema no es de una zona, es de unos pocos modelos.")

with der:
    kpi(P, "La meta: equipos con Wi-Fi 5 o más", f"{c(HOY, 1)} % → {c(META, 1)} %",
        f"reemplazando los {c(EG, 0)} EG8141A5, el modelo más común, antes del 31/12/2027", P["a2"], P["a2"])
    st.markdown(f"""<div class="meta-barra"><div style="width:{META}%;background:{P['a2_suave']}"></div>
<div style="width:{HOY}%;background:{P['a2']}"></div></div>
<div class="meta-ejes"><span>hoy {c(HOY, 1)} %</span><span>meta {c(META, 1)} %</span><span>100 %</span></div>""",
                unsafe_allow_html=True)
    nota(P, f"<b>Plan de recambio</b><br>01/12/2026 · altas nuevas solo con Wi-Fi 5 o superior<br>31/03/2027 · piloto con "
            f"{PILOTO} EG8141A5 en Localidad H<br>31/12/2027 · etapa 1 completa: {c(EG, 0)} equipos", P["a2"])
    nota(P, f"<b>Lo que dejó para los siguientes:</b> el {c(M['obj03']['pct_fuera_estandar'], 1)} % de los equipos tiene el "
            f"firmware fuera de estándar (TP2) y una fuga de datos que había que evitar al predecir (TP3).")
