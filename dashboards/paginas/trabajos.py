"""Apartado general: qué pregunta respondió cada uno de los tres trabajos, qué encontramos y cómo se conectan."""
import streamlit as st

from comun import PALETAS, c, encabezado, escala, estilo, metricas_json, pregunta

P = PALETAS["GEN"]
estilo(P)

M = metricas_json()
T2, T3, O2, O3 = M["obj09_tp2"], M["obj14_tp3"], M["obj02"], M["obj03"]
R2, E2 = T2["prueba"][T2["mejor_modelo"]], T2["criterio_smart"]["metas"]
R3 = T3["prueba"][T3["mejor_modelo"]]
(_, _), (perdidos, detectados) = T3["matrices_confusion_prueba"][T3["mejor_modelo"]]
total = sum(O2["total"][k]["equipos"] for k in O2["total"])
hoy = O2["equipos_wifi_moderno"] / total * 100
meta = (O2["equipos_wifi_moderno"] + M["obj01"]["ranking_top5"][0]["cantidad"]) / total * 100

E = escala()
F = min(max(E, 1), 1.4)   # letra: crece en pantallas altas
st.markdown(f"""<style>
.tp {{ min-height: {int(390 * E)}px; display: flex; flex-direction: column; font-size: {F}rem; }}
.tp .relleno {{ flex: 1; }}
.tp {{ background: {P['tarjeta']}; border: 1px solid {P['borde']}; border-top: 4px solid var(--c); border-radius: 16px;
      padding: 13px 16px 12px; }}
.tp .tag {{ display: inline-block; font-size: .68rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
           color: {P['fondo']}; background: var(--c); border-radius: 99px; padding: 2px 10px; }}
.tp h3 {{ font-size: {1.02 * F:.2f}rem !important; line-height: 1.3; margin: 8px 0 6px !important; padding: 0 !important; min-height: 2.6em; }}
.tp .num {{ font-family: 'Poppins', sans-serif; font-size: {2 * F:.2f}rem; font-weight: 700; color: var(--c);
           line-height: 1.1; }}
.tp .lab {{ color: {P['gris']}; font-size: {.8 * F:.2f}rem; margin-bottom: 8px; }}
.tp .meta {{ font-size: {.78 * F:.2f}rem; background: {P['fondo']}; border-radius: 8px; padding: 5px 9px; color: {P['texto']};
            margin-bottom: 8px; }}
.tp .rot {{ font-size: .66rem; letter-spacing: .14em; text-transform: uppercase; color: {P['gris2']}; font-weight: 600; }}
.tp p {{ font-size: {.86 * F:.2f}rem; line-height: 1.42; margin: 1px 0 7px; color: {P['texto']}; }}
.tp + div, [data-testid="stPageLink"] {{ margin-top: 2px; }}
.hilo {{ margin-top: 6px; display: flex; align-items: center; gap: 10px; background: {P['tarjeta']}; border: 1px solid {P['borde']};
        border-radius: 14px; padding: 10px 14px; font-size: {.84 * F:.2f}rem; line-height: 1.4; }}
.hilo b {{ color: var(--c); }}
.hilo .f {{ color: {P['gris2']}; font-size: 1.2rem; flex: none; }}
</style>""", unsafe_allow_html=True)

encabezado(P, "Proyecto integrador", "Tres trabajos sobre la misma red",
           f"Inventario de {c(total, 0)} equipos de una empresa de fibra óptica, más el listado de su central (OLT) "
           f"del 29/10/2026.")
pregunta(P, "¿Qué pregunta respondió cada trabajo y qué encontramos?")

