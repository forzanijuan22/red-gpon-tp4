"""Fase 3, TP2 (objetivo 9): regresión del % de equipos con firmware fuera de estándar en cada puerto PON.

Cada fila es un PON (301). Las funciones se usan paso a paso desde notebooks/TP2_regresion.ipynb;
main() corre todo de una vez para run_all.py. Las dos vías producen los mismos archivos y cifras."""
import sys
from pathlib import Path

import matplotlib
if "ipykernel" not in sys.modules:   # en el notebook se deja el backend inline para ver las figuras
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, KFold, cross_val_predict, learning_curve, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import RAIZ, guardar_figura, guardar_metricas  # noqa: E402

SEED = 42
OUT = RAIZ / "reports" / "TP2"
OBJETIVO = "pct_fw_fuera"
CATEGORICAS = ["Localidad", "Slot"]
NUMERICAS_BASE = ["onts", "pct_moderno", "pct_catv", "n_modelos"]
N_SHARES = 5                                    # solo las proporciones de los 5 modelos más usados
PROHIBIDAS = ["pct_v3", "n_versiones", OBJETIVO]  # todo lo que sale de Version es la respuesta
VARIABLES_OLT = ["olt_pct_online", "olt_dist_mediana_km", "olt_rxp_mediana_dbm"]

# Umbrales del criterio SMART (CLAUDE.md, Fase 3)
META_R2, META_R2_AJ = 0.45, 0.30
# Convención del equipo para diagnosticar el ajuste comparando entrenamiento y prueba
UMBRAL_SUBAJUSTE = 0.45   # R² de entrenamiento menor que esto: el modelo ni siquiera explica bien lo que ya vio
UMBRAL_BRECHA = 0.15      # R² entrenamiento − R² prueba mayor que esto: memoriza más de lo que generaliza

ACENTO, ACENTO_CLARO, GRIS, TINTA2 = "#2a78d6", "#9cc3ee", "#c9c7c0", "#52514e"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})

HIPERPARAMETROS = {
    # nombre: (estimador, grilla, justificación)
    "Dummy (promedio)": (
        DummyRegressor(strategy="mean"), {},
        "Predice siempre el promedio del entrenamiento. Es el piso: un modelo que no le gana no sirve."),
    "Regresión Lineal": (
        LinearRegression(), {},
        "Línea base de la consigna. Sin hiperparámetros: mínimos cuadrados ordinarios."),
    "Ridge": (
        Ridge(), {"modelo__alpha": [0.1, 1, 10]},
        "Regresión lineal con penalización L2. Con 240 PON y ~21 predictores (varios one-hot), "
        "alpha controla cuánto se encogen los coeficientes: 0,1 (casi lineal), 1 (por defecto), 10 (fuerte)."),
    "Random Forest": (
        RandomForestRegressor(n_estimators=300, random_state=SEED, n_jobs=-1),
        {"modelo__min_samples_leaf": [1, 3, 5], "modelo__max_depth": [None, 8]},
        "300 árboles (con más, el error ya no cambia). min_samples_leaf y max_depth limitan la "
        "profundidad: con pocos PON, hojas de 1 PON memorizan ruido, por eso se prueban 3 y 5."),
    "Gradient Boosting": (
        GradientBoostingRegressor(n_estimators=200, random_state=SEED),
        {"modelo__learning_rate": [0.05, 0.1], "modelo__max_depth": [2, 3]},
        "200 árboles chicos en secuencia. learning_rate 0,05 o 0,1 (pasos cortos, menos sobreajuste); "
        "max_depth 2 o 3 (interacciones de a pares o de a tres variables, suficiente para 240 filas)."),
}


# ------------------------------------------------------------------ datos y variables
def cargar_pons():
    return pd.read_csv(RAIZ / "data" / "processed" / "pons.csv")


def particion(pons):
    """80/20 con semilla 42. Cada fila es un PON, así que no hace falta agrupar."""
    return train_test_split(pons, test_size=0.2, random_state=SEED)


def top_shares(train, n=N_SHARES):
    """Proporciones de los n modelos con mayor media, calculadas solo con el entrenamiento."""
    shares = [c for c in train.columns if c.startswith("share_")]
    return train[shares].mean().sort_values(ascending=False).head(n).index.tolist()


def kfold():
    return KFold(n_splits=5, shuffle=True, random_state=SEED)


def preprocesador(numericas, categoricas=CATEGORICAS):
    """One-hot para las categóricas y escalado para las numéricas, todo dentro del pipeline.
    La imputación por mediana solo actúa en la prueba con datos de la OLT (PON sin lectura)."""
    num = Pipeline([("imputar", SimpleImputer(strategy="median")), ("escalar", StandardScaler())])
    return ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), categoricas), ("num", num, numericas)])


def n_predictores(pipe, categoricas=CATEGORICAS):
    """Predictores efectivos para el R² ajustado: columnas one-hot menos una referencia por categórica
    (la codificación completa es redundante: las columnas de cada categórica suman 1)."""
    if isinstance(pipe.named_steps["modelo"], DummyRegressor):
        return 0
    return len(pipe.named_steps["prep"].get_feature_names_out()) - len(categoricas)


