"""TP4: figuras del artículo científico integrador (plantilla de la cátedra: letra Arial, ancho de una columna).

Cada figura sale de los datos procesados y de results/metrics.json; las que reentrenan modelos verifican antes de
guardarse que reproducen las cifras de metrics.json. Las capturas de la aplicación (Fig. 8) se recortan de las imágenes
que se sacan con la aplicación corriendo (ver src/articulo_tp4.py).
Correr:  python src/articulo_figuras.py"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from sklearn.metrics import average_precision_score, precision_recall_curve, r2_score, roc_auc_score, roc_curve
from sklearn.model_selection import cross_val_predict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import METRICS, RAIZ  # noqa: E402

SALIDA = RAIZ / "reports" / "TP4" / "figuras"
ANCHO = 2.75   # pulgadas: la columna angosta de la plantilla mide 7,05 cm
AZUL, AZUL_CLARO, AZUL_MEDIO = "#1f5fa8", "#a9c6ea", "#5b8fd1"
GRIS, GRIS_OSC, ROJO = "#bdbab3", "#4a4945", "#b8392f"
COLOR_TP = {"TP1": "#d9733f", "TP2": "#c98a12", "TP3": "#2f8f80", "TP4": AZUL}
ESTILO = {
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
    "font.size": 6.8, "axes.titlesize": 7, "axes.labelsize": 6.8, "xtick.labelsize": 6.2, "ytick.labelsize": 6.2,
    "legend.fontsize": 6.2, "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.5,
    "xtick.major.width": 0.5, "ytick.major.width": 0.5, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "lines.linewidth": 1.0, "savefig.dpi": 400, "axes.titlelocation": "left", "axes.titlepad": 4,
}
plt.rcParams.update(ESTILO)


def _c(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def _miles(n):
    return f"{int(n):,}".replace(",", ".")


def _coma(ax, ejes="xy"):
    for e in ejes:
        eje = ax.xaxis if e == "x" else ax.yaxis
        eje.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))


def _guardar(fig, nombre):
    ruta = SALIDA / nombre
    fig.savefig(ruta, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)
    return ruta


# ------------------------------------------------------------------ Fig. 1: flujo del proyecto
def fig_flujo(m):
    t2, t3, f1 = m["obj09_tp2"], m["obj14_tp3"], m["fase1_chequeos"]["detalle"]
    f = f1
    filas_olt = f1["OLT: filas"]["obtenido"]
    fig, ax = plt.subplots(figsize=(ANCHO, 3.35))
    ax.set_xlim(0, 1); ax.set_ylim(-0.01, 1.005); ax.axis("off")

    def caja(x0, y0, w, h, titulo, texto, color, relleno=None):
        ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0.006,rounding_size=0.018",
                                    fc=relleno or matplotlib.colors.to_rgba(color, 0.12), ec=color, lw=0.8))
        ax.text(x0 + w / 2, y0 + h - 0.022, titulo, ha="center", va="top", fontsize=6.1, fontweight="bold", color=GRIS_OSC)
        ax.text(x0 + w / 2, y0 + h - 0.066, texto, ha="center", va="top", fontsize=5.4, color=GRIS_OSC, linespacing=1.3)

    def flecha(x0, y0, x1, y1):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=6, lw=0.7, color=GRIS_OSC))

    gris = "#efeeea"
    caja(0.01, 0.84, 0.47, 0.15, "Inventario de ONT", f"{_miles(f['Filas']['obtenido'])} equipos · 13 columnas\nfoto estática, sin fechas",
         GRIS_OSC, gris)
    caja(0.52, 0.84, 0.47, 0.15, "Listado de la OLT", f"{_miles(filas_olt)} equipos · 29/10/2026\nestado, potencia y distancia",
         GRIS_OSC, gris)
    caja(0.01, 0.615, 0.47, 0.175, "TP1 · Limpieza y EDA",
         f"alias: {int(f['Modelos (nombres originales)']['obtenido'])} → {int(f['Modelos canónicos']['obtenido'])} modelos\n"
         f"variables derivadas\n{m['fase1_chequeos']['ok']} chequeos automáticos", COLOR_TP["TP1"])
    caja(0.01, 0.37, 0.47, 0.19, "TP2 · Regresión",
         f"{t2['datos']['pon']} puertos PON\n% de firmware fuera\nde estándar por puerto", COLOR_TP["TP2"])
    caja(0.52, 0.37, 0.47, 0.19, "TP3 · Clasificación",
         f"{_miles(t3['datos']['equipos'])} clientes online\n¿señal en riesgo?\n+ ensambles y K-Means", COLOR_TP["TP3"])
    caja(0.01, 0.17, 0.98, 0.145, "Selección y serialización (joblib)",
         f"{t2['mejor_modelo']} (TP2) y {t3['mejor_modelo'].lower()} (TP3): pipeline completo", COLOR_TP["TP4"])
    caja(0.01, 0.0, 0.98, 0.115, "TP4 · Aplicación web",
         "Streamlit y Plotly · validación de entradas", COLOR_TP["TP4"])
    flecha(0.245, 0.84, 0.245, 0.79)             # inventario -> TP1
    flecha(0.245, 0.615, 0.245, 0.56)            # TP1 -> TP2
    flecha(0.42, 0.615, 0.60, 0.56)              # TP1 -> TP3
    flecha(0.80, 0.84, 0.80, 0.56)               # OLT -> TP3
    flecha(0.245, 0.37, 0.245, 0.315)            # TP2 -> serialización
    flecha(0.755, 0.37, 0.755, 0.315)            # TP3 -> serialización
    flecha(0.5, 0.17, 0.5, 0.115)                # serialización -> app
    return _guardar(fig, "fig1_flujo.png")


# ------------------------------------------------------------------ Fig. 2: EDA del TP1
def fig_eda(m):
    onts = pd.read_csv(RAIZ / "data" / "processed" / "onts.csv", encoding="utf-8-sig")
    total = len(onts)
    conteo = onts["Modelo_canonico"].value_counts()
    wifi = onts.groupby("Modelo_canonico")["WiFi_Tecnologia"].agg(lambda s: s.str.contains(r"Wi-Fi [56]").mean())
    top = conteo.head(6)
    otros = conteo.iloc[6:]
    nombres = list(top.index) + [f"Otros {len(otros)}"]
    valores = list(top.values) + [int(otros.sum())]
    moderno = [wifi[n] > 0.5 for n in top.index] + [False]
    fig, (a, b) = plt.subplots(2, 1, figsize=(ANCHO, 3.15), gridspec_kw={"height_ratios": [1, 1.3], "hspace": 0.62})
    y = np.arange(len(valores))[::-1]
    a.barh(y, valores, color=[AZUL if mo else GRIS for mo in moderno], height=0.7)
    for yi, v in zip(y, valores):
        a.text(v + total * 0.006, yi, f"{_miles(v)} ({_c(v / total * 100, 1)} %)", va="center", fontsize=5.8)
    a.set_yticks(y, nombres); a.set_xlim(0, max(valores) * 1.42); a.tick_params(axis="y", length=0)
    a.set_xlabel("equipos"); _coma(a, "x")
    a.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _miles(v)))
    a.set_title(f"(a) Tres modelos son el {_c(m['obj01']['pct_top3'], 0)} % de los equipos")

    fuera = pd.Series(m["obj03"]["pct_fuera_por_localidad"]).sort_values()
    media = m["obj03"]["pct_fuera_estandar"]
    yb = np.arange(len(fuera))
    b.barh(yb, fuera.values, color=[AZUL if v == fuera.max() else GRIS for v in fuera.values], height=0.7)
    for yi, v in zip(yb, fuera.values):
        b.text(v + 1, yi, f"{_c(v, 1)} %", va="center", fontsize=5.8, zorder=3,
               bbox=dict(fc="white", ec="none", pad=0.2))
    b.axvline(media, color=ROJO, ls="--", lw=0.7, zorder=2)
    b.set_ylim(-0.6, len(fuera) + 0.4)
    b.text(media + 1.5, len(fuera) - 0.1, f"promedio de la red: {_c(media, 1)} %", color=ROJO, fontsize=5.8, va="center")
    b.set_yticks(yb, [n.replace("Santa Clara de Buena Vista", "Sta. Clara de B. Vista").replace("San Martin de las Escobas",
                                                                                                 "S. Martín de las Escobas")
                      for n in fuera.index])
    b.tick_params(axis="y", length=0); b.set_xlim(0, 105); b.set_xlabel("% de equipos con firmware fuera de estándar")
    b.set_title("(b) Firmware fuera de estándar por localidad")
    return _guardar(fig, "fig2_eda.png")


# ------------------------------------------------------------------ Fig. 3 y 4: TP2
def figs_tp2(m):
    import ast

    from sklearn.base import clone
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline

    import tp2_regresion as t2
    t = m["obj09_tp2"]
    mejor = t["mejor_modelo"]
    modelos = ["Dummy (promedio)", "Regresión Lineal", "Ridge", "Random Forest", "Gradient Boosting"]
    etiquetas = ["Dummy", "Lineal", "Ridge", "Random\nForest", "Gradient\nBoosting"]
    fig, ax = plt.subplots(figsize=(ANCHO, 1.75))
    x = np.arange(len(modelos))
    for j, (k, nombre, color) in enumerate([("entrenamiento", "Entrenamiento", AZUL_CLARO), ("cv_media", "Validación cruzada", AZUL_MEDIO),
                                            ("prueba", "Prueba", AZUL)]):
        v = [t[k][mo]["R2"] for mo in modelos]
        ax.bar(x + (j - 1) * 0.26, v, 0.26, color=color, label=nombre, edgecolor="white", linewidth=0.3)
    meta = t["criterio_smart"]["metas"]["R2_prueba"]
    ax.axhline(meta, color=ROJO, ls="--", lw=0.7)
    ax.text(-0.42, meta + 0.015, f"meta {_c(meta)}", color=ROJO, fontsize=5.8, ha="left", va="bottom")
    ax.axhline(0, color=GRIS_OSC, lw=0.5)
    ax.set_xticks(x, etiquetas); ax.tick_params(axis="x", length=0); ax.set_ylabel("$R^2$"); ax.set_ylim(-0.05, 0.95)
    ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, 1.12), handlelength=1, columnspacing=0.9)
    _coma(ax, "y")
    f3 = _guardar(fig, "fig3_tp2_comparacion.png")

    pons = t2.cargar_pons()
    train, test = t2.particion(pons)
    cols = t["variables"]["categoricas"] + t["variables"]["numericas"]
    pipe = Pipeline([("prep", t2.preprocesador(t["variables"]["numericas"])),
                     ("modelo", Ridge(**ast.literal_eval(t["hiperparametros_elegidos"][mejor])))])
    pipe.fit(train[cols], train[t2.OBJETIVO])
    pred = pipe.predict(test[cols])
    assert abs(r2_score(test[t2.OBJETIVO], pred) - t["prueba"][mejor]["R2"]) < 1e-9, "la figura no reproduce metrics.json"
    oof = cross_val_predict(clone(pipe), train[cols], train[t2.OBJETIVO], cv=t2.kfold())
    ytr, yte = train[t2.OBJETIVO].values, test[t2.OBJETIVO].values
    fig, (a, b) = plt.subplots(1, 2, figsize=(ANCHO, 1.55), gridspec_kw={"wspace": 0.5})
    a.scatter(ytr * 100, oof * 100, s=3, color=GRIS, linewidths=0, label="entrenamiento (VC)")
    a.scatter(yte * 100, pred * 100, s=5, color=AZUL, linewidths=0, label="prueba")
    a.plot([0, 100], [0, 100], color=GRIS_OSC, ls="--", lw=0.6)
    a.set_xlabel("real (%)"); a.set_ylabel("predicho (%)"); a.set_title("(a) Predicho contra real")
    b.scatter(oof * 100, (ytr - oof) * 100, s=3, color=GRIS, linewidths=0)
    b.scatter(pred * 100, (yte - pred) * 100, s=5, color=AZUL, linewidths=0)
    b.axhline(0, color=GRIS_OSC, lw=0.6)
    b.set_xlabel("predicho (%)"); b.set_ylabel("residuo (p.p.)"); b.set_title("(b) Residuos")
    for axx in (a, b):
        _coma(axx)
    f4 = _guardar(fig, "fig4_tp2_residuos.png")
    return f3, f4


# ------------------------------------------------------------------ Fig. 5, 6 y 7: TP3
CORTO = {"Regresión Logística": "Reg. logística", "Árbol de Decisión": "Árbol", "KNN": "KNN", "Naive Bayes": "Naive Bayes",
         "Random Forest": "Random Forest", "Gradient Boosting": "Grad. Boosting", "Regla de los vecinos": "Regla de vecinos"}


def figs_tp3(m):
    from informes_figuras import _ajustar_tp3

    import tp3_clasificacion as t3
    plt.rcParams.update(ESTILO)   # informes_figuras cambia la letra a Times al importarse
    t = m["obj14_tp3"]
    d, test, probas = _ajustar_tp3(m)   # reentrena con los hiperparámetros elegidos y verifica contra metrics.json
    y = test[t3.OBJETIVO].values

    mods = t3.INDIVIDUALES + t3.ENSAMBLES
    fig, axes = plt.subplots(2, 3, figsize=(ANCHO, 2.05), gridspec_kw={"hspace": 0.75, "wspace": 0.25})
    for ax, n in zip(axes.flat, mods):
        cm = np.array(t["matrices_confusion_prueba"][n])
        norm = cm / cm.sum(axis=1, keepdims=True)
        ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
        for i in range(2):
            for j in range(2):
                ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=6.4, color="white" if norm[i, j] > 0.6 else "black")
        ax.set_xticks([0, 1], ["sin", "riesgo"], fontsize=5.6); ax.set_yticks([0, 1], ["sin", "riesgo"], fontsize=5.6)
        if ax not in axes[:, 0]:
            ax.set_yticklabels([])
        ax.tick_params(length=0)
        ax.set_title(CORTO[n] + (" *" if n == t["mejor_modelo"] else ""), fontsize=6.4, loc="center", pad=3)
        for s in ax.spines.values():
            s.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel("real", fontsize=6)
    for ax in axes[1]:
        ax.set_xlabel("predicho", fontsize=6)
    f5 = _guardar(fig, "fig5_tp3_matrices.png")

    colores = {"Regresión Logística": AZUL, "Árbol de Decisión": "#7a5cc2", "KNN": "#2f9e8f", "Naive Bayes": "#d08a2e",
               "Random Forest": ROJO, "Gradient Boosting": "#8c6d46", "Regla de los vecinos": "black"}
    fig = plt.figure(figsize=(ANCHO, 2.35))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 0.5], wspace=0.45, hspace=0.62)
    a, b, ley = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])
    ley.axis("off")
    for n, s in probas.items():
        ls = "--" if n == "Regla de los vecinos" else "-"
        lw = 1.1 if n in (t["mejor_modelo"], "Regla de los vecinos") else 0.65
        fpr, tpr, _ = roc_curve(y, s)
        p, r, _ = precision_recall_curve(y, s)
        etiqueta = f"{CORTO[n]} ({_c(roc_auc_score(y, s))} | {_c(average_precision_score(y, s))})"
        a.plot(fpr, tpr, ls, color=colores[n], lw=lw, label=etiqueta)
        b.plot(r, p, ls, color=colores[n], lw=lw)
    a.plot([0, 1], [0, 1], color=GRIS, lw=0.6); b.axhline(y.mean(), color=GRIS, lw=0.6)
    a.set_xlabel("tasa de falsos positivos"); a.set_ylabel("recall"); a.set_title("(a) Curvas ROC")
    b.set_xlabel("recall"); b.set_ylabel("precisión"); b.set_title("(b) Precisión-recall")
    for axx in (a, b):
        axx.set_xticks([0, 0.5, 1]); axx.set_yticks([0, 0.5, 1])
        _coma(axx)
    ley.legend(*a.get_legend_handles_labels(), frameon=False, ncol=2, loc="center", fontsize=5.5, handlelength=1.6,
               columnspacing=0.8, title="modelo (ROC-AUC | PR-AUC en prueba)", title_fontsize=5.7)
    f6 = _guardar(fig, "fig6_tp3_roc_pr.png")

    cl = t3.clustering(d)
    c = t["clustering"]
    assert cl["k_mejor"] == c["k_mejor"], "el clustering no reproduce metrics.json"
    k, kx = cl["k_mejor"], cl["k_extra"]
    fig, axes = plt.subplots(2, 2, figsize=(ANCHO, 2.75), gridspec_kw={"hspace": 0.62, "wspace": 0.45})
    paleta = np.array(["#e0a030", AZUL, "#2f9e8f", ROJO, "#7a5cc2", GRIS_OSC, "#8c6d46", GRIS])
    pca = cl["pca"]
    axes[0, 0].scatter(pca[:, 0], pca[:, 1], c=paleta[cl["etiquetas"][k]], s=0.5, linewidths=0, alpha=0.7, rasterized=True)
    axes[0, 0].set_title(f"(a) K-Means, $k$ = {k}")
    clase = d[t3.OBJETIVO].values
    orden = np.argsort(clase)
    axes[0, 1].scatter(pca[orden, 0], pca[orden, 1], c=np.where(clase[orden] == 1, ROJO, GRIS), s=0.5, linewidths=0, alpha=0.7,
                       rasterized=True)
    axes[0, 1].set_title("(b) Clase real")
    for ax in axes[0]:
        ax.set_xlabel(f"CP1 ({_c(cl['pca_varianza'][0] * 100, 0)} %)"); ax.set_ylabel(f"CP2 ({_c(cl['pca_varianza'][1] * 100, 0)} %)")
        _coma(ax)
    ks = sorted(int(x) for x in c["silueta"])
    axes[1, 0].plot(ks, [c["silueta"][str(x)] for x in ks], marker="o", ms=2.5, color=AZUL, label="silueta")
    axes[1, 0].plot(ks, [c["ARI"][str(x)] for x in ks], marker="s", ms=2.5, color=ROJO, label="ARI")
    axes[1, 0].set_xlabel("$k$ (cantidad de grupos)"); axes[1, 0].set_title("(c) Elección de $k$")
    axes[1, 0].legend(frameon=False, loc="upper right", handlelength=1.4); axes[1, 0].set_ylim(0, 0.3)
    _coma(axes[1, 0])
    pe = cl["perfil_extra"].sort_values("pct_en_riesgo")
    top = pe["pct_en_riesgo"].max()
    axes[1, 1].barh([f"G{g} ({_miles(n)})" for g, n in zip(pe["grupo"], pe["equipos"])], pe["pct_en_riesgo"] * 100,
                    color=[ROJO if v == top else GRIS for v in pe["pct_en_riesgo"]], height=0.65)
    axes[1, 1].axvline(d[t3.OBJETIVO].mean() * 100, color=GRIS_OSC, ls="--", lw=0.6)
    for i, v in enumerate(pe["pct_en_riesgo"]):
        axes[1, 1].text(v * 100 + 0.8, i, f"{_c(v * 100, 1)} %", va="center", fontsize=5.6, zorder=3,
                        bbox=dict(fc="white", ec="none", pad=0.2))
    axes[1, 1].set_xlabel("% en riesgo"); axes[1, 1].set_xlim(0, top * 100 * 1.5); axes[1, 1].tick_params(axis="y", length=0)
    axes[1, 1].set_title(f"(d) Riesgo por grupo ($k$ = {kx})")
    _coma(axes[1, 1], "x")
    f7 = _guardar(fig, "fig7_tp3_clustering.png")
    return f5, f6, f7


# ------------------------------------------------------------------ figuras de la versión larga (10 páginas)
NOMBRES_VAR = {"pct_catv": "% con TV", "Localidad": "Localidad", "share_EG8141A5": "Prop. EG8141A5",
               "share_EG8143A5": "Prop. EG8143A5", "onts": "Equipos del PON", "share_CN1001": "Prop. CN1001",
               "share_RDC143": "Prop. RDC143", "pct_moderno": "% modernos", "share_CN2002": "Prop. CN2002",
               "n_modelos": "N.º de modelos", "Slot": "Slot", "vec_rxp": "Señal de los vecinos",
               "WiFi_Tecnologia": "Wi-Fi", "onts_pon": "Equipos del PON", "fw_generacion": "Generación de firmware",
               "fw_fuera_estandar": "Firmware fuera de est.", "Puertos_LAN": "Puertos LAN", "ID": "ID",
               "id_rel": "Posición en el PON", "Modelo_canonico": "Modelo", "slot_n": "Slot", "pon_n": "PON",
               "Distancia_m": "Distancia"}


def fig_importancia(m):
    """Importancia por permutación en prueba: Ridge (caída del R²) y regresión logística (caída del PR-AUC)."""
    i2 = pd.read_csv(RAIZ / "reports" / "TP2" / "importancia_permutacion.csv", encoding="utf-8-sig").head(7).iloc[::-1]
    i3 = pd.read_csv(RAIZ / "reports" / "TP3" / "importancia_permutacion.csv", encoding="utf-8-sig").head(6).iloc[::-1]
    assert abs(i3.iloc[-1]["caida_PR_AUC_media"] - m["obj14_tp3"]["importancia_permutacion"]["vec_rxp"]) < 1e-12
    fig, (a, b) = plt.subplots(2, 1, figsize=(ANCHO, 2.85), gridspec_kw={"hspace": 0.75})
    err = {"lw": 0.6, "ecolor": GRIS_OSC, "capsize": 1.5}
    a.barh([NOMBRES_VAR[v] for v in i2["variable"]], i2["caida_R2_media"], xerr=i2["caida_R2_desvio"], height=0.65,
           color=[AZUL if v > 0.05 else GRIS for v in i2["caida_R2_media"]], error_kw=err)
    a.set_xlabel("caída del R² en prueba al desordenar la variable"); a.set_title("(a) Ridge (TP2)")
    b.barh([NOMBRES_VAR[v] for v in i3["variable"]], i3["caida_PR_AUC_media"], xerr=i3["caida_PR_AUC_desvio"], height=0.65,
           color=[AZUL if v > 0.05 else GRIS for v in i3["caida_PR_AUC_media"]], error_kw=err)
    b.set_xlabel("caída del PR-AUC en prueba al desordenar la variable"); b.set_title("(b) Regresión logística (TP3)")
    for ax in (a, b):
        ax.tick_params(axis="y", length=0); ax.axvline(0, color=GRIS_OSC, lw=0.5)
        _coma(ax, "x")
    return _guardar(fig, "fig_importancia.png")


def fig_aprendizaje(m):
    """Curva de aprendizaje del TP2: RMSE en entrenamiento y validación según la cantidad de puertos."""
    t = m["obj09_tp2"]["curva_aprendizaje"]
    fig, ax = plt.subplots(figsize=(ANCHO, 1.65))
    for nombre, archivo, color in [("Ridge", "curva_aprendizaje_ridge.csv", AZUL),
                                   ("Random Forest", "curva_aprendizaje_random_forest.csv", ROJO)]:
        cu = pd.read_csv(RAIZ / "reports" / "TP2" / archivo, encoding="utf-8-sig")
        ax.plot(cu["n_entrenamiento"], cu["RMSE_entrenamiento"] * 100, ls="--", color=color, lw=0.9)
        ax.plot(cu["n_entrenamiento"], cu["RMSE_validacion"] * 100, color=color, marker="o", ms=2.3, label=nombre)
    assert abs(cu["RMSE_validacion"].iloc[-1] - t["Random Forest"]["RMSE_validacion_final"]) < 1e-12
    ax.plot([], [], ls="--", color=GRIS_OSC, label="entrenamiento"); ax.plot([], [], color=GRIS_OSC, label="validación")
    ax.set_xlabel("puertos PON de entrenamiento"); ax.set_ylabel("RMSE (puntos %)")
    ax.legend(frameon=False, ncol=2, loc="upper right", fontsize=5.6, handlelength=1.6, columnspacing=0.8)
    ax.set_ylim(8, 19)
    _coma(ax)
    return _guardar(fig, "fig_aprendizaje.png")


def fig_umbral(m):
    """Precisión y recall de la regresión logística en prueba según el umbral, con los dos umbrales discutidos."""
    import joblib
    from sklearn.metrics import precision_score, recall_score
    t = m["obj14_tp3"]
    g = joblib.load(RAIZ / "modelos" / "tp3_regresion_logistica.joblib")
    d = pd.read_csv(RAIZ / "data" / "processed" / "tp3_clientes.csv", encoding="utf-8-sig")
    test = d[d["conjunto"] == "prueba"]
    y = test[g["objetivo"]].values
    proba = g["pipeline"].predict_proba(test[g["categoricas"] + g["numericas"]])[:, 1]
    comp = t["umbral_decision"]["comparacion_prueba"]
    for clave in ("0,5 (por defecto)", "recall 80 % en CV"):
        u = comp[clave]["valor"]
        assert abs(recall_score(y, proba >= u) - comp[clave]["recall"]) < 1e-9, "el umbral no reproduce metrics.json"
    us = np.linspace(0.05, 0.95, 181)
    prec = [precision_score(y, proba >= u, zero_division=np.nan) for u in us]
    rec = [recall_score(y, proba >= u) for u in us]
    fig, ax = plt.subplots(figsize=(ANCHO, 1.85))
    ax.plot(us, rec, color=AZUL, label="recall (clientes en riesgo encontrados)")
    ax.plot(us, prec, color=ROJO, label="precisión (marcados que están en riesgo)")
    for clave, texto, lado in (("0,5 (por defecto)", "umbral 0,5", 1), ("recall 80 % en CV", "recall 80 %\nen VC", -1)):
        u = comp[clave]["valor"]
        ax.axvline(u, color=GRIS_OSC, ls=":", lw=0.7)
        ax.text(u + lado * 0.012, 0.04, texto, fontsize=5.6, va="bottom", ha="left" if lado > 0 else "right",
                color=GRIS_OSC, bbox=dict(fc="white", ec="none", pad=0.3))
    ax.set_xlabel("umbral sobre el puntaje del modelo"); ax.set_ylim(0, 1.02); ax.set_xlim(0.05, 0.95)
    ax.legend(frameon=False, loc="lower center", fontsize=5.6, handlelength=1.4, bbox_to_anchor=(0.5, 1.0))
    _coma(ax)
    return _guardar(fig, "fig_umbral.png")


def fig_distribuciones(m):
    """(a) % de firmware fuera de estándar por puerto (variable del TP2) y (b) % de clientes en riesgo según la señal media
    de sus vecinos de puerto (evidencia directa del hallazgo del TP3). Mismos datos que las pestañas «El problema» y
    «Qué lo explica» del dashboard."""
    pons = pd.read_csv(RAIZ / "data" / "processed" / "pons.csv", encoding="utf-8-sig")
    y = pons["pct_fw_fuera"] * 100
    assert abs(y.mean() / 100 - m["obj09_tp2"]["datos"]["objetivo_media"]) < 1e-9
    v = pd.read_csv(RAIZ / "data" / "app" / "tp3_vecinos.csv", encoding="utf-8-sig")
    v = v[v["clientes"] >= 20]
    red = m["obj14_tp3"]["datos"]["pct_en_riesgo"] * 100
    fig, (a, b) = plt.subplots(2, 1, figsize=(ANCHO, 3.3), gridspec_kw={"hspace": 0.72})
    a.hist(y, bins=np.arange(0, 105, 5), color=AZUL_MEDIO, edgecolor="white", linewidth=0.4)
    a.axvline(y.median(), color=ROJO, ls="--", lw=0.8)
    a.text(y.median() + 1.5, a.get_ylim()[1] * 0.92, f"mediana {_c(y.median(), 1)} %", color=ROJO, fontsize=5.8, va="top",
           bbox=dict(fc="white", ec="none", pad=0.3))
    a.set_xlabel("% de equipos del puerto con firmware fuera de estándar"); a.set_ylabel("puertos PON")
    a.set_title(f"(a) Variable del TP2 en los {len(y)} puertos")
    _coma(a)
    x = v["vecinos_desde_dBm"] + 0.5
    b.bar(x, v["pct_en_riesgo"] * 100, width=0.85, color=[ROJO if p * 100 > red else GRIS for p in v["pct_en_riesgo"]])
    b.axhline(red, color=GRIS_OSC, ls="--", lw=0.7)
    b.text(x.max() + 0.4, red + 2, f"red: {_c(red, 1)} %", fontsize=5.8, color=GRIS_OSC, ha="right", va="bottom")
    for xi, p in zip(x, v["pct_en_riesgo"]):
        if p * 100 > 30:
            b.text(xi, p * 100 + 2, f"{_c(p * 100, 0)} %", ha="center", fontsize=5.6)
    b.set_xlabel("señal media de los vecinos del puerto (dBm)"); b.set_ylabel("% en riesgo")
    b.set_title("(b) TP3: % en riesgo según la señal de los vecinos")
    b.set_ylim(0, 100)
    _coma(b)
    return _guardar(fig, "fig_distribuciones.png")


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    m = json.loads(METRICS.read_text(encoding="utf-8"))
    rutas = [fig_flujo(m), fig_eda(m), *figs_tp2(m), *figs_tp3(m), fig_importancia(m), fig_aprendizaje(m), fig_umbral(m),
             fig_distribuciones(m)]
    for r in rutas:
        print(r.relative_to(RAIZ))


if __name__ == "__main__":
    main()
