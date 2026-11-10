"""Apartado del TP3 (clasificación, objetivo 14): clientes con la señal de la fibra en riesgo.
Cada pestaña responde una sola pregunta y entra en una pantalla, sin desplazarse. La primera es la decisión:
¿a qué puerto PON conviene conectar a un cliente nuevo para que no quede con la señal al límite? La última prueba casos
que no existen. Es un apartado del dashboard único (python dashboards/lanzar.py)
No muestra números de serie ni IPs: el dataset del objetivo 14 no los incluye."""
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.metrics import precision_recall_curve

from comun import (PALETAS, RAIZ, c, csv, modelo_guardado, encabezado, estilo, grafico, kpi, layout, leyenda, metricas_json, mini, nota, pct,
                   pesas, pregunta)

P = PALETAS["TP3"]
estilo(P)

M = metricas_json()
T = M["obj14_tp3"]
MEJOR = T["mejor_modelo"]
PR, VEC = T["prueba"][MEJOR], T["prueba"]["Regla de los vecinos"]
UMBRAL_RIESGO, MINIMO = -25, -27
# semáforo sobre el riesgo previsto, expresado como percentil entre los clientes actuales
ZONAS = [(50, "Conectar acá", P["ok"]), (80, "Revisar la fibra antes", P["alerta"]), (101, "Elegir otro puerto", P["mal"])]
MODELOS = ["Regresión Logística", "Árbol de Decisión", "KNN", "Naive Bayes", "Random Forest", "Gradient Boosting"]
NOMBRE = {"Regresión Logística": "Regresión logística", "Árbol de Decisión": "Árbol de decisión",
          "Dummy (prior)": "Siempre “sin riesgo”", "Regla de los vecinos": "Regla de los vecinos"}
VARIABLE = {"vec_rxp": "Señal de los vecinos", "Distancia_m": "Distancia", "WiFi_Tecnologia": "Wi-Fi", "onts_pon": "Clientes del puerto",
            "Localidad": "Localidad", "fw_generacion": "Generación de firmware", "fw_fuera_estandar": "Firmware fuera de estándar",
            "Puertos_LAN": "Puertos LAN", "ID": "ID en el puerto", "id_rel": "Posición en el puerto", "Modelo_canonico": "Modelo de equipo",
            "slot_n": "Tarjeta (slot)", "pon_n": "Número de PON"}

tabla = csv("reports/TP3/tabla_metricas.csv")
EN, CV, PRU = (tabla[tabla["conjunto"] == k].set_index("modelo") for k in ("entrenamiento", "validación cruzada (media)", "prueba"))
imp = csv("reports/TP3/importancia_permutacion.csv")
selk = csv("reports/TP3/clustering_seleccion_k.csv")
perfiles = {2: csv("reports/TP3/clustering_perfil_k2.csv"), 4: csv("reports/TP3/clustering_perfil_k4.csv")}


GUARDADO = modelo_guardado("tp3_regresion_logistica.joblib")   # regresión logística serializada (TP4)
ENTRADAS = GUARDADO["categoricas"] + GUARDADO["numericas"]


@st.cache_data(show_spinner="Cargando los datos…")
def datos():
    """Solo datos agregados (src/serializar_modelos.py): por puerto, por localidad, por modelo y por tramos de señal, más
    los puntajes del modelo sin ubicación ni identificador. La aplicación no tiene la señal de cada cliente."""
    rangos = json.loads((RAIZ / "data" / "app" / "tp3_rangos.json").read_text(encoding="utf-8"))
    return (csv("data/app/tp3_puertos.csv"), csv("data/app/tp3_localidades.csv").set_index("Localidad"),
            csv("data/app/tp3_equipos.csv").set_index("Modelo_canonico"), csv("data/app/tp3_histograma.csv"),
            csv("data/app/tp3_vecinos.csv"), rangos)


def zona(percentil):
    return next((texto, color) for limite, texto, color in ZONAS if percentil < limite)


puertos, locs, equipos, histo, vecinos, R = datos()
pipe = GUARDADO["pipeline"]
referencia = csv("data/app/tp3_referencia.csv")["puntaje"].to_numpy()   # puntajes de los clientes actuales, ordenados
prueba = csv("data/app/tp3_prueba.csv")
proba_prueba, y_te = prueba["puntaje"].to_numpy(), prueba["en_riesgo"].to_numpy()
localidades = sorted(locs.index)