# ------------------------------------------------------------------ métricas
def r2_ajustado(r2, n, p):
    return 1 - (1 - r2) * (n - 1) / (n - p - 1) if n - p - 1 > 0 else np.nan


def metricas(y, yhat, p):
    mse = mean_squared_error(y, yhat)
    r2 = r2_score(y, yhat)
    return {"MSE": mse, "RMSE": np.sqrt(mse), "MAE": mean_absolute_error(y, yhat), "R2": r2,
            "R2_ajustado": r2_ajustado(r2, len(y), p)}


def metricas_cv(pipe, X, y):
    """Las 5 métricas en cada partición del KFold (el modelo se reajusta en cada una)."""
    filas = []
    for tr, va in kfold().split(X):
        m = clone(pipe).fit(X.iloc[tr], y.iloc[tr])
        filas.append(metricas(y.iloc[va], m.predict(X.iloc[va]), n_predictores(m)))
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ entrenamiento
def entrenar(nombre, X, y, numericas, categoricas=CATEGORICAS):
    """GridSearchCV sobre el entrenamiento con KFold(5). Elige por RMSE y reajusta con todo el entrenamiento."""
    est, grilla, _ = HIPERPARAMETROS[nombre]
    pipe = Pipeline([("prep", preprocesador(numericas, categoricas)), ("modelo", clone(est))])
    gs = GridSearchCV(pipe, grilla, cv=kfold(), refit="rmse", return_train_score=True,
                      scoring={"rmse": "neg_root_mean_squared_error", "mae": "neg_mean_absolute_error", "r2": "r2"})
    return gs.fit(X, y)


def entrenar_todos(X, y, numericas):
    return {n: entrenar(n, X, y, numericas) for n in HIPERPARAMETROS}


def tabla_metricas(busquedas, Xtr, ytr, Xte, yte):
    """Tabla larga: modelo x conjunto (entrenamiento, validación cruzada media y desvío, prueba)."""
    filas = []
    for nombre, gs in busquedas.items():
        mejor = gs.best_estimator_
        p = n_predictores(mejor)
        cv = metricas_cv(mejor, Xtr, ytr)
        params = {k.replace("modelo__", ""): v for k, v in gs.best_params_.items()}
        conjuntos = [("entrenamiento", metricas(ytr, mejor.predict(Xtr), p)),
                     ("validación cruzada (media)", cv.mean().to_dict()),
                     ("validación cruzada (desvío)", cv.std(ddof=1).to_dict()),
                     ("prueba", metricas(yte, mejor.predict(Xte), p))]
        for conj, m in conjuntos:
            filas.append({"modelo": nombre, "hiperparametros": str(params) if params else "-", "predictores": p,
                          "conjunto": conj, **m})
    return pd.DataFrame(filas)


def pivote(tabla, metrica):
    return tabla.pivot(index="modelo", columns="conjunto", values=metrica).reindex(list(HIPERPARAMETROS))


def diagnostico(tabla):
    """Sobreajuste o subajuste de cada modelo, comparando R² de entrenamiento contra prueba (y contra la CV)."""
    r2 = pivote(tabla, "R2")
    d = pd.DataFrame({"R2_entrenamiento": r2["entrenamiento"], "R2_cv": r2["validación cruzada (media)"],
                      "R2_prueba": r2["prueba"]})
    d["brecha_entrenamiento_prueba"] = d["R2_entrenamiento"] - d["R2_prueba"]
    d["brecha_entrenamiento_cv"] = d["R2_entrenamiento"] - d["R2_cv"]

    # Se miran las dos brechas: la prueba tiene solo 61 PON y por azar puede salir "fácil";
    # la validación cruzada promedia 5 particiones de 48 PON y es más estable.
    def leer(r):
        if r.R2_entrenamiento < UMBRAL_SUBAJUSTE:
            return "subajuste: sesgo alto (no aprende ni el entrenamiento)"
        if max(r.brecha_entrenamiento_prueba, r.brecha_entrenamiento_cv) > UMBRAL_BRECHA:
            return "sobreajuste: varianza alta (memoriza el entrenamiento)"
        return "ajuste razonable: sesgo y varianza equilibrados"
    d["diagnostico"] = d.apply(leer, axis=1)
    return d.reset_index()


def elegir_mejor(tabla):
    """El mejor se elige por RMSE medio de validación cruzada, nunca mirando la prueba."""
    rmse_cv = pivote(tabla, "RMSE")["validación cruzada (media)"].drop("Dummy (promedio)")
    return rmse_cv.idxmin()