TRABAJOS = [
    dict(color=PALETAS["TP1"]["a1"], tag="TP1 · Exploración · octubre", pagina="paginas/tp1.py",
         pregunta="¿Dónde está el límite del servicio?", num=f"{round(O2['total']['Wi-Fi 4']['pct'])} %",
         lab="de los equipos solo tiene Wi-Fi 4", meta=f"Meta: pasar de {c(hoy, 1)} % a {c(meta, 1)} % de Wi-Fi moderno a fines de 2027",
         como=f"Análisis exploratorio de {c(total, 0)} equipos: limpieza (24 nombres de modelo → 22), gráficos y un "
              f"indicador con meta SMART.",
         hallazgo="El problema está en el módem del cliente, no en la fibra ni en una zona: tres modelos son el 70 % de la red.",
         decision="Plan de recambio, empezando por el modelo más común (EG8141A5)."),
    dict(color=PALETAS["TP2"]["a1"], tag="TP2 · Regresión · noviembre", pagina="paginas/tp2.py",
         pregunta="¿Qué parte de cada puerto tiene el firmware fuera de estándar?", num=f"± {c(R2['MAE'] * 100, 0)} puntos",
         lab=f"de error por puerto ({T2['mejor_modelo']}, R² {c(R2['R2'])})",
         meta=f"Cumple la meta: R² {c(R2['R2'])} ≥ {c(E2['R2_prueba'])} y error menor que adivinar",
         como=f"{T2['datos']['pon']} puertos, 4 modelos de regresión contra adivinar el promedio; ganó {T2['mejor_modelo']}, "
              f"el que menos memoriza.",
         hallazgo="Depende de qué modelos hay en el puerto y de la localidad: es un tema administrativo, no de la fibra.",
         decision="Qué puertos actualizar primero en cada ventana de mantenimiento."),
    dict(color=PALETAS["TP3"]["a1"], tag="TP3 · Clasificación · noviembre", pagina="paginas/tp3.py",
         pregunta="¿Qué clientes quedan con la señal al límite?", num=f"{detectados} de {detectados + perdidos}",
         lab="clientes en riesgo encontrados en la prueba (regresión logística)",
         meta=f"Cumple las metas: ROC-AUC {c(R3['ROC_AUC'])} ≥ 0,68 y PR-AUC {c(R3['PR_AUC'])} ≥ 0,22",
         como=f"{c(T3['datos']['equipos'], 0)} clientes, 4 clasificadores, 2 ensambles y agrupamiento; ganó la regresión "
              f"logística.",
         hallazgo="La señal de los vecinos lo explica casi todo: el problema está en la fibra del puerto, no en el módem.",
         decision="A qué puerto conectar a cada cliente nuevo."),
]
for col, t in zip(st.columns(3, gap="medium"), TRABAJOS):
    with col:
        st.markdown(f"""<div class="tp" style="--c:{t['color']}"><span class="tag">{t['tag']}</span><h3>{t['pregunta']}</h3>
<div class="num">{t['num']}</div><div class="lab">{t['lab']}</div><div class="meta">{t['meta']}</div>
{f'<div class="rot">Cómo lo resolvimos</div><p>{t["como"]}</p>' if E >= 1.3 else ''}
<div class="relleno"></div><div class="rot">Lo que encontramos</div><p>{t['hallazgo']}</p><div class="rot">Para qué sirve</div><p>{t['decision']}</p></div>""",
                    unsafe_allow_html=True)
        st.page_link(t["pagina"], label=f"Ver el {t['tag'].split(' ·')[0]}", icon=":material/arrow_forward:")

st.markdown(f"""<div class="hilo" style="--c:{P['a1']}"><b>Cómo se conectan:</b>
<span>El TP1 mostró que el límite está en los equipos y que el {c(O3['pct_fuera_estandar'], 1)} % tiene el firmware fuera de
estándar</span><span class="f">→</span><span>el TP2 estima en qué puertos se concentra, para actualizarlos de a puerto</span>
<span class="f">→</span><span>el TP3 suma la señal de la central para anticipar qué clientes quedan al límite, sin la fuga de
datos que encontramos en el TP1.</span></div>""", unsafe_allow_html=True)
