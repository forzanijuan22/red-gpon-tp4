"""Figuras de los informes del TP2 y del TP3 (estilo IEEE: letra Times, ancho de página, 300 dpi).
Los modelos se reconstruyen con los hiperparámetros elegidos que guarda metrics.json, y cada figura verifica
que sus cifras coincidan con las de metrics.json antes de guardarse."""
import ast
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score, precision_recall_curve, r2_score, roc_auc_score, roc_curve
from sklearn.model_selection import cross_val_predict
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import METRICS, RAIZ  # noqa: E402

AZUL, AZUL_CLARO, AZUL_MEDIO, GRIS, GRIS_OSC, ROJO = "#1f5fa8", "#a9c6ea", "#5b8fd1", "#bdbab3", "#4a4945", "#b8392f"
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"], "mathtext.fontset": "stix",
    "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5, "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "lines.linewidth": 1.2, "savefig.dpi": 300,
})
ANCHO = 6.3   # pulgadas: ancho útil de la página del informe


def _c(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def _coma(ax, ejes="xy"):
    """Separador decimal con coma, solo en los ejes numéricos (los de categorías conservan sus etiquetas)."""
    for e in ejes:
        eje = ax.xaxis if e == "x" else ax.yaxis
        eje.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))


def _guardar(fig, ruta):
    fig.savefig(ruta, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return ruta


# ------------------------------------------------------------------ TP2
def figuras_tp2(m, carpeta):
    import tp2_regresion as t2
    t = m["obj09_tp2"]
    mejor = t["mejor_modelo"]
    var = t["variables"]
    pons = t2.cargar_pons()
    train, test = t2.particion(pons)
    cols = var["categoricas"] + var["numericas"]
    alpha = ast.literal_eval(t["hiperparametros_elegidos"]["Ridge"])["alpha"]
    pipe = Pipeline([("prep", t2.preprocesador(var["numericas"])), ("modelo", Ridge(alpha=alpha))])
    pipe.fit(train[cols], train[t2.OBJETIVO])
    pred_te = pipe.predict(test[cols])
    assert abs(r2_score(test[t2.OBJETIVO], pred_te) - t["prueba"][mejor]["R2"]) < 1e-9, "la figura no reproduce metrics.json"
    oof = cross_val_predict(clone(pipe), train[cols], train[t2.OBJETIVO], cv=t2.kfold())
    salidas = {}

    # Fig. 1: R² y RMSE por modelo en entrenamiento, validación cruzada y prueba
    modelos = ["Dummy (promedio)", "Regresión Lineal", "Ridge", "Random Forest", "Gradient Boosting"]
    etiquetas = ["Dummy", "Lineal", "Ridge", "Random\nForest", "Gradient\nBoosting"]
    conj = [("entrenamiento", "Entrenamiento", AZUL_CLARO), ("cv_media", "Validación cruzada", AZUL_MEDIO), ("prueba", "Prueba", AZUL)]
    fig, axes = plt.subplots(1, 2, figsize=(ANCHO, 2.3))
    x = np.arange(len(modelos))
    for ax, met, tit in zip(axes, ["R2", "RMSE"], ["(a) $R^2$ (mayor es mejor)", "(b) RMSE (menor es mejor)"]):
        for j, (k, nombre, color) in enumerate(conj):
            v = [t[k][mo][met] for mo in modelos]
            ax.bar(x + (j - 1) * 0.26, v, 0.26, color=color, label=nombre, edgecolor="white", linewidth=0.3)
        ax.set_xticks(x, etiquetas); ax.set_title(tit, loc="left"); ax.axhline(0, color=GRIS_OSC, lw=0.5)
        _coma(ax, "y")
    axes[0].legend(frameon=False, loc="upper left", ncol=1)
    fig.tight_layout(w_pad=2)
    salidas["fig1"] = _guardar(fig, carpeta / "ieee_fig1_comparacion.png")

    # Fig. 2: predicho contra real, residuos contra predichos e histograma de residuos (mejor modelo)
    ytr, yte = train[t2.OBJETIVO].values, test[t2.OBJETIVO].values
    fig, axes = plt.subplots(1, 3, figsize=(ANCHO, 2.15))
    a = axes[0]
    a.scatter(ytr * 100, oof * 100, s=6, color=GRIS, label="Entrenamiento (fuera de muestra)", linewidths=0)
    a.scatter(yte * 100, pred_te * 100, s=10, color=AZUL, label="Prueba", linewidths=0)
    a.plot([0, 100], [0, 100], color=GRIS_OSC, ls="--", lw=0.8)
    a.set_xlabel("Real (%)"); a.set_ylabel("Predicho (%)"); a.set_title("(a) Predicho contra real", loc="left")
    b = axes[1]   # sin leyenda: el epígrafe explica los colores (gris = entrenamiento fuera de muestra, azul = prueba)
    b.scatter(oof * 100, (ytr - oof) * 100, s=6, color=GRIS, linewidths=0)
    b.scatter(pred_te * 100, (yte - pred_te) * 100, s=10, color=AZUL, linewidths=0)
    b.axhline(0, color=GRIS_OSC, lw=0.8)
    b.set_xlabel("Predicho (%)"); b.set_ylabel("Residuo (p.p.)"); b.set_title("(b) Residuos contra predichos", loc="left")
    h = axes[2]
    bins = np.linspace(-50, 50, 26)
    h.hist((ytr - oof) * 100, bins=bins, color=GRIS, label="Entrenamiento")
    h.hist((yte - pred_te) * 100, bins=bins, color=AZUL, alpha=0.85, label="Prueba")
    h.set_xlabel("Residuo (p.p.)"); h.set_ylabel("PON"); h.set_title("(c) Distribución de residuos", loc="left")
    for ax in axes:
        _coma(ax)
    fig.tight_layout(w_pad=1.2)
    salidas["fig2"] = _guardar(fig, carpeta / "ieee_fig2_residuos.png")

    # Fig. 3: importancia por permutación y curva de aprendizaje
    imp = pd.read_csv(RAIZ / "reports" / "TP2" / "importancia_permutacion.csv").head(8).iloc[::-1]
    nombres = {"pct_catv": "% con TV", "Localidad": "Localidad", "share_EG8141A5": "Prop. EG8141A5", "share_EG8143A5": "Prop. EG8143A5",
               "onts": "Equipos del PON", "share_CN1001": "Prop. CN1001", "share_RDC143": "Prop. RDC143", "pct_moderno": "% modernos",
               "share_CN2002": "Prop. CN2002", "n_modelos": "N.º de modelos", "Slot": "Slot", "share_RDC141": "Prop. RDC141"}
    curva = pd.read_csv(next((RAIZ / "reports" / "TP2").glob(f"curva_aprendizaje_{mejor.lower()}.csv")))
    curva_rf = pd.read_csv(RAIZ / "reports" / "TP2" / "curva_aprendizaje_random_forest.csv")
    fig, (a, b) = plt.subplots(1, 2, figsize=(ANCHO, 2.6), gridspec_kw={"width_ratios": [1.05, 1]})
    a.barh([nombres.get(v, v) for v in imp["variable"]], imp["caida_R2_media"], xerr=imp["caida_R2_desvio"],
           color=[AZUL if v > 0.02 else GRIS for v in imp["caida_R2_media"]], error_kw={"lw": 0.6, "ecolor": GRIS_OSC})
    a.set_xlabel("Caída del $R^2$ en prueba"); a.set_title("(a) Importancia por permutación", loc="left")
    for nombre, cu, color in [(mejor, curva, AZUL), ("Random Forest", curva_rf, ROJO)]:
        b.plot(cu["n_entrenamiento"], cu["RMSE_entrenamiento"] * 100, ls="--", color=color, lw=1)
        b.plot(cu["n_entrenamiento"], cu["RMSE_validacion"] * 100, color=color, marker="o", ms=2.5, label=nombre)
    b.plot([], [], ls="--", color=GRIS_OSC, label="entrenamiento"); b.plot([], [], color=GRIS_OSC, label="validación")
    b.set_xlabel("PON de entrenamiento"); b.set_ylabel("RMSE (p.p.)"); b.set_title("(b) Curva de aprendizaje", loc="left")
    b.legend(frameon=False, ncol=4, fontsize=6.3, loc="upper center", bbox_to_anchor=(0.5, -0.3), columnspacing=0.8, handlelength=1.6)
    _coma(a, "x"); _coma(b)
    fig.tight_layout(w_pad=1.5)
    salidas["fig3"] = _guardar(fig, carpeta / "ieee_fig3_importancia.png")
    return salidas


# ------------------------------------------------------------------ TP3
def _ajustar_tp3(m):
    import tp3_clasificacion as t3
    t = m["obj14_tp3"]
    d = t3.cargar_datos()
    train, test = t3.particion(d)
    cols = t3.CATEGORICAS + t3.NUMERICAS
    probas = {}
    for n in t3.INDIVIDUALES + t3.ENSAMBLES:
        est, _, _, _ = t3.HIPERPARAMETROS[n]
        pipe = Pipeline([("prep", t3.preprocesador()), ("modelo", clone(est))])
        params = ast.literal_eval(t["hiperparametros_elegidos"][n])
        pipe.set_params(**{f"modelo__{k}": v for k, v in params.items()})
        pipe.fit(train[cols], train[t3.OBJETIVO])
        probas[n] = pipe.predict_proba(test[cols])[:, 1]
        assert abs(roc_auc_score(test[t3.OBJETIVO], probas[n]) - t["prueba"][n]["ROC_AUC"]) < 1e-6, f"{n}: no reproduce metrics.json"
    probas["Regla de los vecinos"] = -test["vec_rxp"].fillna(train["vec_rxp"].median()).values
    return d, test, probas


def figuras_tp3(m, carpeta):
    import tp3_clasificacion as t3
    t = m["obj14_tp3"]
    d, test, probas = _ajustar_tp3(m)
    y = test[t3.OBJETIVO].values
    salidas = {}

    # Fig. 1: matrices de confusión (prueba) de los 4 individuales y los 2 ensambles
    mods = t3.INDIVIDUALES + t3.ENSAMBLES
    fig, axes = plt.subplots(1, 6, figsize=(ANCHO, 1.45))
    for ax, n in zip(axes, mods):
        cm = np.array(t["matrices_confusion_prueba"][n])
        norm = cm / cm.sum(axis=1, keepdims=True)
        ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
        for i in range(2):
            for j in range(2):
                ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=8, color="white" if norm[i, j] > 0.6 else "black")
        ax.set_xticks([0, 1], ["Sin", "Riesgo"], fontsize=6.5); ax.set_yticks([0, 1], ["Sin", "Riesgo"], fontsize=6.5)
        ax.tick_params(length=0)
        ax.set_title(n.replace("Regresión Logística", "Reg. Logística").replace("Árbol de Decisión", "Árbol")
                     .replace("Gradient Boosting", "Grad. Boosting").replace("Random Forest", "Rand. Forest"), fontsize=7.5)
        for s in ax.spines.values():
            s.set_visible(False)
    axes[0].set_ylabel("Real", fontsize=7)
    for ax in axes:
        ax.set_xlabel("Predicho", fontsize=7)
    fig.tight_layout(w_pad=0.6)
    salidas["fig1"] = _guardar(fig, carpeta / "ieee_fig1_matrices.png")

    # Fig. 2: curvas ROC y precisión-recall en prueba
    colores = {"Regresión Logística": AZUL, "Árbol de Decisión": "#7a5cc2", "KNN": "#2f9e8f", "Naive Bayes": "#d08a2e",
               "Random Forest": ROJO, "Gradient Boosting": "#8c6d46", "Regla de los vecinos": "black"}
    fig, (a, b) = plt.subplots(1, 2, figsize=(ANCHO, 2.5))
    for n, s in probas.items():
        ls = "--" if n == "Regla de los vecinos" else "-"
        fpr, tpr, _ = roc_curve(y, s)
        p, r, _ = precision_recall_curve(y, s)
        etiqueta = n.replace("Regresión Logística", "Reg. Logística").replace("Regla de los vecinos", "Regla de vecinos")
        a.plot(fpr, tpr, ls, color=colores[n], lw=1.1 if n in (t["mejor_modelo"], "Regla de los vecinos") else 0.8,
               label=f"{etiqueta} ({_c(roc_auc_score(y, s))})")
        b.plot(r, p, ls, color=colores[n], lw=1.1 if n in (t["mejor_modelo"], "Regla de los vecinos") else 0.8,
               label=f"{etiqueta} ({_c(average_precision_score(y, s))})")
    a.plot([0, 1], [0, 1], color=GRIS, lw=0.7); b.axhline(y.mean(), color=GRIS, lw=0.7)
    a.set_xlabel("Tasa de falsos positivos"); a.set_ylabel("Recall"); a.set_title("(a) Curvas ROC (AUC)", loc="left")
    b.set_xlabel("Recall"); b.set_ylabel("Precisión"); b.set_title("(b) Curvas precisión-recall (AP)", loc="left")
    a.legend(frameon=False, fontsize=6.3, loc="lower right"); b.legend(frameon=False, fontsize=6.3, loc="upper right")
    for ax in (a, b):
        _coma(ax)
    fig.tight_layout(w_pad=1.5)
    salidas["fig2"] = _guardar(fig, carpeta / "ieee_fig2_roc_pr.png")

    # Fig. 3: clustering (PCA por grupo, PCA por clase y % en riesgo por grupo con k = 4)
    cl = t3.clustering(d)
    c = t["clustering"]
    assert cl["k_mejor"] == c["k_mejor"], "el clustering no reproduce metrics.json"
    k, kx = cl["k_mejor"], cl["k_extra"]
    fig, axes = plt.subplots(1, 3, figsize=(ANCHO, 2.15), gridspec_kw={"width_ratios": [1, 1, 0.95]})
    paleta = np.array([AZUL, "#e0a030", "#2f9e8f", ROJO, "#7a5cc2", GRIS_OSC, "#8c6d46", GRIS])
    axes[0].scatter(cl["pca"][:, 0], cl["pca"][:, 1], c=paleta[cl["etiquetas"][k]], s=1.2, linewidths=0, alpha=0.7)
    axes[0].set_title(f"(a) Grupos de K-Means ($k$ = {k})", loc="left")
    clase = d[t3.OBJETIVO].values
    orden = np.argsort(clase)
    axes[1].scatter(cl["pca"][orden, 0], cl["pca"][orden, 1], c=np.where(clase[orden] == 1, ROJO, GRIS), s=1.2, linewidths=0, alpha=0.7)
    axes[1].set_title("(b) Clase real", loc="left")   # sin leyenda: el epígrafe explica rojo = en riesgo, gris = sin riesgo
    for ax in axes[:2]:
        ax.set_xlabel(f"CP1 ({_c(cl['pca_varianza'][0] * 100, 0)} %)"); ax.set_ylabel(f"CP2 ({_c(cl['pca_varianza'][1] * 100, 0)} %)")
        _coma(ax)
    pe = cl["perfil_extra"].sort_values("pct_en_riesgo")
    top = pe["pct_en_riesgo"].max()
    axes[2].barh([f"G{g} ({n})" for g, n in zip(pe["grupo"], pe["equipos"])], pe["pct_en_riesgo"] * 100,
                 color=[ROJO if v == top else GRIS for v in pe["pct_en_riesgo"]])
    axes[2].axvline(d[t3.OBJETIVO].mean() * 100, color=GRIS_OSC, ls="--", lw=0.7)
    for i, v in enumerate(pe["pct_en_riesgo"]):
        axes[2].text(v * 100 + 0.6, i, f"{_c(v * 100, 1)} %", va="center", fontsize=7)
    axes[2].set_xlabel("% en riesgo"); axes[2].set_xlim(0, top * 100 * 1.35)
    axes[2].set_title(f"(c) Riesgo por grupo ($k$ = {kx})", loc="left")
    _coma(axes[2], "x")
    fig.tight_layout(w_pad=1.0)
    salidas["fig3"] = _guardar(fig, carpeta / "ieee_fig3_clustering.png")
    return salidas


if __name__ == "__main__":
    met = json.loads(METRICS.read_text(encoding="utf-8"))
    print(figuras_tp2(met, RAIZ / "reports" / "TP2"))
    print(figuras_tp3(met, RAIZ / "reports" / "TP3"))