def mejora_gridsearch(busquedas):
    """Espacio explorado y mejora: RMSE de CV con los valores por defecto de scikit-learn contra el mejor."""
    por_defecto = {"Ridge": {"modelo__alpha": 1},
                   "Random Forest": {"modelo__min_samples_leaf": 1, "modelo__max_depth": None},
                   "Gradient Boosting": {"modelo__learning_rate": 0.1, "modelo__max_depth": 3}}
    espacio, resumen = [], []
    for nombre, gs in busquedas.items():
        res = pd.DataFrame(gs.cv_results_)
        for i, r in res.iterrows():
            espacio.append({"modelo": nombre,
                            "hiperparametros": str({k.replace("modelo__", ""): v for k, v in r["params"].items()}) or "-",
                            "RMSE_cv": -r["mean_test_rmse"], "RMSE_cv_desvio": r["std_test_rmse"],
                            "MAE_cv": -r["mean_test_mae"], "R2_cv": r["mean_test_r2"],
                            "R2_entrenamiento_cv": r["mean_train_r2"], "ranking": r["rank_test_rmse"]})
        if nombre in por_defecto:
            i_def = next(i for i, p in enumerate(res["params"]) if p == por_defecto[nombre])
            rd, rb = -res.loc[i_def, "mean_test_rmse"], -res.loc[gs.best_index_, "mean_test_rmse"]
            resumen.append({"modelo": nombre, "combinaciones": len(res),
                            "RMSE_cv_por_defecto": rd, "RMSE_cv_mejor": rb, "mejora_pct": (rd - rb) / rd * 100,
                            "mejores_hiperparametros": str({k.replace("modelo__", ""): v for k, v in gs.best_params_.items()})})
    return pd.DataFrame(espacio), pd.DataFrame(resumen)


# ------------------------------------------------------------------ extras
def importancia(pipe, Xte, yte):
    """Importancia por permutación sobre la prueba: cuánto empeora el R² al mezclar cada variable original.
    Se calcula después de la evaluación final y no se usa para tomar ninguna decisión del modelo."""
    r = permutation_importance(pipe, Xte, yte, n_repeats=30, random_state=SEED, scoring="r2")
    return (pd.DataFrame({"variable": Xte.columns, "caida_R2_media": r.importances_mean, "caida_R2_desvio": r.importances_std})
            .sort_values("caida_R2_media", ascending=False).reset_index(drop=True))


def importancia_grupo(pipe, X, y, columnas, n_repeats=30):
    """Permuta varias columnas juntas (misma permutación de filas). Sirve para variables casi redundantes:
    si se mezcla solo una, la otra puede suplirla y la importancia individual engaña."""
    rng = np.random.RandomState(SEED)
    base = r2_score(y, pipe.predict(X))
    caidas = []
    for _ in range(n_repeats):
        Xp = X.copy()
        Xp[columnas] = X[columnas].values[rng.permutation(len(X))]
        caidas.append(base - r2_score(y, pipe.predict(Xp)))
    return float(np.mean(caidas)), float(np.std(caidas))


def comparar_shares(train, test):
    """Justificación de usar 5 proporciones de modelo y no las 22: Regresión Lineal con cada opción."""
    filas = []
    todas = [c for c in train.columns if c.startswith("share_")]
    for etiqueta, shares in [(f"{N_SHARES} modelos más usados", top_shares(train)), (f"los {len(todas)} modelos", todas)]:
        nums = NUMERICAS_BASE + shares
        cols = CATEGORICAS + nums
        gs = entrenar("Regresión Lineal", train[cols], train[OBJETIVO], nums)
        p = n_predictores(gs.best_estimator_)
        cv = metricas_cv(gs.best_estimator_, train[cols], train[OBJETIVO]).mean()
        te = metricas(test[OBJETIVO], gs.best_estimator_.predict(test[cols]), p)
        filas.append({"proporciones": etiqueta, "predictores": p, "R2_cv": cv["R2"], "R2_prueba": te["R2"],
                      "R2_ajustado_prueba": te["R2_ajustado"]})
    return pd.DataFrame(filas)


def coeficientes_lineales(pipe):
    """Coeficientes de un modelo lineal (variables numéricas escaladas: comparables entre sí)."""
    nombres = pipe.named_steps["prep"].get_feature_names_out()
    coef = pipe.named_steps["modelo"].coef_
    return (pd.DataFrame({"variable": [n.split("__", 1)[1] for n in nombres], "coeficiente": coef})
            .assign(abs=lambda d: d["coeficiente"].abs()).sort_values("abs", ascending=False).drop(columns="abs")
            .reset_index(drop=True))


def importancia_arboles(pipe):
    nombres = pipe.named_steps["prep"].get_feature_names_out()
    imp = pipe.named_steps["modelo"].feature_importances_
    return (pd.DataFrame({"variable": [n.split("__", 1)[1] for n in nombres], "importancia": imp})
            .sort_values("importancia", ascending=False).reset_index(drop=True))


def breusch_pagan(resid, pred):
    """Test de Breusch-Pagan (versión de Koenker) con el valor predicho como regresor:
    si el residuo² crece con la predicción, hay heterocedasticidad. LM = n·R² ~ chi²(1)."""
    e2 = resid ** 2
    r2_aux = np.corrcoef(pred, e2)[0, 1] ** 2
    lm = len(resid) * r2_aux
    return lm, stats.chi2.sf(lm, 1)