encabezado(P, "TP3 · Clasificación", "Clientes con la señal de la fibra en riesgo",
           "Un cliente está en riesgo si le llega menos de −25 dBm. El modelo lo anticipa sin medir su propia señal.")
t_dec, t_prob, t_mod, t_umb, t_vec, t_gru, t_sim = st.tabs([
    ":material/home: A qué puerto conectar", ":material/signal_cellular_alt: El problema", ":material/leaderboard: Qué modelo",
    ":material/tune: A cuántos revisar", ":material/hub: Qué lo explica", ":material/workspaces: Grupos",
    ":material/science: Probar un caso nuevo"])

# ------------------------------------------------------------------ 1. decisión
with t_dec:
    pregunta(P, "¿A qué puerto conecto a un cliente nuevo?")
    izq, centro, der = st.columns([1, 2.25, 1.25], gap="medium")
    with izq:
        loc = st.selectbox("Localidad", localidades, index=localidades.index("Localidad E"))
        equipo = st.selectbox("Equipo a instalar", equipos.index.tolist())

        # un cliente nuevo hipotético en cada puerto de la localidad: sus vecinos ya están medidos, su propia señal todavía no
        pp = (puertos[puertos["Localidad"] == loc].rename(columns={"slot_n": "slot", "pon_n": "pon"})
              .reset_index(drop=True))
        nuevos = pd.DataFrame({
            "Localidad": loc, "Modelo_canonico": equipo, "Puertos_LAN": equipos.loc[equipo, "lan"], "WiFi_Tecnologia": equipos.loc[equipo, "wifi"],
            "slot_n": pp["slot"], "pon_n": pp["pon"], "ID": pp["id_max"] + 1, "id_rel": 1.0, "onts_pon": pp["clientes"] + 1,
            "fw_generacion": equipos.loc[equipo, "gen"], "fw_fuera_estandar": 0, "Distancia_m": pp["distancia"], "vec_rxp": pp["senal"]})
        puntaje = pipe.predict_proba(nuevos[ENTRADAS])[:, 1]
        pp["riesgo"] = np.searchsorted(referencia, puntaje) / len(referencia) * 100   # percentil entre los clientes actuales
        pp["nombre"] = [f"Slot {int(s)} · PON {int(p_)}" for s, p_ in zip(pp["slot"], pp["pon"])]
        pp = pp.sort_values("riesgo").reset_index(drop=True)

        por_defecto = int(pp["clientes"].idxmax())   # arranca en el puerto con más clientes: el caso más común
        elegido = st.selectbox("Puerto que estás evaluando", pp.index, index=por_defecto,
                               format_func=lambda i: f"{pp.loc[i, 'nombre']}  ({int(pp.loc[i, 'clientes'])} clientes)")
        sel = pp.loc[elegido]
        texto, color = zona(sel["riesgo"])
        kpi(P, "Veredicto para este puerto", texto, f"Un cliente nuevo acá sería más riesgoso que el {c(sel['riesgo'], 0)} % "
            f"de los clientes que ya tiene la red.", color, color)
    with centro:
        mostrar = pp.head(10)
        if elegido not in mostrar.index:
            mostrar = pd.concat([mostrar, pp.loc[[elegido]]])
        mostrar = mostrar.iloc[::-1]
        fig = go.Figure(go.Bar(
            x=mostrar["riesgo"], y=[f"{n_}  ({c(s, 1)} dBm)" for n_, s in zip(mostrar["nombre"], mostrar["senal"])], orientation="h",
            marker=dict(color=[zona(v)[1] for v in mostrar["riesgo"]],
                        line=dict(color=[P["texto"] if i == elegido else "rgba(0,0,0,0)" for i in mostrar.index], width=2.5)),
            text=[f"{c(v, 0)}" + ("  ◂ el que evaluás" if i == elegido else "") for v, i in zip(mostrar["riesgo"], mostrar.index)],
            textposition="outside", customdata=np.c_[mostrar["clientes"], mostrar["en_riesgo"] * 100],
            hovertemplate="%{y}<br>riesgo previsto: %{x:.0f}<br>%{customdata[0]} clientes · %{customdata[1]:.0f} % en riesgo hoy<extra></extra>"))
        layout(fig, P, 405, f"Puertos de {loc}: arriba, los más seguros")
        fig.update_xaxes(title="riesgo estimado (0 a 100)", range=[0, 128], tickvals=[0, 20, 40, 60, 80, 100])
        grafico(fig)
        st.caption("Riesgo 80 = más riesgoso que el 80 % de los clientes actuales. Entre paréntesis: la señal que hoy reciben "
                   "los clientes del puerto (más cerca de 0, mejor).")
        leyenda([(f"menos de 50: {ZONAS[0][1].lower()}", P["ok"]), (f"50 a 80: {ZONAS[1][1].lower()}", P["alerta"]),
                 (f"80 o más: {ZONAS[2][1].lower()}", P["mal"])])
    with der:
        margen = sel["senal"] - UMBRAL_RIESGO
        kpi(P, "Señal de los vecinos", f"{c(sel['senal'], 1)} dBm",
            f"lo que reciben hoy, en promedio, los clientes de este puerto: {c(abs(margen), 1)} dB "
            f"{'antes' if margen >= 0 else 'después'} del límite de riesgo (−25)", P["a2"])
        kpi(P, "En riesgo hoy en el puerto", pct(sel["en_riesgo"], 0), f"de sus {int(sel['clientes'])} clientes", P["a2"])
        nota(P, f"<b>¿Es confiable?</b> Si le mostrás un cliente en riesgo y uno sano que nunca vio, señala bien al que está en "
                f"riesgo 7 de cada 10 veces (ROC-AUC {c(PR['ROC_AUC'])}; la meta era 0,68). De cada 10 clientes en riesgo, "
                f"encuentra 6.")

