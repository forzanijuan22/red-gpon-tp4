"""Apartado del TP2 (regresión, objetivo 9): firmware fuera de estándar por puerto PON.
Cada pestaña responde una sola pregunta y entra en una pantalla, sin desplazarse. La primera es la decisión:
¿qué puertos conviene actualizar en la próxima ventana de mantenimiento? La última prueba casos que no existen.
Es un apartado del dashboard único (python dashboards/lanzar.py)"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from comun import (PALETAS, c, csv, modelo_guardado, encabezado, estilo, grafico, kpi, layout, metricas_json, nota, pesas, pregunta, ventana)

P = PALETAS["TP2"]
estilo(P)

M = metricas_json()
T, O3 = M["obj09_tp2"], M["obj03"]
MEJOR = T["mejor_modelo"]
PR = T["prueba"][MEJOR]
METAS = T["criterio_smart"]["metas"]
NUEVOS = O3["advertencia_fuera_vs_desactualizado"]["fuera_estandar_con_generacion_mayor"]
ERROR = PR["MAE"] * 100   # error medio por puerto, en puntos porcentuales
MODELOS = ["Dummy (promedio)", "Regresión Lineal", "Ridge", "Random Forest", "Gradient Boosting"]
NOMBRE = {"Dummy (promedio)": "Adivinar el promedio", "Regresión Lineal": "Regresión lineal"}
VARIABLE = {"pct_catv": "% con TV", "Localidad": "Localidad", "share_EG8141A5": "% de EG8141A5",
            "share_EG8143A5": "% de EG8143A5", "onts": "Equipos del puerto", "share_CN1001": "% de CN1001",
            "share_RDC143": "% de RDC143", "pct_moderno": "% de equipos modernos", "share_CN2002": "% de CN2002",
            "n_modelos": "Cantidad de modelos", "Slot": "Tarjeta (slot)"}

tabla = csv("reports/TP2/tabla_metricas.csv")
EN, CV, PRU = (tabla[tabla["conjunto"] == k].set_index("modelo") for k in ("entrenamiento", "validación cruzada (media)", "prueba"))
pons = csv("data/processed/pons.csv")
pred = csv("results/tp2_predicciones_prueba.csv")
imp = csv("reports/TP2/importancia_permutacion.csv")
olt = csv("reports/TP2/prueba_olt.csv")
# % previsto fuera de muestra para cada puerto (cada uno lo predijo un modelo que no lo vio), pasado a equipos
ranking = csv("results/cli_05_ranking_puertos.csv")
ranking["equipos_previstos"] = ranking["previsto"] * ranking["onts"]
ranking["equipos_reales"] = ranking["pct_fw_fuera"] * ranking["onts"]


def modelo():
    """Ridge serializado (mismos hiperparámetros y partición que el informe): pipeline y columnas de entrada en orden."""
    guardado = modelo_guardado("tp2_ridge.joblib")
    return guardado["pipeline"], guardado["columnas"]


def puerto(k):
    loc, s, p_ = k.split("|")
    return f"{loc} · S{s.rstrip('/')} · P{p_.rstrip('/')}"


encabezado(P, "TP2 · Regresión", "Firmware fuera de estándar por puerto PON",
           "El firmware se actualiza de a un puerto entero: el modelo estima qué porcentaje de cada puerto hay que actualizar.")
t_dec, t_prob, t_mod, t_err, t_exp, t_sim = st.tabs([
    ":material/checklist: Qué actualizar", ":material/bar_chart: El problema", ":material/leaderboard: Qué modelo",
    ":material/rule: Cuánto se equivoca", ":material/visibility: Qué lo explica", ":material/science: Probar un caso nuevo"])

# ------------------------------------------------------------------ 1. decisión
with t_dec:
    pregunta(P, "¿Qué puertos actualizar en la próxima ventana de mantenimiento?")
    izq, centro, der = st.columns([1, 2.25, 1.25], gap="medium")
    with izq:
        loc = st.selectbox("Localidad", ["Toda la red"] + sorted(ranking["Localidad"].unique()))
        n = st.slider("Puertos que entran en la ventana", 3, 12, 10)
        r = ranking if loc == "Toda la red" else ranking[ranking["Localidad"] == loc]
        r = r.sort_values("equipos_previstos", ascending=False).reset_index(drop=True)
        n = min(n, len(r))
        elegidos = r.head(n)
        total = r["equipos_previstos"].sum()
        kpi(P, "Se actualizarían", f"≈ {c(elegidos['equipos_previstos'].sum(), 0)} equipos", f"actualizando {n} puertos de {len(r)}")
        kpi(P, "Parte del total", f"{c(elegidos['equipos_previstos'].sum() / total * 100, 0)} %",
            f"de todos los equipos fuera de estándar de {'la red' if loc == 'Toda la red' else loc}", P["a2"])
        st.download_button("Descargar estos puertos (CSV)",
                           elegidos.assign(Puerto=elegidos["pon_key"].map(puerto))[["Puerto", "Localidad", "onts", "previsto", "equipos_previstos"]]
                           .rename(columns={"onts": "equipos", "previsto": "pct_previsto"}).to_csv(index=False).encode("utf-8-sig"),
                           "puertos_a_actualizar.csv", "text/csv", icon=":material/download:", width="stretch")
    with centro:
        top = elegidos.iloc[::-1]
        fig = go.Figure(go.Bar(
            x=top["equipos_previstos"], y=[puerto(k) for k in top["pon_key"]], orientation="h", marker_color=P["a1"],
            text=[f"{c(e, 0)} equipos ({c(p_ * 100, 0)} %{'' if ventana()[1] < 1500 else ' del puerto'})"
                  for e, p_ in zip(top["equipos_previstos"], top["previsto"])],
            textposition="outside", customdata=np.c_[top["onts"], top["equipos_reales"]],
            hovertemplate="%{y}<br>%{customdata[0]} equipos en el puerto<br>el modelo estima %{x:.0f} para actualizar"
                          "<br>en el inventario hay %{customdata[1]:.0f}<extra></extra>"))
        layout(fig, P, 455, f"Los {n} puertos donde más equipos se arreglan de una vez")
        fig.update_xaxes(title="equipos a actualizar en el puerto, según el modelo", range=[0, top["equipos_previstos"].max() * 1.55])
        grafico(fig)
    with der:
        curva = r["equipos_previstos"].cumsum() / total * 100
        hasta = min(len(r), 60)
        fig = go.Figure(go.Scatter(x=np.arange(1, len(r) + 1), y=curva, mode="lines", line=dict(color=P["a2"], width=3),
                                   hovertemplate="%{x} puertos → %{y:.0f} % del total<extra></extra>"))
        fig.add_trace(go.Scatter(x=[n], y=[curva.iloc[n - 1]], mode="markers", marker=dict(size=13, color=P["a1"]), hoverinfo="skip"))
        fig.add_annotation(x=n, y=curva.iloc[n - 1], text=f"{n} puertos: {c(curva.iloc[n - 1], 0)} %", showarrow=False, xanchor="left",
                           xshift=10, yshift=-12, font=dict(color=P["a1"], size=13))
        layout(fig, P, 215, "¿Cuánto del total se arregla?")
        fig.update_xaxes(title=f"puertos actualizados (los primeros {hasta})", range=[0, hasta + 1])
        fig.update_yaxes(title="% del total", range=[0, curva.iloc[hasta - 1] * 1.08], ticksuffix=" %")
        grafico(fig)
        nota(P, f"<b>¿Es confiable?</b> En promedio se equivoca por {c(ERROR, 0)} puntos: si dice 30 %, lo real suele estar entre "
                f"{c(30 - ERROR, 0)} y {c(30 + ERROR, 0)} %. Lo comprobamos con puertos que el modelo no había visto.")
        nota(P, f"<b>Antes de actualizar:</b> {c(NUEVOS, 0)} de los {c(O3['equipos_fuera_estandar'], 0)} equipos “fuera de "
                f"estándar” tienen una versión <i>más nueva</i>. La empresa tiene que confirmar cuál es la correcta.", P["a2"])

# ------------------------------------------------------------------ 2. el problema
with t_prob:
    pregunta(P, "¿Cuánto cambia el problema de un puerto a otro?")
    a, b = st.columns([1.25, 1], gap="medium")
    with a:
        pct_puerto = pons["pct_fw_fuera"] * 100
        med = pct_puerto.median()
        fig = go.Figure(go.Histogram(x=pct_puerto, xbins=dict(start=0, end=100.01, size=5), marker_color=P["a1"],
                                     marker_line_color=P["fondo"], marker_line_width=1.5,
                                     hovertemplate="%{x} %<br>%{y} puertos<extra></extra>"))
        fig.add_vline(x=med, line_dash="dash", line_color=P["a2"])
        layout(fig, P, 450, f"Cuántos puertos hay con cada % · la línea marca la mitad ({c(med, 0)} %)")
        fig.update_xaxes(title="% de equipos del puerto con firmware fuera de estándar")
        fig.update_yaxes(title="cantidad de puertos")
        grafico(fig)
    with b:
        loc_ = (pons.groupby("Localidad").apply(lambda g: np.average(g["pct_fw_fuera"], weights=g["onts"]) * 100, include_groups=False)
                .sort_values())
        prom = O3["equipos_fuera_estandar"] / pons["onts"].sum() * 100
        fig = go.Figure(go.Bar(x=loc_.values, y=loc_.index, orientation="h",
                               marker_color=[P["a1"] if v > prom else P["gris2"] for v in loc_.values],
                               text=[f"{c(v, 1)} %" for v in loc_.values], textposition="outside"))
        layout(fig, P, 345, "% de equipos fuera de estándar en cada localidad")
        fig.update_xaxes(title=f"ámbar: por encima del total de la red ({c(prom, 1)} %)", range=[0, 100])
        grafico(fig)
        nota(P, f"Hay de todo: <b>{T['datos']['pon_con_0_pct']} puertos con 0 %</b> y {T['datos']['pon_con_100_pct']} con 100 %. "
                f"En Localidad A casi todo está fuera de estándar; en Localidad C, poco. Por eso tiene sentido estimarlo puerto por puerto.")

# ------------------------------------------------------------------ 3. qué modelo
with t_mod:
    pregunta(P, "¿Qué modelo conviene usar?")
    a, b = st.columns([1.35, 1], gap="medium")
    with a:
        fig = go.Figure()
        for conj, df_, col in (("puertos que ya vio", EN, P["gris2"]), ("puertos nuevos (con esto se elige)", CV, P["a2"]),
                               ("prueba final (61 puertos guardados)", PRU, P["a1"])):
            fig.add_trace(go.Bar(name=conj, x=[NOMBRE.get(m, m).replace(" ", "<br>", 1) for m in MODELOS],
                                 y=[df_.loc[m, "R2"] for m in MODELOS], marker_color=col,
                                 text=[c(df_.loc[m, "R2"]) for m in MODELOS] if df_ is CV else None, textposition="outside",
                                 hovertemplate="%{x}<br>" + conj + ": %{y:.2f}<extra></extra>"))
        fig.add_hline(y=METAS["R2_prueba"], line_dash="dash", line_color=P["a1"], annotation_text="meta 0,45",
                      annotation_position="top left")
        layout(fig, P, 430, "R² de cada modelo (0 = no explica nada, 1 = todo)", leyenda=True)
        fig.update_layout(barmode="group", bargap=.25)
        fig.update_xaxes(tickangle=0)
        fig.update_yaxes(range=[-0.05, 0.85])
        grafico(fig)
        st.caption("“Puertos nuevos” es la validación cruzada: el modelo aprende con 4 partes de los datos y se evalúa con la "
                   "quinta, cinco veces. La prueba final se mira una sola vez, al terminar.")
    with b:
        grafico(pesas(P, [(NOMBRE.get(m, m), EN.loc[m, "R2"], CV.loc[m, "R2"]) for m in MODELOS[1:]],
                      "Cuánto pierde cada modelo con puertos nuevos", "R²", [0.3, 0.82]))
        nota(P, f"<b>Cómo leerlo:</b> la barra gris es lo que el modelo se aprendió de memoria; cuanto más larga, peor le va con "
                f"puertos nuevos. <b>Ganó {MEJOR}</b>: el mejor con puertos nuevos ({c(CV.loc[MEJOR, 'R2'])}) y casi no memoriza. "
                f"El Random Forest pasa de {c(EN.loc['Random Forest', 'R2'])} a {c(CV.loc['Random Forest', 'R2'])}.")

# ------------------------------------------------------------------ 4. cuánto se equivoca
with t_err:
    pregunta(P, "¿Cuánto se equivoca el modelo elegido?")
    a, b, k = st.columns([1.1, 1.1, 0.8], gap="medium")
    real, prev, res = pred["pct_fw_fuera"] * 100, pred["predicho"] * 100, pred["residuo"] * 100
    with a:
        fig = go.Figure(go.Scatter(x=real, y=prev, mode="markers", marker=dict(size=pred["onts"].clip(4, 40) / 2.2 + 5, color=P["a1"],
                                                                                 opacity=.8, line=dict(color=P["fondo"], width=1)),
                                   customdata=np.c_[pred["Localidad"], pred["onts"]],
                                   hovertemplate="%{customdata[0]} · %{customdata[1]} equipos<br>real %{x:.0f} % · estimado %{y:.0f} %<extra></extra>"))
        fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", line=dict(color=P["gris"], dash="dash"), hoverinfo="skip"))
        layout(fig, P, 455, "Lo que estimó contra lo real")
        fig.update_xaxes(title="% real del puerto", range=[-3, 103])
        fig.update_yaxes(title="% que estimó el modelo", range=[-3, 103])
        grafico(fig)
    with b:
        fig = go.Figure(go.Scatter(x=prev, y=res, mode="markers", marker=dict(size=pred["onts"].clip(4, 40) / 2.2 + 5, color=P["a2"],
                                                                               opacity=.8, line=dict(color=P["fondo"], width=1)),
                                   hovertemplate="estimado %{x:.0f} %<br>se equivocó por %{y:.0f} puntos<extra></extra>"))
        fig.add_hline(y=0, line_color=P["a1"])
        layout(fig, P, 455, "De cuánto fue cada error")
        fig.update_xaxes(title="% que estimó el modelo")
        fig.update_yaxes(title="error: real − estimado (puntos)")
        grafico(fig)
    with k:
        nota(P, f"<b>Cómo leerlo:</b> cada punto es uno de los {len(pred)} puertos de prueba (más grande, más equipos). A la izquierda, "
                f"sobre la línea punteada = acierto exacto. A la derecha, sobre la línea = sin error; los errores se reparten "
                f"parejo para arriba y para abajo.")
        kpi(P, "Error promedio", f"{c(ERROR, 1)} puntos", f"adivinando siempre el promedio: {c(METAS['MAE_dummy_prueba'] * 100, 1)}")
        pat = T["residuos"]["patrones"]
        nota(P, f"<b>Dónde falla más:</b> en puertos de 5 equipos o menos se equivoca por "
                f"{c(pat['MAE_pon_5_onts_o_menos'] * 100, 0)} puntos; en el resto, por {c(pat['MAE_pon_mas_de_5_onts'] * 100, 0)}. "
                f"Un puerto de 2 equipos solo puede tener 0, 50 o 100 %.", P["a2"])

# ------------------------------------------------------------------ 5. qué lo explica
with t_exp:
    pregunta(P, "¿Qué hace que un puerto tenga más equipos fuera de estándar?")
    a, b = st.columns([1.15, 1], gap="medium")
    with a:
        im = imp[imp["caida_R2_media"] > 0].head(8).iloc[::-1]
        fig = go.Figure(go.Bar(x=im["caida_R2_media"], y=[VARIABLE.get(v, v) for v in im["variable"]], orientation="h",
                               marker_color=[P["a1"] if v == "pct_catv" else (P["a2"] if x > .05 else P["gris2"])
                                             for v, x in zip(im["variable"], im["caida_R2_media"])],
                               text=[c(x) for x in im["caida_R2_media"]], textposition="outside"))
        layout(fig, P, 430, "Qué pasa si le escondemos cada dato al modelo")
        fig.update_xaxes(title="cuánto empeora el modelo (caída del R²): más largo, más importante",
                         range=[0, im["caida_R2_media"].max() * 1.18])
        grafico(fig)
        st.caption("Le escondimos al modelo un dato por vez, mezclándolo al azar. Si el modelo empeora mucho, ese dato era importante.")
    with b:
        fig = go.Figure()
        posiciones = (["middle left", "bottom right"], ["middle left", "top right"], ["middle left", "middle right"])
        for (col_, nom), color, pos in zip((("R2_cv", "puertos nuevos"), ("R2_prueba", "prueba final"), ("R2_ajustado_prueba", "R² ajustado")),
                                           (P["a2"], P["a1"], P["gris"]), posiciones):
            fig.add_trace(go.Scatter(x=["Sin datos de la red", "Con datos de la red"], y=olt[col_], mode="lines+markers+text", name=nom,
                                     line=dict(color=color, width=3), marker=dict(size=12), text=[c(v) for v in olt[col_]],
                                     textposition=pos, textfont=dict(color=color)))
        layout(fig, P, 265, "¿Mejora con los datos de la red?", leyenda=True)
        fig.update_xaxes(range=[-0.45, 1.45])
        fig.update_yaxes(title="R²", range=[0, .7])
        grafico(fig)
        nota(P, f"<b>Lo que más pesa es qué modelos de equipo tiene el puerto</b> (el % con TV es casi lo mismo que el % de EG8143A5) "
                f"y en qué localidad está. Sumarle señal, distancia y % de equipos encendidos no lo mejora: las tres líneas bajan. Que un equipo esté "
                f"desactualizado depende de decisiones <b>administrativas</b>, no de la fibra.")

# ------------------------------------------------------------------ 6. probar un caso nuevo
with t_sim:
    pregunta(P, "¿Qué estimaría el modelo para un puerto que no existe?")
    pipe, columnas = modelo()
    a, b, k = st.columns([1, 1.15, 1.2], gap="medium")
    with a:
        claves = pons["pon_key"].tolist()
        base = st.selectbox("Partir de un puerto real", claves, index=claves.index("Localidad I|0/|5/"), format_func=puerto,
                            help="Carga los valores de ese puerto. Después cambialos como quieras para inventar uno nuevo.")
        f = pons.set_index("pon_key").loc[base]
        localidades = sorted(pons["Localidad"].unique())
        loc_s = st.selectbox("Localidad", localidades, index=localidades.index(f["Localidad"]), key=f"loc_{base}")
        onts = st.slider("Equipos en el puerto", 1, 120, int(f["onts"]), key=f"onts_{base}")
        n_mod = st.slider("Modelos de equipo distintos", 1, 15, int(f["n_modelos"]), key=f"nmod_{base}")
        catv = st.slider("% de equipos con salida de TV", 0, 100, int(round(f["pct_catv"] * 100)), key=f"catv_{base}") / 100
    with b:
        shares = {}
        for col in ("share_EG8141A5", "share_EG8143A5", "share_CN1001", "share_CN2002", "share_RDC143"):
            shares[col] = st.slider(f"% de equipos {col.split('_')[1]}", 0, 100, int(round(f[col] * 100)), key=f"{col}_{base}") / 100
        moderno = st.slider("% de equipos modernos", 0, 100, int(round(f["pct_moderno"] * 100)),
                            key=f"mod_{base}") / 100
    slots = pons.loc[pons["Localidad"] == loc_s, "Slot"]
    slot = f["Slot"] if loc_s == f["Localidad"] else slots.mode().iloc[0]   # la tarjeta casi no influye: se usa la más común
    caso = pd.DataFrame([{"Localidad": loc_s, "Slot": slot, "onts": onts, "pct_moderno": moderno, "pct_catv": catv, "n_modelos": n_mod,
                          **shares}])[columnas]
    crudo = float(pipe.predict(caso)[0])
    est = min(max(crudo, 0), 1) * 100
    equipos_est = est / 100 * onts
    puesto = int((ranking["equipos_previstos"] > equipos_est).sum()) + 1
    with k:
        kpi(P, "% fuera de estándar estimado", f"{c(est, 0)} %",
            f"lo real probablemente esté entre {c(max(est - ERROR, 0), 0)} y {c(min(est + ERROR, 100), 0)} %")
        kpi(P, "Equipos a actualizar", f"≈ {c(equipos_est, 0)} de {onts}",
            f"quedaría en el puesto {puesto} de {len(ranking) + 1} puertos: "
            f"{'entra' if puesto <= 10 else 'no entra'} en una ventana de 10", P["a2"])
        # avisos: valores fuera de lo que vio el modelo o combinaciones que no existen en la red real
        avisos = []
        if onts > pons["onts"].max():
            avisos.append(f"{onts} equipos es más de lo que vio el modelo (máximo real: {int(pons['onts'].max())}).")
        if n_mod > pons["n_modelos"].max():
            avisos.append(f"{n_mod} modelos distintos es más de lo que vio el modelo (máximo real: {int(pons['n_modelos'].max())}).")
        if sum(shares.values()) > 1.001:
            avisos.append(f"Los 5 modelos suman {c(sum(shares.values()) * 100, 0)} % de los equipos: no puede pasar de 100 %.")
        if sum(v > 0 for v in shares.values()) > n_mod:
            avisos.append(f"Hay {sum(v > 0 for v in shares.values())} modelos con equipos, pero pusiste {n_mod} modelos distintos.")
        if abs(catv - shares["share_EG8143A5"]) > .2:
            avisos.append("En la red real, el % con TV y el % de EG8143A5 casi coinciden. Esta combinación casi no existe.")
        if crudo < 0 or crudo > 1:
            avisos.append(f"El modelo dio {c(crudo * 100, 0)} %, que no es posible: se muestra recortado entre 0 y 100 %.")
        if avisos:
            nota(P, "<b>Ojo, este caso es raro:</b><br>" + "<br>".join(f"• {t}" for t in avisos) +
                    "<br>El modelo igual estima, pero el resultado es menos confiable.", P["mal"])
        else:
            nota(P, "<b>Caso dentro de lo conocido:</b> todos los valores están dentro de lo que el modelo vio en la red real, "
                    "así que vale el margen de error habitual.", P["ok"])