def analisis_residuos(pipe, Xtr, ytr, Xte, yte):
    """Residuos (real − predicho) del mejor modelo: fuera de muestra en el entrenamiento (CV) y en la prueba."""
    oof = cross_val_predict(clone(pipe), Xtr, ytr, cv=kfold())
    res = {}
    for nombre, y, yhat in [("cv_entrenamiento", ytr.values, oof), ("prueba", yte.values, pipe.predict(Xte))]:
        e = y - yhat
        sw = stats.shapiro(e)
        lm, p_bp = breusch_pagan(e, yhat)
        res[nombre] = {"n": len(e), "media": e.mean(), "desvio": e.std(ddof=1), "asimetria": stats.skew(e),
                       "shapiro_W": sw.statistic, "shapiro_p": sw.pvalue, "breusch_pagan_LM": lm, "breusch_pagan_p": p_bp}
    # patrón no capturado: PON chicos (pocas ONTs) tienen proporciones más extremas -> errores más grandes
    e_oof = ytr.values - oof
    rho = stats.spearmanr(Xtr["onts"], np.abs(e_oof))
    pequeños = Xtr["onts"] <= 5
    res["patrones"] = {
        "spearman_abs_residuo_vs_onts": rho.statistic, "spearman_p": rho.pvalue,
        "MAE_pon_5_onts_o_menos": float(np.abs(e_oof[pequeños.values]).mean()),
        "MAE_pon_mas_de_5_onts": float(np.abs(e_oof[~pequeños.values]).mean()),
        "n_pon_5_onts_o_menos": int(pequeños.sum()),
        "residuo_medio_por_localidad": pd.Series(e_oof, index=Xtr.index).groupby(Xtr["Localidad"]).mean().round(4).to_dict(),
    }
    return res, oof


def curva_aprendizaje(pipe, X, y):
    tam, tr, va = learning_curve(clone(pipe), X, y, cv=kfold(), train_sizes=np.linspace(0.3, 1.0, 8),
                                 scoring="neg_root_mean_squared_error", shuffle=True, random_state=SEED)
    return pd.DataFrame({"n_entrenamiento": tam, "RMSE_entrenamiento": -tr.mean(axis=1), "RMSE_entrenamiento_desvio": tr.std(axis=1),
                         "RMSE_validacion": -va.mean(axis=1), "RMSE_validacion_desvio": va.std(axis=1)})


# ------------------------------------------------------------------ prueba extra: datos de la OLT
def variables_olt(pons):
    """% de equipos online, distancia mediana (km) y potencia recibida mediana (dBm, solo online) por PON."""
    from olt import cargar_olt
    o = cargar_olt().dropna(subset=["Slot", "PON", "ID"]).copy()
    o["pon_key"] = (o["Localidad"] + "|" + o["Slot"].astype(int).astype(str) + "/|"
                    + o["PON"].astype(int).astype(str) + "/")
    online = o[o["Estado"].eq("Online")]
    v = pd.DataFrame({
        "olt_pct_online": o.groupby("pon_key")["Estado"].agg(lambda s: s.eq("Online").mean()),
        "olt_dist_mediana_km": o.groupby("pon_key")["Distancia_m"].median() / 1000,
        "olt_rxp_mediana_dbm": online.groupby("pon_key")["RXP_dBm"].median(),
    })
    return pons.merge(v, left_on="pon_key", right_index=True, how="left")


def prueba_olt(nombre, train, test, numericas):
    """Repite el mejor modelo (misma grilla, misma partición) sumando las variables de la OLT por PON."""
    tr, te = variables_olt(train), variables_olt(test)
    cols_base = CATEGORICAS + numericas
    cols_olt = cols_base + VARIABLES_OLT
    filas = []
    for etiqueta, cols, nums in [("sin OLT", cols_base, numericas), ("con OLT", cols_olt, numericas + VARIABLES_OLT)]:
        gs = entrenar(nombre, tr[cols], tr[OBJETIVO], nums)
        cv = metricas_cv(gs.best_estimator_, tr[cols], tr[OBJETIVO]).mean()
        p = n_predictores(gs.best_estimator_)
        te_m = metricas(te[OBJETIVO], gs.best_estimator_.predict(te[cols]), p)
        filas.append({"variables": etiqueta, "predictores": p, "R2_cv": cv["R2"], "MAE_cv": cv["MAE"], "RMSE_cv": cv["RMSE"],
                      "R2_prueba": te_m["R2"], "R2_ajustado_prueba": te_m["R2_ajustado"], "MAE_prueba": te_m["MAE"],
                      "RMSE_prueba": te_m["RMSE"]})
    cobertura = {"pon_con_datos_olt_entrenamiento": int(tr["olt_pct_online"].notna().sum()), "pon_entrenamiento": len(tr),
                 "pon_con_datos_olt_prueba": int(te["olt_pct_online"].notna().sum()), "pon_prueba": len(te),
                 "corr_spearman_con_objetivo": {v: float(stats.spearmanr(tr[v], tr[OBJETIVO], nan_policy="omit").statistic)
                                                for v in VARIABLES_OLT}}
    return pd.DataFrame(filas), cobertura