# ------------------------------------------------------------------ 2. el problema
with t_prob:
    pregunta(P, "¿Cuántos clientes están al límite y dónde?")
    a, b = st.columns([1.3, 1], gap="medium")
    with a:
        fig = go.Figure()
        for nombre, clase, col in (("sin riesgo", "sin riesgo", P["gris2"]), ("en riesgo (−25 a −27)", "en riesgo", P["alerta"]),
                                   ("degradada (menos de −27)", "degradada", P["a2"])):
            h = histo[histo["clase"] == clase]   # clientes por tramo de 0,5 dB (ya agrupados)
            fig.add_trace(go.Bar(x=h["desde_dBm"] + 0.25, y=h["clientes"], width=0.5, name=nombre, marker_color=col,
                                 marker_line_color=P["fondo"], marker_line_width=1,
                                 hovertemplate="%{x:.2f} dBm: %{y} clientes<extra></extra>"))
        for x in (UMBRAL_RIESGO, MINIMO):
            fig.add_vline(x=x, line_dash="dash", line_color=P["a2"])
        layout(fig, P, 455, f"Cuánta señal le llega a cada uno de los {c(R['clientes'], 0)} clientes", leyenda=True)
        fig.update_layout(barmode="overlay")
        fig.update_xaxes(title="señal recibida (dBm) · líneas: −25 riesgo, −27 se corta",
                         autorange="reversed", range=[-10, -32])
        fig.update_yaxes(title="clientes")
        grafico(fig)
    with b:
        loc_ = locs["en_riesgo"].sort_values() * 100
        red = R["pct_en_riesgo"] * 100
        fig = go.Figure(go.Bar(x=loc_.values, y=loc_.index, orientation="h",
                               marker_color=[P["a2"] if v > red else P["gris2"] for v in loc_.values],
                               text=[f"{c(v, 1)} %" for v in loc_.values], textposition="outside"))
        layout(fig, P, 345, "% en riesgo por localidad")
        fig.update_xaxes(title=f"% en riesgo (rosa: más que la red, {c(red, 1)} %)", range=[0, loc_.max() * 1.15])
        grafico(fig)
        nota(P, f"<b>{c(R['en_riesgo'], 0)} clientes en riesgo: 1 de cada 9.</b> Como son pocos, el % de aciertos "
                f"engaña: un modelo que dijera siempre “sin riesgo” acertaría el 89 % de las veces sin encontrar a ninguno.")

# ------------------------------------------------------------------ 3. qué modelo
with t_mod:
    pregunta(P, "¿Qué modelo conviene usar?")
    a, b = st.columns([1.4, 1], gap="medium")
    with a:
        metrica = st.segmented_control("Métrica", ["PR_AUC", "ROC_AUC"], default="PR_AUC", label_visibility="collapsed",
                                       format_func={"PR_AUC": "Encontrar a los pocos en riesgo (PR-AUC)",
                                                    "ROC_AUC": "Distinguir en riesgo de sano (ROC-AUC)"}.get) or "PR_AUC"
        filas = ["Dummy (prior)"] + MODELOS + ["Regla de los vecinos"]
        fig = go.Figure()
        for conj, df_, col in (("clientes nuevos (con esto se elige)", CV, P["a2"]),
                               ("prueba final (973 clientes guardados)", PRU, P["a1"])):
            ys = [df_.loc[m, metrica] if m in df_.index else None for m in filas]
            fig.add_trace(go.Bar(name=conj, x=[NOMBRE.get(m, m).replace(" ", "<br>", 1) for m in filas], y=ys, marker_color=col,
                                 text=[c(v) if v is not None else "" for v in ys] if df_ is PRU else None, textposition="outside",
                                 hovertemplate="%{x}<br>" + conj + ": %{y:.2f}<extra></extra>"))
        meta = {"ROC_AUC": .68, "PR_AUC": .22}[metrica]
        fig.add_hline(y=meta, line_dash="dash", line_color=P["a1"], annotation_text=f"meta {c(meta)}", annotation_position="top left")
        layout(fig, P, 380, "Puntaje de cada modelo: más alto, mejor", leyenda=True)
        fig.update_layout(barmode="group", bargap=.22)
        fig.update_xaxes(tickangle=0)
        fig.update_yaxes(range=[0, .9 if metrica == "ROC_AUC" else .55])
        grafico(fig)
        if metrica == "PR_AUC":
            st.caption("PR-AUC: qué tan bien encuentra a los pocos clientes en riesgo. Al azar daría 0,11. "
                       "La regla de los vecinos no aprende nada: solo ordena por la señal de los vecinos.")
        else:
            st.caption("ROC-AUC: de 100 pares (un cliente en riesgo y uno sano), en cuántos señala bien al que está en riesgo. "
                       "Al azar daría 0,50. La regla de los vecinos no aprende nada: solo ordena por la señal de los vecinos.")
    with b:
        grafico(pesas(P, [(NOMBRE.get(m, m), EN.loc[m, "ROC_AUC"], CV.loc[m, "ROC_AUC"]) for m in
                          ["Regresión Logística", "Naive Bayes", "Árbol de Decisión", "Gradient Boosting", "Random Forest", "KNN"]],
                      "Cuánto pierde cada modelo con clientes nuevos", "ROC-AUC", [0.6, 1.03]))
        nota(P, f"<b>Cómo leerlo:</b> la barra gris es lo que el modelo se aprendió de memoria. <b>Ganó la regresión logística:</b> "
                f"la mejor encontrando clientes en riesgo que no vio ({c(CV.loc[MEJOR, 'PR_AUC'])}) y casi no memoriza. "
                f"KNN se reconoce a sí mismo (1,00) y cae con clientes nuevos.")

# ------------------------------------------------------------------ 4. a cuántos revisar
with t_umb:
    pregunta(P, "¿A cuántos clientes conviene mandar a revisar?")
    a, b, k = st.columns([1, 1, 1.2], gap="medium")
    with a:
        nota(P, "<b>Qué es el umbral:</b> el modelo le da a cada cliente un puntaje de 0 a 1. El umbral es el corte: con ese "
                "puntaje o más, se manda a revisar. <b>Si lo bajás</b>, encontrás más clientes en riesgo, pero visitás a más que "
                "estaban bien.")
        u = st.slider("Umbral (puntaje mínimo para revisar)", 0.05, 0.95, 0.50, 0.01)
        marca = proba_prueba >= u
        tp_, fp_ = int((marca & (y_te == 1)).sum()), int((marca & (y_te == 0)).sum())
        fn_, tn_ = int((~marca & (y_te == 1)).sum()), int((~marca & (y_te == 0)).sum())
        prec = tp_ / (tp_ + fp_) if tp_ + fp_ else 0
        mini(P, [("En riesgo encontrados", f"{tp_} de {tp_ + fn_}"), ("Visitas de más", c(fp_, 0)),
                 ("Mandados a revisar", f"{c(tp_ + fp_, 0)} de {c(len(y_te), 0)}"), ("Revisados en riesgo", f"{c(prec * 100, 0)} %")])
        st.caption("“Visitas de más”: se revisan y estaban bien. El corte conveniente depende de cuánto cuesta un reclamo "
                   "frente a una visita técnica.")
    with b:
        etiquetas = [[f"<b>{tn_}</b><br>sin revisar", f"<b>{fp_}</b><br>visitas<br>de más"],
                     [f"<b>{fn_}</b><br>se escapan", f"<b>{tp_}</b><br>encontrados"]]
        fig = go.Figure(go.Heatmap(z=[[0, 1], [2, 3]], x=["no se revisa", "se revisa"], y=["estaba bien", "en riesgo"],
                                   text=etiquetas, texttemplate="%{text}", textfont=dict(size=13),
                                   colorscale=[[0, P["tarjeta"]], [.33, P["borde"]], [.66, P["a2_suave"]], [1, P["a1_suave"]]],
                                   showscale=False, hoverinfo="skip"))
        layout(fig, P, 430, f"Los {c(len(y_te), 0)} clientes de prueba")
        fig.update_yaxes(autorange="reversed")
        grafico(fig)
    with k:
        prc, rcl, thr = precision_recall_curve(y_te, proba_prueba)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=thr, y=rcl[:-1] * 100, name="% de los en riesgo que encontrás", line=dict(color=P["a1"], width=3)))
        fig.add_trace(go.Scatter(x=thr, y=prc[:-1] * 100, name="% de los revisados que estaban en riesgo",
                                 line=dict(color=P["a2"], width=3)))
        fig.add_vline(x=u, line_color=P["texto"], line_dash="dot")
        layout(fig, P, 430, "Más bajo: encontrás más, revisás de más", leyenda=True)
        fig.update_xaxes(title="umbral (la línea punteada es el que elegiste)", range=[0.05, 0.95])
        fig.update_yaxes(range=[0, 102], ticksuffix=" %")
        grafico(fig)