# ------------------------------------------------------------------ criterio SMART
def criterio_smart(tabla, mejor):
    te = pivote(tabla, "R2")["prueba"]
    r2aj = pivote(tabla, "R2_ajustado")["prueba"]
    mae = pivote(tabla, "MAE")["prueba"]
    mae_dummy = mae["Dummy (promedio)"]
    filas = [
        {"criterio": "R² en prueba", "umbral": f">= {META_R2}", "valor": te[mejor], "cumple": te[mejor] >= META_R2},
        {"criterio": "R² ajustado en prueba", "umbral": f">= {META_R2_AJ}", "valor": r2aj[mejor], "cumple": r2aj[mejor] >= META_R2_AJ},
        {"criterio": "MAE en prueba menor que el del Dummy", "umbral": f"< {mae_dummy:.3f}", "valor": mae[mejor],
         "cumple": mae[mejor] < mae_dummy},
    ]
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ figuras
def _c(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def fig_comparacion(tabla, mejor):
    modelos = list(HIPERPARAMETROS)
    etiquetas = ["Dummy\n(promedio)", "Regresión\nLineal", "Ridge", "Random\nForest", "Gradient\nBoosting"]
    conjuntos = [("entrenamiento", ACENTO_CLARO), ("validación cruzada (media)", "#6aa3e3"), ("prueba", ACENTO)]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.6))
    x = np.arange(len(modelos))
    for ax, met, nombre in zip(axes, ["RMSE", "MAE", "R2"], ["RMSE (menor es mejor)", "MAE (menor es mejor)", "R² (mayor es mejor)"]):
        pv = pivote(tabla, met)
        for j, (conj, color) in enumerate(conjuntos):
            xs = x + (j - 1) * 0.27
            ax.bar(xs, pv[conj], 0.27, color=color, label=conj.replace(" (media)", ""))
            for xi, v, m in zip(xs, pv[conj], modelos):
                ax.text(xi, max(v, 0) + 0.004, _c(v), ha="center", va="bottom", fontsize=8, rotation=90,
                        weight="bold" if (m == mejor and conj == "prueba") else "normal")
        ax.set_ylim(top=ax.get_ylim()[1] * 1.12)
        ax.axhline(pv.loc["Dummy (promedio)", "prueba"], color=TINTA2, ls="--", lw=1, label="Dummy en prueba")
        ax.set_xticks(x, etiquetas, fontsize=9)
        ax.set_title(nombre, fontsize=11)
        ax.axhline(0, color=GRIS, lw=0.8)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, fontsize=10)
    r2 = pivote(tabla, "R2")
    fig.suptitle(f"{mejor} gana en validación cruzada (R² {_c(r2.loc[mejor, 'validación cruzada (media)'])}; prueba "
                 f"{_c(r2.loc[mejor, 'prueba'])}). El Random Forest baja de {_c(r2.loc['Random Forest', 'entrenamiento'])} "
                 f"en entrenamiento a {_c(r2.loc['Random Forest', 'validación cruzada (media)'])} en validación",
                 x=0.01, ha="left", fontsize=12.5)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return fig