# ------------------------------------------------------------------ 5. por qué los vecinos
with t_vec:
    pregunta(P, "¿De qué depende que un cliente quede en riesgo?")
    a, b, k = st.columns([1.05, 1.05, 0.9], gap="medium")
    with a:
        im = imp.iloc[::-1]
        fig = go.Figure(go.Bar(x=im["caida_PR_AUC_media"], y=[VARIABLE.get(v, v) for v in im["variable"]], orientation="h",
                               marker_color=[P["a1"] if v == "vec_rxp" else P["gris2"] for v in im["variable"]],
                               text=[c(x, 3) if x > 0.01 else "" for x in im["caida_PR_AUC_media"]], textposition="outside"))
        layout(fig, P, 430, "Si le escondemos cada dato")
        fig.update_xaxes(title="cuánto empeora el modelo", range=[-0.02, 0.32])
        grafico(fig)
        st.caption("Barra más larga = dato más importante. “Señal de los vecinos”: la señal promedio que reciben los otros "
                   "clientes del mismo puerto.")
    with b:
        tramos = vecinos[vecinos["clientes"] >= 20]   # tramos de 1 dB con suficientes clientes
        red = R["pct_en_riesgo"] * 100
        fig = go.Figure(go.Bar(
            x=tramos["vecinos_desde_dBm"] + 0.5, y=tramos["pct_en_riesgo"] * 100, width=0.85,
            marker_color=[P["a2"] if v * 100 > red else P["gris2"] for v in tramos["pct_en_riesgo"]],
            customdata=tramos["clientes"], hovertemplate="vecinos con %{x:.1f} dBm: %{y:.0f} % en riesgo "
                                                         "(%{customdata} clientes)<extra></extra>"))
        fig.add_hline(y=red, line_dash="dash", line_color=P["a2"], annotation_text=f"toda la red: {c(red, 1)} %",
                      annotation_position="top right")
        layout(fig, P, 395, "% en riesgo según la señal de los vecinos")
        fig.update_xaxes(title="señal de los vecinos (dBm)", range=[-28, -13])
        fig.update_yaxes(title="% de clientes en riesgo", range=[0, 100], ticksuffix=" %")
        grafico(fig)
        st.caption("Cada barra junta a los clientes cuyos vecinos reciben esa señal (tramos de 1 dB). Cuanto más débil la "
                   "señal de los vecinos (a la izquierda), más clientes en riesgo.")
    with k:
        fig = go.Figure()
        for nom, col, vals in (("Modelo con 13 datos", P["a1"], [PR["ROC_AUC"], PR["PR_AUC"]]),
                               ("Solo la señal de los vecinos", P["a2"], [VEC["ROC_AUC"], VEC["PR_AUC"]])):
            fig.add_trace(go.Bar(name=nom, x=["ROC-AUC", "PR-AUC"], y=vals, marker_color=col, text=[c(v) for v in vals],
                                 textposition="outside"))
        layout(fig, P, 235, "Mirar solo a los vecinos rinde igual", leyenda=True)
        fig.update_layout(barmode="group")
        fig.update_yaxes(range=[0, .85])
        grafico(fig)
        nota(P, "<b>Qué significa:</b> los clientes de un puerto comparten la misma fibra, empalmes y divisor. Si esa fibra está "
                "mal, a todos les llega poca señal. Por eso la señal de los vecinos predice casi todo, y el módem, el firmware o la "
                "distancia casi no suman. <b>El problema está en la fibra del puerto, no en el equipo.</b>")

# ------------------------------------------------------------------ 6. grupos
with t_gru:
    pregunta(P, "¿Hay grupos de clientes con más riesgo?")
    a, b = st.columns([1, 1.25], gap="medium")
    with a:
        fig = go.Figure()
        for col_, nom, color in (("silueta", "qué tan separados quedan (silueta)", P["a1"]),
                                 ("ARI", "cuánto coinciden con “en riesgo” (ARI)", P["a2"])):
            fig.add_trace(go.Scatter(x=selk["k"], y=selk[col_], mode="lines+markers", name=nom, line=dict(color=color, width=3),
                                     marker=dict(size=10)))
        layout(fig, P, 330, "¿Cuántos grupos armar? (probamos de 2 a 8)", leyenda=True)
        fig.update_xaxes(title="cantidad de grupos", dtick=1)
        fig.update_yaxes(range=[0, .3])
        grafico(fig)
        nota(P, f"<b>Qué hicimos:</b> un algoritmo (K-Means) armó grupos de clientes parecidos sin saber quién está en riesgo. "
                f"Quedan poco separados (silueta {c(selk.loc[0, 'silueta'])}, donde 1 sería perfecto), pero con 4 grupos aparece "
                f"uno que vale la pena mirar.", P["a2"])
    with b:
        k_ = st.segmented_control("Grupos", [2, 4], default=4, format_func=lambda x: f"{x} grupos", label_visibility="collapsed") or 4
        pf = perfiles[k_].sort_values("distancia_mediana_m").reset_index(drop=True)
        top = pf["pct_en_riesgo"].idxmax()
        fig = go.Figure(go.Bar(
            x=pf["pct_en_riesgo"] * 100, y=[f"{c(n_, 0)} clientes · {c(km / 1000, 1)} km" for n_, km in zip(pf["equipos"], pf["distancia_mediana_m"])],
            orientation="h", marker_color=[P["a2"] if i == top else P["gris2"] for i in pf.index],
            text=[f"{c(v * 100, 1)} %" for v in pf["pct_en_riesgo"]], textposition="outside",
            customdata=pf[["localidad_principal"]], hovertemplate="%{y}<br>%{x:.1f} % en riesgo<br>sobre todo %{customdata[0]}<extra></extra>"))
        layout(fig, P, 330, "% en riesgo de cada grupo (de más cerca a más lejos de la central)")
        fig.update_xaxes(title=f"% en riesgo (toda la red: {c(R['pct_en_riesgo'] * 100, 1)} %)", range=[0, 32])
        fig.update_yaxes(autorange="reversed")
        grafico(fig)
        g = pf.loc[top]
        nota(P, f"<b>{c(g['equipos'], 0)} clientes a {c(g['distancia_mediana_m'] / 1000, 1)} km</b> de la central tienen "
                f"{c(g['pct_en_riesgo'] * 100, 1)} % en riesgo, casi el triple que el resto. El "
                f"{c(g['pct_localidad_principal'] * 100, 0)} % está en {g['localidad_principal']}: por ahí conviene empezar.")