def fig_predicho_vs_real(busquedas, Xtr, ytr, Xte, yte, mejor):
    modelos = list(HIPERPARAMETROS)
    fig, axes = plt.subplots(2, 3, figsize=(14, 9.2))
    for ax, nombre in zip(axes.flat, modelos):
        m = busquedas[nombre].best_estimator_
        ax.scatter(ytr * 100, m.predict(Xtr) * 100, s=12, color=GRIS, alpha=0.7, label="entrenamiento")
        ax.scatter(yte * 100, m.predict(Xte) * 100, s=22, color=ACENTO, label="prueba")
        ax.plot([0, 100], [0, 100], color=TINTA2, ls="--", lw=1, label="predicción perfecta")
        r2 = r2_score(yte, m.predict(Xte))
        ax.set_title(f"{nombre}{' (mejor)' if nombre == mejor else ''}: R² prueba {_c(r2)}", fontsize=11,
                     weight="bold" if nombre == mejor else "normal")
        ax.set_xlim(-3, 103); ax.set_ylim(-10, 103)
        ax.set_xlabel("% real fuera de estándar en el PON"); ax.set_ylabel("% predicho")
    axes.flat[0].legend(frameon=False, fontsize=9, loc="upper left")
    axes.flat[-1].axis("off")
    axes.flat[-1].text(0, 0.6, "Cada punto es un puerto PON.\nGris: entrenamiento (240).\nAzul: prueba (61).\n\n"
                       "Cuanto más cerca de la diagonal,\nmejor la predicción.", fontsize=12, color=TINTA2, va="top")
    fig.suptitle("Los modelos siguen la tendencia pero achatan los extremos: sobreestiman los PON al día (0 %) "
                 "y subestiman los de 40 a 60 %",
                 x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    return fig


def fig_residuos(ytr, oof, yte, pred_te, res, mejor):
    e_tr, e_te = ytr.values - oof, yte.values - pred_te
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    bins = np.linspace(-0.6, 0.6, 31)
    a1.hist(e_tr * 100, bins=bins * 100, color=GRIS, label="fuera de muestra en entrenamiento (CV)")
    a1.hist(e_te * 100, bins=bins * 100, color=ACENTO, alpha=0.8, label="prueba")
    a1.axvline(0, color=TINTA2, lw=1)
    a1.set_xlabel("Residuo = real − predicho (puntos porcentuales)"); a1.set_ylabel("Cantidad de PON")
    a1.legend(frameon=False, fontsize=9)
    a1.set_title(f"Distribución (Shapiro-Wilk p = {_c(res['cv_entrenamiento']['shapiro_p'], 4)} en CV, "
                 f"{_c(res['prueba']['shapiro_p'], 3)} en prueba)", fontsize=10)
    a2.scatter(oof * 100, e_tr * 100, s=12, color=GRIS, label="CV entrenamiento")
    a2.scatter(pred_te * 100, e_te * 100, s=22, color=ACENTO, label="prueba")
    a2.axhline(0, color=TINTA2, lw=1)
    a2.set_xlabel("% predicho fuera de estándar"); a2.set_ylabel("Residuo (puntos porcentuales)")
    a2.set_title(f"Residuos contra predichos (Breusch-Pagan p = {_c(res['cv_entrenamiento']['breusch_pagan_p'], 3)} en CV)", fontsize=10)
    a2.legend(frameon=False, fontsize=9)
    normal = res["cv_entrenamiento"]["shapiro_p"] >= 0.05
    fig.suptitle(f"Residuos de {mejor}: centrados en cero, "
                 f"{'compatibles con normalidad' if normal else 'con colas más largas que una normal'} "
                 f"(asimetría {_c(res['cv_entrenamiento']['asimetria'])})", x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    return fig


def fig_curva_aprendizaje(curvas):
    fig, axes = plt.subplots(1, len(curvas), figsize=(6.5 * len(curvas), 5), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, (nombre, c) in zip(axes, curvas.items()):
        ax.plot(c["n_entrenamiento"], c["RMSE_entrenamiento"] * 100, "o-", color=ACENTO_CLARO, label="entrenamiento")
        ax.plot(c["n_entrenamiento"], c["RMSE_validacion"] * 100, "o-", color=ACENTO, label="validación")
        ax.fill_between(c["n_entrenamiento"], (c["RMSE_validacion"] - c["RMSE_validacion_desvio"]) * 100,
                        (c["RMSE_validacion"] + c["RMSE_validacion_desvio"]) * 100, color=ACENTO, alpha=0.12)
        ax.set_title(nombre, fontsize=11); ax.set_xlabel("PON usados para entrenar")
        brecha = (c["RMSE_validacion"] - c["RMSE_entrenamiento"]).iloc[-1] * 100
        ax.text(0.98, 0.95, f"brecha final: {_c(brecha, 1)} p.p.", transform=ax.transAxes, ha="right", va="top", fontsize=10, color=TINTA2)
    axes[0].set_ylabel("RMSE (puntos porcentuales)"); axes[0].legend(frameon=False)
    brechas = {n: (c["RMSE_validacion"] - c["RMSE_entrenamiento"]).iloc[-1] * 100 for n, c in curvas.items()}
    n_mejor, n_otro = list(curvas)[0], list(curvas)[-1]
    fig.suptitle(f"{n_mejor.split(' (')[0]} casi no tiene brecha ({_c(brechas[n_mejor], 1)} p.p.): su límite es el sesgo. "
                 f"{n_otro} conserva {_c(brechas[n_otro], 1)} p.p. de brecha: varianza",
                 x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    return fig


def fig_importancia(imp, mejor, grupo, corr_catv):
    """grupo = (caída media, desvío) al permutar juntas pct_catv y share_EG8143A5."""
    d = pd.concat([imp, pd.DataFrame([{"variable": "pct_catv + share_EG8143A5\n(mezcladas juntas)",
                                       "caida_R2_media": grupo[0], "caida_R2_desvio": grupo[1]}])])
    d = d.sort_values("caida_R2_media")
    fig, ax = plt.subplots(figsize=(11, 6.2))
    cols = ["#1b4f8f" if "juntas" in v else ACENTO if m > 0.02 else GRIS for v, m in zip(d["variable"], d["caida_R2_media"])]
    ax.barh(d["variable"], d["caida_R2_media"], xerr=d["caida_R2_desvio"], color=cols, error_kw={"ecolor": TINTA2, "lw": 0.8})
    for i, (v, s) in enumerate(zip(d["caida_R2_media"], d["caida_R2_desvio"])):
        ax.text(max(v, 0) + s + 0.012, i, _c(v, 3), va="center", fontsize=9)
    ax.set_xlabel("Caída del R² en prueba al mezclar la variable (importancia por permutación)")
    ax.set_xlim(right=d["caida_R2_media"].max() + d["caida_R2_desvio"].max() + 0.12)
    ax.set_title(f"{mejor}: lo que más pesa es el % de equipos con TV, que es casi lo mismo que la proporción de\n"
                 f"EG8143A5 (correlación {_c(corr_catv)}); le sigue la localidad",
                 loc="left", fontsize=11.5)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------ todo junto
def correr(guardar=True, verbose=True):
    """Corre el TP2 completo. Devuelve un dict con todos los objetos intermedios (lo usa el notebook)."""
    pons = cargar_pons()
    train, test = particion(pons)
    shares = top_shares(train)
    numericas = NUMERICAS_BASE + shares
    cols = CATEGORICAS + numericas
    assert not set(cols) & set(PROHIBIDAS), "fuga: hay una variable prohibida entre las entradas"
    Xtr, ytr, Xte, yte = train[cols], train[OBJETIVO], test[cols], test[OBJETIVO]

    busquedas = entrenar_todos(Xtr, ytr, numericas)
    tabla = tabla_metricas(busquedas, Xtr, ytr, Xte, yte)
    diag = diagnostico(tabla)
    mejor = elegir_mejor(tabla)
    espacio, mejora = mejora_gridsearch(busquedas)
    pipe = busquedas[mejor].best_estimator_
    imp = importancia(pipe, Xte, yte)
    grupo_catv = importancia_grupo(pipe, Xte, yte, ["pct_catv", "share_EG8143A5"])
    corr_catv = float(Xtr["pct_catv"].corr(Xtr["share_EG8143A5"]))
    comp_shares = comparar_shares(train, test)
    coef = coeficientes_lineales(busquedas["Regresión Lineal"].best_estimator_)
    imp_rf = importancia_arboles(busquedas["Random Forest"].best_estimator_)
    res, oof = analisis_residuos(pipe, Xtr, ytr, Xte, yte)
    curvas = {f"{mejor} (mejor)": curva_aprendizaje(pipe, Xtr, ytr)}
    if mejor != "Random Forest":
        curvas["Random Forest"] = curva_aprendizaje(busquedas["Random Forest"].best_estimator_, Xtr, ytr)
    olt_tabla, olt_cob = prueba_olt(mejor, train, test, numericas)
    smart = criterio_smart(tabla, mejor)

    r = dict(pons=pons, train=train, test=test, shares=shares, numericas=numericas, cols=cols,
             Xtr=Xtr, ytr=ytr, Xte=Xte, yte=yte, busquedas=busquedas, tabla=tabla, diag=diag, mejor=mejor,
             espacio=espacio, mejora=mejora, imp=imp, grupo_catv=grupo_catv, corr_catv=corr_catv,
             comp_shares=comp_shares, coef=coef, imp_rf=imp_rf, res=res, oof=oof, curvas=curvas,
             olt_tabla=olt_tabla, olt_cob=olt_cob, smart=smart)
    if guardar:
        guardar_todo(r)
    if verbose:
        with pd.option_context("display.width", 200, "display.max_columns", 20, "display.float_format", "{:.3f}".format):
            print(tabla[tabla["conjunto"].isin(["entrenamiento", "validación cruzada (media)", "prueba"])]
                  .drop(columns=["hiperparametros"]).to_string(index=False))
            print("\n", diag.to_string(index=False))
            print(f"\nMejor modelo (por RMSE de CV): {mejor}")
            print("\n", olt_tabla.to_string(index=False))
            print("\n", smart.to_string(index=False))
    return r


def guardar_todo(r):
    OUT.mkdir(parents=True, exist_ok=True)
    tabla, mejor = r["tabla"], r["mejor"]
    tabla.to_csv(OUT / "tabla_metricas.csv", index=False, encoding="utf-8-sig")
    r["diag"].to_csv(OUT / "diagnostico_ajuste.csv", index=False, encoding="utf-8-sig")
    r["espacio"].to_csv(OUT / "gridsearch_espacio.csv", index=False, encoding="utf-8-sig")
    r["mejora"].to_csv(OUT / "gridsearch_mejora.csv", index=False, encoding="utf-8-sig")
    r["imp"].to_csv(OUT / "importancia_permutacion.csv", index=False, encoding="utf-8-sig")
    r["coef"].to_csv(OUT / "coeficientes_regresion_lineal.csv", index=False, encoding="utf-8-sig")
    r["imp_rf"].to_csv(OUT / "importancia_random_forest.csv", index=False, encoding="utf-8-sig")
    r["olt_tabla"].to_csv(OUT / "prueba_olt.csv", index=False, encoding="utf-8-sig")
    r["smart"].to_csv(OUT / "criterio_smart.csv", index=False, encoding="utf-8-sig")
    r["comp_shares"].to_csv(OUT / "comparacion_5_vs_22_modelos.csv", index=False, encoding="utf-8-sig")
    for nombre, c in r["curvas"].items():
        c.assign(modelo=nombre).to_csv(OUT / f"curva_aprendizaje_{nombre.split(' (')[0].replace(' ', '_').lower()}.csv",
                                       index=False, encoding="utf-8-sig")

    # predicciones de prueba del mejor modelo (sirven para el gráfico 5 del cliente)
    pipe = r["busquedas"][mejor].best_estimator_
    pred = r["test"][["pon_key", "Localidad", "Slot", "PON", "onts", OBJETIVO]].assign(
        predicho=pipe.predict(r["Xte"]), residuo=lambda d: d[OBJETIVO] - d["predicho"])
    (RAIZ / "results").mkdir(exist_ok=True)
    pred.to_csv(RAIZ / "results" / "tp2_predicciones_prueba.csv", index=False, encoding="utf-8-sig")

    figs = {"tp2_comparacion_modelos.png": fig_comparacion(tabla, mejor),
            "tp2_predicho_vs_real.png": fig_predicho_vs_real(r["busquedas"], r["Xtr"], r["ytr"], r["Xte"], r["yte"], mejor),
            "tp2_residuos.png": fig_residuos(r["ytr"], r["oof"], r["yte"], pipe.predict(r["Xte"]), r["res"], mejor),
            "tp2_curva_aprendizaje.png": fig_curva_aprendizaje(r["curvas"]),
            "tp2_importancia_variables.png": fig_importancia(r["imp"], mejor, r["grupo_catv"], r["corr_catv"])}
    for nombre, fig in figs.items():
        guardar_figura(fig, nombre, carpeta=OUT); plt.close(fig)

    # todas las cifras del informe y del cuestionario, con una clave por objetivo
    def por_modelo(conj):
        return {m: {k: float(tabla[(tabla["modelo"] == m) & (tabla["conjunto"] == conj)][k].iloc[0])
                    for k in ["MSE", "RMSE", "MAE", "R2", "R2_ajustado"]} for m in HIPERPARAMETROS}
    y = r["pons"][OBJETIVO]
    guardar_metricas("obj09_tp2", {
        "datos": {"pon": len(r["pons"]), "entrenamiento": len(r["train"]), "prueba": len(r["test"]),
                  "objetivo_media": float(y.mean()), "objetivo_desvio": float(y.std()), "objetivo_mediana": float(y.median()),
                  "pon_con_0_pct": int((y == 0).sum()), "pon_con_100_pct": int((y == 1).sum())},
        "variables": {"categoricas": CATEGORICAS, "numericas": r["numericas"], "shares_top5": r["shares"],
                      "prohibidas": PROHIBIDAS, "predictores_efectivos": int(tabla["predictores"].max())},
        "hiperparametros_elegidos": {m: tabla[tabla["modelo"] == m]["hiperparametros"].iloc[0] for m in HIPERPARAMETROS},
        "entrenamiento": por_modelo("entrenamiento"), "cv_media": por_modelo("validación cruzada (media)"),
        "cv_desvio": por_modelo("validación cruzada (desvío)"), "prueba": por_modelo("prueba"),
        "diagnostico": {d.modelo: {"brecha_entrenamiento_prueba": d.brecha_entrenamiento_prueba,
                                   "brecha_entrenamiento_cv": d.brecha_entrenamiento_cv, "diagnostico": d.diagnostico}
                        for d in r["diag"].itertuples()},
        "umbrales_diagnostico": {"subajuste_R2_entrenamiento": UMBRAL_SUBAJUSTE, "sobreajuste_brecha": UMBRAL_BRECHA},
        "mejor_modelo": mejor,
        "gridsearch_mejora": r["mejora"].set_index("modelo").to_dict("index"),
        "importancia_permutacion": dict(zip(r["imp"]["variable"], r["imp"]["caida_R2_media"])),
        "importancia_pct_catv_y_share_EG8143A5_juntas": {"media": r["grupo_catv"][0], "desvio": r["grupo_catv"][1]},
        "correlacion_pct_catv_share_EG8143A5": r["corr_catv"],
        "comparacion_5_vs_22_modelos": r["comp_shares"].set_index("proporciones").to_dict("index"),
        "coeficientes_regresion_lineal_top5": dict(zip(r["coef"]["variable"].head(5), r["coef"]["coeficiente"].head(5))),
        "importancia_random_forest_top5": dict(zip(r["imp_rf"]["variable"].head(5), r["imp_rf"]["importancia"].head(5))),
        "residuos": r["res"],
        "curva_aprendizaje": {n: {"RMSE_validacion_inicio": float(c["RMSE_validacion"].iloc[0]),
                                  "RMSE_validacion_final": float(c["RMSE_validacion"].iloc[-1]),
                                  "RMSE_entrenamiento_final": float(c["RMSE_entrenamiento"].iloc[-1]),
                                  "brecha_final_pp": float((c["RMSE_validacion"].iloc[-1] - c["RMSE_entrenamiento"].iloc[-1]) * 100),
                                  "n_inicio": int(c["n_entrenamiento"].iloc[0]), "n_final": int(c["n_entrenamiento"].iloc[-1])}
                              for n, c in r["curvas"].items()},
        "prueba_olt": {"resultados": r["olt_tabla"].set_index("variables").to_dict("index"), **r["olt_cob"]},
        "criterio_smart": {"metas": {"R2_prueba": META_R2, "R2_ajustado_prueba": META_R2_AJ,
                                     "MAE_dummy_prueba": float(por_modelo("prueba")["Dummy (promedio)"]["MAE"])},
                           "resultados": {s.criterio: {"valor": s.valor, "cumple": s.cumple} for s in r["smart"].itertuples()},
                           "cumple_todo": bool(r["smart"]["cumple"].all())},
    })


def main():
    correr()
    from tp2_informe import escribir
    for ruta in escribir():
        print(f"Borrador: {ruta.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