# ------------------------------------------------------------------ 7. probar un caso nuevo
with t_sim:
    pregunta(P, "¿Qué diría el modelo de un cliente que no existe?")
    a, b, k = st.columns([1, 1.35, 1.1], gap="medium")
    with a:
        loc_n = st.selectbox("Localidad", localidades, index=localidades.index("Localidad E"), key="loc_nuevo")
        equipos_n = equipos
        equipo_n = st.selectbox("Equipo a instalar", equipos_n.index.tolist(), key="equipo_nuevo")
        vecinos_n = st.slider("Clientes que ya hay en el puerto", 1, 100, 23)
        senal_n = st.slider("Señal de los vecinos (dBm)", -32.0, -10.0, -20.5, 0.5,
                            help="La señal promedio que reciben hoy los otros clientes del puerto. Más cerca de 0, mejor.")
        dist_n = st.slider("Distancia de fibra hasta la central (km)", 0.1, 30.0, 1.5, 0.1)
    lugar = locs.loc[loc_n]
    slot_n, pon_n = int(lugar["slot_moda"]), int(lugar["pon_moda"])   # casi no influyen: los más comunes de la localidad

    def caso(senal):
        return pd.DataFrame({
            "Localidad": loc_n, "Modelo_canonico": equipo_n, "Puertos_LAN": equipos_n.loc[equipo_n, "lan"],
            "WiFi_Tecnologia": equipos_n.loc[equipo_n, "wifi"], "slot_n": slot_n, "pon_n": pon_n, "ID": vecinos_n, "id_rel": 1.0,
            "onts_pon": vecinos_n + 1, "fw_generacion": equipos_n.loc[equipo_n, "gen"], "fw_fuera_estandar": 0,
            "Distancia_m": dist_n * 1000, "vec_rxp": senal})[ENTRADAS]

    puntaje_n = float(pipe.predict_proba(caso([senal_n]))[0, 1])
    riesgo_n = np.searchsorted(referencia, puntaje_n) / len(referencia) * 100
    with b:
        grilla = np.arange(-32, -9.5, 0.5)
        curva = np.searchsorted(referencia, pipe.predict_proba(caso(grilla))[:, 1]) / len(referencia) * 100
        fig = go.Figure()
        for (desde, hasta), (_, _, col) in zip(((0, 50), (50, 80), (80, 100)), ZONAS):
            fig.add_hrect(y0=desde, y1=hasta, fillcolor=col, opacity=.12, line_width=0)
        fig.add_trace(go.Scatter(x=grilla, y=curva, mode="lines", line=dict(color=P["texto"], width=3),
                                 hovertemplate="vecinos con %{x} dBm → riesgo %{y:.0f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=[senal_n], y=[riesgo_n], mode="markers", marker=dict(size=16, color=zona(riesgo_n)[1],
                                 line=dict(color=P["texto"], width=2)), hoverinfo="skip"))
        layout(fig, P, 450, "El riesgo según la señal de los vecinos")
        fig.update_xaxes(title="señal de los vecinos (dBm) · a la derecha, más débil", autorange="reversed")
        fig.update_yaxes(title="riesgo estimado (0 a 100)", range=[0, 101])
        grafico(fig)
    with k:
        texto_n, color_n = zona(riesgo_n)
        kpi(P, "Veredicto", texto_n, f"Sería más riesgoso que el {c(riesgo_n, 0)} % de los clientes que ya tiene la red.", color_n, color_n)
        mini(P, [("Puntaje del modelo", c(puntaje_n)), ("¿Se manda a revisar? (corte 0,50)", "Sí" if puntaje_n >= .5 else "No")])
        avisos = []
        if not R["vec_min"] <= senal_n <= R["vec_max"]:
            avisos.append(f"Ningún puerto real tiene vecinos con {c(senal_n, 1)} dBm (van de {c(R['vec_min'], 1)} a "
                          f"{c(R['vec_max'], 1)}).")
        if dist_n * 1000 > R["dist_max"]:
            avisos.append(f"{c(dist_n, 1)} km es más lejos que cualquier cliente real (máximo {c(R['dist_max'] / 1000, 1)} km).")
        if vecinos_n + 1 > R["onts_pon_max"]:
            avisos.append(f"Ningún puerto real tiene {vecinos_n + 1} clientes (máximo {R['onts_pon_max']}).")
        if equipo_n not in lugar["modelos"].split("|"):
            avisos.append(f"En {loc_n} no hay ningún {equipo_n} instalado hoy.")
        if avisos:
            nota(P, "<b>Ojo, este caso es raro:</b><br>" + "<br>".join(f"• {x}" for x in avisos) +
                    "<br>El modelo igual estima, pero el resultado es menos confiable.", P["mal"])
        else:
            nota(P, "<b>Caso dentro de lo conocido:</b> todos los valores están dentro de lo que el modelo vio en la red real.", P["ok"])
        st.caption("En el gráfico, la línea es este mismo cliente con distintas señales de vecinos y el punto es el caso que "
                   "cargaste. Las franjas son el semáforo: verde conectar, amarillo revisar, rosa otro puerto.")
