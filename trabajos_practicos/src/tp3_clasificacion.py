"""Fase 4, TP3 (objetivo 14): ¿el cliente tiene la señal de la fibra en riesgo? Clasificación binaria por ONT.

Cada fila es un equipo online que cruza con el inventario y tiene lectura válida (4872). Clase "en riesgo" = potencia
recibida < -25 dBm. Las funciones se usan paso a paso desde notebooks/TP3_clasificacion.ipynb; main() corre todo
de una vez para run_all.py. Las dos vías producen los mismos archivos y cifras."""
import sys
import time
from pathlib import Path

import matplotlib
if "ipykernel" not in sys.modules:   # en el notebook se deja el backend inline para ver las figuras
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, adjusted_rand_score, average_precision_score, balanced_accuracy_score,
                             classification_report, cohen_kappa_score, confusion_matrix, davies_bouldin_score, f1_score,
                             fbeta_score, precision_recall_curve, precision_score, recall_score, roc_auc_score, roc_curve,
                             silhouette_score)
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold, learning_curve
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, plot_tree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import RAIZ, guardar_figura, guardar_metricas  # noqa: E402

SEED = 42
OUT = RAIZ / "reports" / "TP3"
OBJETIVO = "en_riesgo"
GRUPO = "pon_key"
CATEGORICAS = ["Localidad", "Modelo_canonico", "Puertos_LAN", "WiFi_Tecnologia"]
NUMERICAS = ["slot_n", "pon_n", "ID", "id_rel", "onts_pon", "fw_generacion", "fw_fuera_estandar", "Distancia_m", "vec_rxp"]
PROHIBIDAS = ["RXP_dBm", "TXP_dBm", "Estado", "Nivel_senal", OBJETIVO]   # la señal y el estado del propio equipo son la respuesta

# Umbrales del criterio SMART (CLAUDE.md, Fase 4)
META_ROC, META_PR = 0.68, 0.22
# Convención del equipo para diagnosticar el ajuste (sobre ROC-AUC, que no depende del umbral)
UMBRAL_SUBAJUSTE = 0.68   # ROC-AUC de entrenamiento menor que la meta: no separa ni lo que ya vio
UMBRAL_BRECHA = 0.10      # ROC-AUC entrenamiento − validación (CV o prueba) mayor que esto: memoriza

INDIVIDUALES = ["Regresión Logística", "Árbol de Decisión", "KNN", "Naive Bayes"]
ENSAMBLES = ["Random Forest", "Gradient Boosting"]
REFERENCIAS = ["Dummy (prior)", "Regla de los vecinos"]

ACENTO, ACENTO_CLARO, GRIS, TINTA2, ROJO = "#2a78d6", "#9cc3ee", "#c9c7c0", "#52514e", "#c8463c"
COLORES = {"Regresión Logística": "#2a78d6", "Árbol de Decisión": "#7a5cc2", "KNN": "#2f9e8f", "Naive Bayes": "#d08a2e",
           "Random Forest": "#c8463c", "Gradient Boosting": "#8c6d46", "Dummy (prior)": "#a8a6a0",
           "Regla de los vecinos": "#0b0b0b"}
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})

HIPERPARAMETROS = {
    # nombre: (estimador, grilla, ¿umbral elegido en CV?, justificación)
    "Dummy (prior)": (
        DummyClassifier(strategy="prior"), {}, False,
        "Predice la proporción de la clase (11 %) para todos: siempre dice 'sin riesgo'. Es el piso."),
    "Regresión Logística": (
        LogisticRegression(class_weight="balanced", max_iter=3000), {"modelo__C": [0.01, 0.1, 1, 10]}, False,
        "Línea base de la consigna. C es la inversa de la regularización: con ~50 columnas one-hot conviene probar "
        "de mucha (0,01) a poca (10). class_weight='balanced' compensa el 11 % de clase positiva."),
    "Árbol de Decisión": (
        DecisionTreeClassifier(class_weight="balanced", random_state=SEED),
        {"modelo__max_depth": [3, 5, 8, None], "modelo__min_samples_leaf": [10, 50]}, False,
        "Interpretable (se puede dibujar). max_depth y min_samples_leaf limitan la memorización: sin límite, el "
        "árbol aprende cada equipo de entrenamiento."),
    "KNN": (
        KNeighborsClassifier(), {"modelo__n_neighbors": [15, 31, 51, 101], "modelo__weights": ["uniform", "distance"]}, True,
        "Clasifica según los k equipos más parecidos. k chico memoriza ruido; k grande suaviza. No tiene class_weight: "
        "el umbral de decisión se elige en validación cruzada."),
    "Naive Bayes": (
        GaussianNB(), {"modelo__var_smoothing": [1e-9, 1e-6, 1e-3, 1e-1]}, True,
        "Supone variables independientes y normales (one-hot denso). var_smoothing estabiliza las varianzas de las "
        "columnas binarias. Sin class_weight: umbral elegido en validación cruzada."),
    "Random Forest": (
        RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=SEED, n_jobs=-1),
        {"modelo__min_samples_leaf": [1, 5, 20], "modelo__max_depth": [None, 10]}, False,
        "Ensamble por bagging: 300 árboles sobre muestras distintas, que votan. Hojas mínimas y profundidad limitan "
        "la memorización."),
    "Gradient Boosting": (
        GradientBoostingClassifier(n_estimators=200, random_state=SEED),
        {"modelo__learning_rate": [0.05, 0.1], "modelo__max_depth": [2, 3]}, True,
        "Ensamble por boosting: 200 árboles chicos en secuencia, cada uno corrige al anterior. Sin class_weight: umbral "
        "elegido en validación cruzada."),
}
SUPERVISADOS = [n for n in HIPERPARAMETROS if n != "Dummy (prior)"]


# ------------------------------------------------------------------ datos y partición
def cargar_datos():
    """Dataset del objetivo 14 (sección 5 del CLAUDE.md) a partir de las ONTs de la Fase 1 y del listado de la OLT."""
    from olt import cargar_olt, preparar_obj14
    onts = pd.read_csv(RAIZ / "data" / "processed" / "onts.csv")
    return preparar_obj14(onts, cargar_olt())


def sgkf():
    return StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)


def particion(d):
    """Prueba = la primera de las 5 particiones de StratifiedGroupKFold (≈ 20 %): estratificada y separada por PON."""
    tr, te = next(sgkf().split(d, d[OBJETIVO], d[GRUPO]))
    train, test = d.iloc[tr].reset_index(drop=True), d.iloc[te].reset_index(drop=True)
    assert not set(train[GRUPO]) & set(test[GRUPO]), "hay PON en entrenamiento y en prueba a la vez"
    return train, test


def preprocesador():
    """One-hot denso (Naive Bayes no acepta matrices dispersas) y, para las numéricas, mediana + escalado."""
    num = Pipeline([("imputar", SimpleImputer(strategy="median")), ("escalar", StandardScaler())])
    return ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAS),
                              ("num", num, NUMERICAS)])


# ------------------------------------------------------------------ métricas
def metricas(y, proba, umbral):
    pred = (proba >= umbral).astype(int)
    return {"accuracy": accuracy_score(y, pred), "accuracy_balanceada": balanced_accuracy_score(y, pred),
            "precision": precision_score(y, pred, zero_division=0), "recall": recall_score(y, pred),
            "F1": f1_score(y, pred, zero_division=0), "F1_ponderado": f1_score(y, pred, average="weighted"),
            "kappa": cohen_kappa_score(y, pred), "ROC_AUC": roc_auc_score(y, proba),
            "PR_AUC": average_precision_score(y, proba)}


def umbral_f(y, proba, beta=1.0):
    """Umbral de probabilidad que maximiza F-beta (beta = 1: F1; beta = 2: el recall pesa el doble)."""
    p, r, t = precision_recall_curve(y, proba)
    f = (1 + beta ** 2) * p * r / np.where(beta ** 2 * p + r == 0, 1, beta ** 2 * p + r)
    i = int(np.nanargmax(f[:-1]))
    return float(t[i])


def proba_oof(pipe, X, y, g):
    """Probabilidades fuera de muestra (cada equipo predicho por un modelo que no lo vio), con el mismo agrupado."""
    out = np.zeros(len(y))
    for tr, va in sgkf().split(X, y, g):
        m = clone(pipe).fit(X.iloc[tr], y.iloc[tr])
        out[va] = m.predict_proba(X.iloc[va])[:, 1]
    return out


def metricas_cv(pipe, X, y, g, umbral, ajusta_umbral=False):
    """Métricas en cada partición de la validación cruzada. Si el modelo elige su umbral, se elige DENTRO de cada
    partición (probabilidades fuera de muestra de su parte de entrenamiento), para que la validación no lo vea."""
    filas = []
    for tr, va in sgkf().split(X, y, g):
        m = clone(pipe).fit(X.iloc[tr], y.iloc[tr])
        u = umbral_f(y.iloc[tr], proba_oof(pipe, X.iloc[tr], y.iloc[tr], g.iloc[tr])) if ajusta_umbral else umbral
        filas.append(metricas(y.iloc[va], m.predict_proba(X.iloc[va])[:, 1], u))
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ entrenamiento
def entrenar(nombre, X, y, g):
    """GridSearchCV con StratifiedGroupKFold sobre el entrenamiento. Elige por PR-AUC (la métrica que mejor refleja
    cuánto se detecta la clase chica) y reajusta con todo el entrenamiento."""
    est, grilla, ajusta_umbral, _ = HIPERPARAMETROS[nombre]
    pipe = Pipeline([("prep", preprocesador()), ("modelo", clone(est))])
    t0 = time.perf_counter()
    gs = GridSearchCV(pipe, grilla, cv=sgkf(), refit="pr_auc", return_train_score=True,
                      scoring={"pr_auc": "average_precision", "roc_auc": "roc_auc"})
    gs.fit(X, y, groups=g)
    gs.segundos_ = time.perf_counter() - t0
    gs.umbral_ = umbral_f(y, proba_oof(gs.best_estimator_, X, y, g)) if ajusta_umbral else 0.5
    return gs


def entrenar_todos(X, y, g):
    return {n: entrenar(n, X, y, g) for n in HIPERPARAMETROS}


def regla_vecinos(train, test):
    """Segunda referencia, sin ML: cuanto más débil la señal media de los vecinos del PON, más riesgo.
    Puntaje = −vec_rxp (los nulos se completan con la mediana del entrenamiento)."""
    med = train["vec_rxp"].median()
    return {conj: {"ROC_AUC": roc_auc_score(d[OBJETIVO], -d["vec_rxp"].fillna(med)),
                   "PR_AUC": average_precision_score(d[OBJETIVO], -d["vec_rxp"].fillna(med))}
            for conj, d in [("entrenamiento", train), ("prueba", test)]}


ORDEN_CONJUNTOS = ["entrenamiento", "validación cruzada (media)", "validación cruzada (desvío)", "prueba"]


def ordenar(tabla):
    """Orden fijo de filas (modelo, conjunto), para que el notebook y run_all.py guarden la misma tabla."""
    modelos = list(HIPERPARAMETROS) + ["Regla de los vecinos"]
    return (tabla.assign(_m=tabla["modelo"].map(modelos.index), _c=tabla["conjunto"].map(ORDEN_CONJUNTOS.index))
            .sort_values(["_m", "_c"]).drop(columns=["_m", "_c"]).reset_index(drop=True))


def tabla_metricas(busquedas, Xtr, ytr, gtr, Xte, yte, vecinos=None):
    """Tabla larga: modelo x conjunto (entrenamiento, validación cruzada media y desvío, prueba).
    vecinos = resultado de regla_vecinos(); si es None, no se agregan sus filas."""
    filas = []
    for nombre, gs in busquedas.items():
        m, u = gs.best_estimator_, gs.umbral_
        cv = metricas_cv(m, Xtr, ytr, gtr, u, ajusta_umbral=HIPERPARAMETROS[nombre][2])
        params = {k.replace("modelo__", ""): v for k, v in gs.best_params_.items()}
        tipo = "referencia" if nombre in REFERENCIAS else "ensamble" if nombre in ENSAMBLES else "individual"
        for conj, met in [("entrenamiento", metricas(ytr, m.predict_proba(Xtr)[:, 1], u)),
                          ("validación cruzada (media)", cv.mean().to_dict()),
                          ("validación cruzada (desvío)", cv.std(ddof=1).to_dict()),
                          ("prueba", metricas(yte, m.predict_proba(Xte)[:, 1], u))]:
            filas.append({"modelo": nombre, "tipo": tipo, "hiperparametros": str(params) if params else "-", "umbral": u,
                          "segundos_busqueda": gs.segundos_, "conjunto": conj, **met})
    for conj, met in (vecinos or {}).items():
        filas.append({"modelo": "Regla de los vecinos", "tipo": "referencia", "hiperparametros": "-", "umbral": np.nan,
                      "segundos_busqueda": 0.0, "conjunto": conj, **met})
    return ordenar(pd.DataFrame(filas))


def pivote(tabla, metrica, modelos=None):
    return tabla.pivot(index="modelo", columns="conjunto", values=metrica).reindex(modelos or list(HIPERPARAMETROS) + ["Regla de los vecinos"])


def diagnostico(tabla):
    roc = pivote(tabla, "ROC_AUC", list(HIPERPARAMETROS))
    d = pd.DataFrame({"ROC_entrenamiento": roc["entrenamiento"], "ROC_cv": roc["validación cruzada (media)"], "ROC_prueba": roc["prueba"]})
    d["brecha_entrenamiento_cv"] = d["ROC_entrenamiento"] - d["ROC_cv"]
    d["brecha_entrenamiento_prueba"] = d["ROC_entrenamiento"] - d["ROC_prueba"]

    def leer(r):
        if r.ROC_entrenamiento < UMBRAL_SUBAJUSTE:
            return "subajuste: sesgo alto (no separa ni el entrenamiento)"
        if max(r.brecha_entrenamiento_cv, r.brecha_entrenamiento_prueba) > UMBRAL_BRECHA:
            return "sobreajuste: varianza alta (memoriza el entrenamiento)"
        return "ajuste razonable: sesgo y varianza equilibrados"
    d["diagnostico"] = d.apply(leer, axis=1)
    return d.reset_index()


def elegir_mejor(tabla, candidatos=INDIVIDUALES):
    """El clasificador se elige entre los individuales (sección B de la consigna) por PR-AUC medio de validación
    cruzada, nunca mirando la prueba. Los ensambles son el plus (sección D.2) y se comparan contra el elegido."""
    pr = pivote(tabla, "PR_AUC", list(candidatos))["validación cruzada (media)"]
    return pr.idxmax()


def reportes_y_matrices(busquedas, Xtr, ytr, Xte, yte):
    """classification_report y matriz de confusión de cada modelo, en entrenamiento y en prueba."""
    reportes, matrices = [], {}
    for nombre, gs in busquedas.items():
        for conj, X, y in [("entrenamiento", Xtr, ytr), ("prueba", Xte, yte)]:
            pred = (gs.best_estimator_.predict_proba(X)[:, 1] >= gs.umbral_).astype(int)
            rep = classification_report(y, pred, target_names=["sin riesgo", "en riesgo"], output_dict=True, zero_division=0)
            for clase, v in rep.items():
                if isinstance(v, dict):
                    reportes.append({"modelo": nombre, "conjunto": conj, "clase": clase, **v})
            matrices[(nombre, conj)] = confusion_matrix(y, pred, labels=[0, 1])
    return pd.DataFrame(reportes), matrices


def mejora_gridsearch(busquedas):
    por_defecto = {"Regresión Logística": {"modelo__C": 1},
                   "Árbol de Decisión": {"modelo__max_depth": None, "modelo__min_samples_leaf": 10},
                   "KNN": {"modelo__n_neighbors": 15, "modelo__weights": "uniform"},
                   "Naive Bayes": {"modelo__var_smoothing": 1e-9},
                   "Random Forest": {"modelo__min_samples_leaf": 1, "modelo__max_depth": None},
                   "Gradient Boosting": {"modelo__learning_rate": 0.1, "modelo__max_depth": 3}}
    espacio, resumen = [], []
    for nombre, gs in busquedas.items():
        res = pd.DataFrame(gs.cv_results_)
        for _, r in res.iterrows():
            espacio.append({"modelo": nombre, "hiperparametros": str({k.replace("modelo__", ""): v for k, v in r["params"].items()}) or "-",
                            "PR_AUC_cv": r["mean_test_pr_auc"], "PR_AUC_cv_desvio": r["std_test_pr_auc"],
                            "ROC_AUC_cv": r["mean_test_roc_auc"], "ROC_AUC_entrenamiento_cv": r["mean_train_roc_auc"],
                            "ranking": r["rank_test_pr_auc"]})
        if nombre in por_defecto:
            i_def = next(i for i, p in enumerate(res["params"]) if p == por_defecto[nombre])
            pd_, pb = res.loc[i_def, "mean_test_pr_auc"], res.loc[gs.best_index_, "mean_test_pr_auc"]
            resumen.append({"modelo": nombre, "combinaciones": len(res), "referencia": str({k.replace("modelo__", ""): v for k, v in por_defecto[nombre].items()}),
                            "PR_AUC_cv_referencia": pd_, "PR_AUC_cv_mejor": pb, "mejora_puntos": pb - pd_,
                            "mejores_hiperparametros": str({k.replace("modelo__", ""): v for k, v in gs.best_params_.items()}),
                            "segundos_busqueda": gs.segundos_})
    return pd.DataFrame(espacio), pd.DataFrame(resumen)


# ------------------------------------------------------------------ extras
RECALL_OBJETIVO = 0.80   # punto de operación alternativo: detectar 8 de cada 10 clientes en riesgo


def analisis_umbral(pipe, Xtr, ytr, gtr, Xte, yte):
    """Umbral de decisión del mejor modelo, elegido en validación cruzada (probabilidades fuera de muestra):
    - F2 máximo: no detectar a un cliente en riesgo termina en reclamo, así que el recall pesa el doble;
    - el umbral más alto que todavía detecta el 80 % de los clientes en riesgo (punto de operación alternativo)."""
    oof = proba_oof(pipe, Xtr, ytr, gtr)
    p, r, t = precision_recall_curve(ytr, oof)
    curva = pd.DataFrame({"umbral": t, "precision": p[:-1], "recall": r[:-1]})
    u_f2 = umbral_f(ytr, oof, beta=2.0)
    u_r80 = float(curva.loc[curva["recall"] >= RECALL_OBJETIVO, "umbral"].max())
    pte = pipe.predict_proba(Xte)[:, 1]
    umbrales = {"0,5 (por defecto)": 0.5, "F2 máximo en CV": u_f2, "recall 80 % en CV": u_r80}
    comparacion = pd.DataFrame([{"umbral": nombre, "valor": u, "marcados": int((pte >= u).sum()), **metricas(yte, pte, u)}
                                for nombre, u in umbrales.items()])
    cms = {nombre: confusion_matrix(yte, (pte >= u).astype(int), labels=[0, 1]) for nombre, u in umbrales.items()}
    return curva, u_f2, comparacion, cms


def importancia(pipe, Xte, yte):
    """Importancia por permutación sobre la prueba (caída de PR-AUC). Se calcula después de la evaluación final."""
    r = permutation_importance(pipe, Xte, yte, n_repeats=15, random_state=SEED, scoring="average_precision", n_jobs=-1)
    return (pd.DataFrame({"variable": Xte.columns, "caida_PR_AUC_media": r.importances_mean, "caida_PR_AUC_desvio": r.importances_std})
            .sort_values("caida_PR_AUC_media", ascending=False).reset_index(drop=True))


def coeficientes_logistica(pipe):
    nombres = [n.split("__", 1)[1] for n in pipe.named_steps["prep"].get_feature_names_out()]
    coef = pipe.named_steps["modelo"].coef_[0]
    return (pd.DataFrame({"variable": nombres, "coeficiente": coef, "odds_ratio": np.exp(coef)})
            .assign(a=lambda d: d["coeficiente"].abs()).sort_values("a", ascending=False).drop(columns="a").reset_index(drop=True))


def curva_aprendizaje(pipe, X, y, g):
    tam, tr, va = learning_curve(clone(pipe), X, y, groups=g, cv=sgkf(), train_sizes=np.linspace(0.15, 1.0, 7),
                                 scoring="average_precision", shuffle=True, random_state=SEED, n_jobs=-1)
    return pd.DataFrame({"n_entrenamiento": tam, "PR_AUC_entrenamiento": tr.mean(axis=1), "PR_AUC_entrenamiento_desvio": tr.std(axis=1),
                         "PR_AUC_validacion": va.mean(axis=1), "PR_AUC_validacion_desvio": va.std(axis=1)})


# ------------------------------------------------------------------ plus: clustering
def clustering(d, ks=range(2, 9), k_extra=4):
    """K-Means con las mismas variables (one-hot + escaladas), sin la etiqueta. k de 2 a 8 por codo, silueta y
    Davies-Bouldin. Se usa todo el dataset: no hay etiqueta que pueda filtrarse."""
    Z = preprocesador().fit_transform(d[CATEGORICAS + NUMERICAS])
    filas, etiquetas = [], {}
    for k in ks:
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(Z)
        etiquetas[k] = km.labels_
        filas.append({"k": k, "inercia": km.inertia_, "silueta": silhouette_score(Z, km.labels_, random_state=SEED),
                      "davies_bouldin": davies_bouldin_score(Z, km.labels_), "ARI": adjusted_rand_score(d[OBJETIVO], km.labels_)})
    seleccion = pd.DataFrame(filas)
    k_mejor = int(seleccion.loc[seleccion["silueta"].idxmax(), "k"])

    def perfil(k):
        g = pd.DataFrame({"grupo": etiquetas[k], OBJETIVO: d[OBJETIVO].values, "vec_rxp": d["vec_rxp"].values,
                          "Distancia_m": d["Distancia_m"].values, "Localidad": d["Localidad"].values,
                          "Modelo_canonico": d["Modelo_canonico"].values})
        p = g.groupby("grupo").agg(equipos=(OBJETIVO, "size"), en_riesgo=(OBJETIVO, "sum"), pct_en_riesgo=(OBJETIVO, "mean"),
                                   vec_rxp_media=("vec_rxp", "mean"), distancia_mediana_m=("Distancia_m", "median"),
                                   localidad_principal=("Localidad", lambda s: s.mode().iloc[0]),
                                   pct_localidad_principal=("Localidad", lambda s: s.value_counts(normalize=True).iloc[0]),
                                   modelo_principal=("Modelo_canonico", lambda s: s.mode().iloc[0]))
        return p.reset_index()
    pca = PCA(n_components=2, random_state=SEED).fit(Z)
    return {"seleccion": seleccion, "k_mejor": k_mejor, "k_extra": k_extra, "perfil_mejor": perfil(k_mejor),
            "perfil_extra": perfil(k_extra), "etiquetas": etiquetas, "pca": pca.transform(Z),
            "pca_varianza": pca.explained_variance_ratio_}


# ------------------------------------------------------------------ criterio SMART
def criterio_smart(tabla, mejor):
    """Criterio sobre el clasificador elegido y, como control, sobre el que se elegiría entre todos (con ensambles)."""
    general = elegir_mejor(tabla, SUPERVISADOS)
    filas = []
    for rol, m in [("elegido (individual)", mejor)] + ([("mejor en CV entre todos", general)] if general != mejor else []):
        roc = pivote(tabla, "ROC_AUC")["prueba"][m]
        pr = pivote(tabla, "PR_AUC")["prueba"][m]
        filas += [{"modelo": m, "rol": rol, "criterio": "ROC-AUC en prueba", "umbral": f">= {META_ROC}", "valor": roc, "cumple": roc >= META_ROC},
                  {"modelo": m, "rol": rol, "criterio": "PR-AUC en prueba", "umbral": f">= {META_PR}", "valor": pr, "cumple": pr >= META_PR}]
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ figuras
def _c(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def fig_matrices(matrices, modelos, umbrales):
    """Una matriz de confusión por modelo (prueba), con cantidades y etiquetas en palabras."""
    n = len(modelos)
    cols = 4
    filas = int(np.ceil(n / cols))
    fig, axes = plt.subplots(filas, cols, figsize=(4.6 * cols, 4.4 * filas))
    textos = [["sin riesgo y el modelo\nlo dejó tranquilo", "sin riesgo pero el modelo\nlo marcó (falsa alarma)"],
              ["en riesgo y el modelo\nNO lo detectó", "en riesgo y el modelo\nlo detectó"]]
    for ax, nombre in zip(axes.flat, modelos):
        cm = matrices[(nombre, "prueba")]
        ax.imshow([[0, 1], [1, 0]], cmap=matplotlib.colors.ListedColormap(["#eef4fb", "#fbeceb"]))
        for i in range(2):
            for j in range(2):
                color = ACENTO if i == j else ROJO
                ax.text(j, i - 0.12, f"{cm[i, j]}", ha="center", va="center", fontsize=20, weight="bold", color=color)
                ax.text(j, i + 0.22, textos[i][j], ha="center", va="center", fontsize=7.5, color=TINTA2)
        rec = cm[1, 1] / cm[1].sum()
        ax.set_title(f"{nombre}\nencuentra {cm[1, 1]} de {cm[1].sum()} en riesgo ({_c(rec * 100, 0)} %), umbral {_c(umbrales[nombre])}",
                     fontsize=9.5)
        ax.set_xticks([0, 1], ["predice: sin riesgo", "predice: en riesgo"], fontsize=8)
        ax.set_yticks([0, 1], ["real: sin\nriesgo", "real: en\nriesgo"], fontsize=8)
        for s in ax.spines.values():
            s.set_visible(False)
    for ax in list(axes.flat)[n:]:
        ax.axis("off")
    fig.suptitle("Matrices de confusión en la prueba: los modelos con buen recall pagan con muchas falsas alarmas",
                 x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    return fig


def fig_comparacion(tabla, mejor):
    mods = INDIVIDUALES + ENSAMBLES + ["Dummy (prior)"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(16, 5.8), gridspec_kw={"width_ratios": [1.6, 1]})
    mets = [("accuracy", "accuracy"), ("precision", "precision"), ("recall", "recall"), ("F1", "F1")]
    x = np.arange(len(mods))
    w = 0.2
    paleta = ["#c9c7c0", "#9cc3ee", ACENTO, "#1b4f8f"]
    for j, ((met, etiqueta), color) in enumerate(zip(mets, paleta)):
        v = pivote(tabla, met, mods)["prueba"]
        a1.bar(x + (j - 1.5) * w, v, w, color=color, label=etiqueta)
        for xi, vi in zip(x + (j - 1.5) * w, v):
            a1.text(xi, vi + 0.01, _c(vi), ha="center", va="bottom", fontsize=7, rotation=90)
    a1.set_xticks(x, [m.replace(" ", "\n", 1) for m in mods], fontsize=9)
    a1.set_ylim(0, 1.12)
    a1.set_title("Clase 'en riesgo', en prueba (la accuracy alta del Dummy engaña: no detecta a nadie)", fontsize=10.5)
    a1.legend(frameon=False, ncol=4, fontsize=9, loc="upper right")
    mods2 = mods + ["Regla de los vecinos"]
    x2 = np.arange(len(mods2))
    roc, pr = pivote(tabla, "ROC_AUC", mods2)["prueba"], pivote(tabla, "PR_AUC", mods2)["prueba"]
    a2.barh(x2 + 0.2, roc, 0.4, color=ACENTO_CLARO, label="ROC-AUC")
    a2.barh(x2 - 0.2, pr, 0.4, color=ACENTO, label="PR-AUC")
    for xi, a, b in zip(x2, roc, pr):
        a2.text(a + 0.01, xi + 0.2, _c(a), va="center", fontsize=8)
        a2.text(b + 0.01, xi - 0.2, _c(b), va="center", fontsize=8)
    a2.axvline(META_ROC, color=TINTA2, ls="--", lw=1)
    a2.axvline(META_PR, color=TINTA2, ls=":", lw=1)
    a2.text(META_ROC, len(mods2) - 0.35, " meta ROC", fontsize=8, color=TINTA2)
    a2.text(META_PR, len(mods2) - 0.35, " meta PR", fontsize=8, color=TINTA2)
    a2.set_yticks(x2, [("» " if m == mejor else "") + m for m in mods2], fontsize=9)
    a2.invert_yaxis(); a2.set_xlim(0, 1.05)
    a2.legend(frameon=False, fontsize=9, loc="lower right")
    a2.set_title("Capacidad de ordenar por riesgo, en prueba", fontsize=10.5)
    v = pivote(tabla, "ROC_AUC")["prueba"]
    fig.suptitle(f"{mejor} gana en validación cruzada; la regla de los vecinos, sin ML, ordena casi igual "
                 f"(ROC-AUC {_c(v[mejor])} contra {_c(v['Regla de los vecinos'])} en prueba)", x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    return fig


def fig_curvas(busquedas, Xte, yte, test):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 6))
    curvas = {n: busquedas[n].best_estimator_.predict_proba(Xte)[:, 1] for n in INDIVIDUALES + ENSAMBLES}
    curvas["Regla de los vecinos"] = -test["vec_rxp"].fillna(test["vec_rxp"].median()).values
    for n, s in curvas.items():
        fpr, tpr, _ = roc_curve(yte, s)
        p, r, _ = precision_recall_curve(yte, s)
        ls = "--" if n == "Regla de los vecinos" else "-"
        a1.plot(fpr, tpr, ls, color=COLORES[n], lw=1.8, label=f"{n} (AUC {_c(roc_auc_score(yte, s))})")
        a2.plot(r, p, ls, color=COLORES[n], lw=1.8, label=f"{n} (AP {_c(average_precision_score(yte, s))})")
    a1.plot([0, 1], [0, 1], color=GRIS, lw=1, label="azar (0,50)")
    a2.axhline(yte.mean(), color=GRIS, lw=1, label=f"azar ({_c(yte.mean())})")
    a1.set_xlabel("Tasa de falsas alarmas (1 − especificidad)"); a1.set_ylabel("Recall: % de clientes en riesgo detectados")
    a2.set_xlabel("Recall: % de clientes en riesgo detectados"); a2.set_ylabel("Precisión: % de alarmas que eran reales")
    a1.set_title("Curvas ROC (prueba)", fontsize=11); a2.set_title("Curvas precisión-recall (prueba)", fontsize=11)
    a1.legend(frameon=False, fontsize=8.5, loc="lower right"); a2.legend(frameon=False, fontsize=8.5, loc="upper right")
    fig.suptitle("Todas las curvas quedan juntas y lejos de la esquina ideal: la señal depende de la fibra compartida, "
                 "no del equipo", x=0.01, ha="left", fontsize=12.5)
    fig.tight_layout()
    return fig


def fig_umbral(curva, comparacion, mejor):
    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    ax.plot(curva["umbral"], curva["precision"], color=GRIS, lw=2, label="precisión")
    ax.plot(curva["umbral"], curva["recall"], color=ACENTO, lw=2, label="recall")
    r = comparacion.set_index("umbral")
    for (nombre, fila), ls, y in zip(r.iterrows(), [":", "--", "-."], [0.97, 0.87, 0.77]):
        ax.axvline(fila["valor"], color=TINTA2, ls=ls, lw=1.2)
        ax.text(fila["valor"] + 0.005, y, f"{nombre}: {_c(fila['valor'])}", fontsize=9, color=TINTA2, va="top")
    ax.set_xlabel("Umbral de probabilidad para marcar 'en riesgo'"); ax.set_ylabel("Valor (validación cruzada, fuera de muestra)")
    ax.set_ylim(0, 1.02); ax.legend(frameon=False, loc="center right")
    a, b = r.loc["F2 máximo en CV"], r.loc[f"recall {_c(RECALL_OBJETIVO * 100, 0)} % en CV"]
    ax.set_title(f"{mejor}, en prueba: con el umbral elegido por F2 detecta {_c(a['recall'] * 100, 0)} de cada 100 clientes en riesgo "
                 f"marcando {int(a['marcados'])} equipos;\npara detectar {_c(b['recall'] * 100, 0)} hay que marcar "
                 f"{int(b['marcados'])} (solo {_c(b['precision'] * 100, 0)} de cada 100 alarmas serían reales)", loc="left", fontsize=11.5)
    fig.tight_layout()
    return fig


def fig_importancia(imp, mejor):
    d = imp.iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(d["variable"], d["caida_PR_AUC_media"], xerr=d["caida_PR_AUC_desvio"],
            color=[ACENTO if v > 0.01 else GRIS for v in d["caida_PR_AUC_media"]], error_kw={"ecolor": TINTA2, "lw": 0.8})
    for i, (v, s) in enumerate(zip(d["caida_PR_AUC_media"], d["caida_PR_AUC_desvio"])):
        ax.text(max(v, 0) + s + 0.004, i, _c(v, 3), va="center", fontsize=9)
    ax.set_xlabel("Caída de la PR-AUC en prueba al mezclar la variable (importancia por permutación)")
    top = imp.iloc[0]
    ax.set_title(f"{mejor}: casi todo lo aporta {top['variable']} (caída {_c(top['caida_PR_AUC_media'], 3)}); "
                 "el modelo de equipo y el firmware casi no suman", loc="left", fontsize=11.5)
    fig.tight_layout()
    return fig


def fig_curva_aprendizaje(curvas):
    fig, axes = plt.subplots(1, len(curvas), figsize=(6.5 * len(curvas), 5), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, (nombre, c) in zip(axes, curvas.items()):
        ax.plot(c["n_entrenamiento"], c["PR_AUC_entrenamiento"], "o-", color=ACENTO_CLARO, label="entrenamiento")
        ax.plot(c["n_entrenamiento"], c["PR_AUC_validacion"], "o-", color=ACENTO, label="validación")
        ax.fill_between(c["n_entrenamiento"], c["PR_AUC_validacion"] - c["PR_AUC_validacion_desvio"],
                        c["PR_AUC_validacion"] + c["PR_AUC_validacion_desvio"], color=ACENTO, alpha=0.12)
        ax.set_title(nombre, fontsize=11); ax.set_xlabel("Equipos usados para entrenar")
        b = (c["PR_AUC_entrenamiento"] - c["PR_AUC_validacion"]).iloc[-1]
        ax.text(0.98, 0.05, f"brecha final: {_c(b)}", transform=ax.transAxes, ha="right", fontsize=10, color=TINTA2)
    axes[0].set_ylabel("PR-AUC"); axes[0].legend(frameon=False)
    fig.suptitle("Más equipos casi no mejoran la validación: el límite está en la información, no en la cantidad de datos",
                 x=0.01, ha="left", fontsize=12.5)
    fig.tight_layout()
    return fig


def fig_arbol(gs):
    pipe = gs.best_estimator_
    nombres = [n.split("__", 1)[1] for n in pipe.named_steps["prep"].get_feature_names_out()]
    fig, ax = plt.subplots(figsize=(20, 8))
    plot_tree(pipe.named_steps["modelo"], max_depth=3, feature_names=nombres, class_names=["sin riesgo", "en riesgo"],
              filled=True, impurity=False, proportion=True, rounded=True, fontsize=8, ax=ax)
    ax.set_title("Árbol de decisión (primeros 3 niveles; numéricas escaladas: vec_rxp ≤ −1 = señal de vecinos 1 desvío "
                 "más débil que el promedio)", loc="left", fontsize=12)
    fig.tight_layout()
    return fig


def fig_clustering(cl, d):
    s = cl["seleccion"]
    fig = plt.figure(figsize=(17, 10))
    gsp = fig.add_gridspec(2, 3, height_ratios=[1, 1.35])
    for i, (col, nombre, mejor_alto) in enumerate([("inercia", "Codo (inercia)", None), ("silueta", "Silueta (mayor es mejor)", True),
                                                   ("davies_bouldin", "Davies-Bouldin (menor es mejor)", False)]):
        ax = fig.add_subplot(gsp[0, i])
        ax.plot(s["k"], s[col], "o-", color=ACENTO)
        ax.axvline(cl["k_mejor"], color=TINTA2, ls="--", lw=1)
        ax.set_title(nombre, fontsize=11); ax.set_xlabel("k (cantidad de grupos)")
    k = cl["k_mejor"]
    abajo = gsp[1, :].subgridspec(1, 2)
    for j, (titulo, colores) in enumerate([(f"Color por grupo (k = {k})", cl["etiquetas"][k]), ("Color por clase real", d[OBJETIVO].values)]):
        ax = fig.add_subplot(abajo[0, j])
        orden = np.argsort(colores) if j == 1 else np.arange(len(colores))   # los "en riesgo" se dibujan encima
        if j == 0:
            ax.scatter(cl["pca"][orden, 0], cl["pca"][orden, 1], c=colores[orden], cmap="tab10", s=5, alpha=0.6)
        else:
            ax.scatter(cl["pca"][orden, 0], cl["pca"][orden, 1], c=np.where(colores[orden] == 1, ROJO, GRIS), s=5, alpha=0.6)
            ax.scatter([], [], c=ROJO, label="en riesgo"); ax.scatter([], [], c=GRIS, label="sin riesgo")
            ax.legend(frameon=False, markerscale=3)
        ax.set_title(titulo, fontsize=11)
        ax.set_xlabel(f"PCA 1 ({_c(cl['pca_varianza'][0] * 100, 0)} % de la varianza)")
        ax.set_ylabel(f"PCA 2 ({_c(cl['pca_varianza'][1] * 100, 0)} %)")
    pe = cl["perfil_extra"]
    top = pe.loc[pe["pct_en_riesgo"].idxmax()]
    sil = s.set_index("k").loc[k, "silueta"]
    ari = s.set_index("k").loc[k, "ARI"]
    fig.suptitle(f"K-Means: el mejor k es {k} (silueta {_c(sil)}) y los grupos casi no coinciden con la clase (ARI {_c(ari)}). "
                 f"Con k = {cl['k_extra']}, un grupo de {int(top['equipos'])} equipos tiene {_c(top['pct_en_riesgo'] * 100, 0)} % en riesgo",
                 x=0.01, ha="left", fontsize=12.5)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------ todo junto
def correr(guardar=True, verbose=True):
    """Corre el TP3 completo. Devuelve un dict con todos los objetos intermedios (lo usa el notebook)."""
    d = cargar_datos()
    train, test = particion(d)
    cols = CATEGORICAS + NUMERICAS
    assert not set(cols) & set(PROHIBIDAS), "fuga: hay una variable prohibida entre las entradas"
    Xtr, ytr, gtr = train[cols], train[OBJETIVO], train[GRUPO]
    Xte, yte = test[cols], test[OBJETIVO]

    busquedas = entrenar_todos(Xtr, ytr, gtr)
    vecinos = regla_vecinos(train, test)
    tabla = tabla_metricas(busquedas, Xtr, ytr, gtr, Xte, yte, vecinos)
    diag = diagnostico(tabla)
    mejor = elegir_mejor(tabla)
    reportes, matrices = reportes_y_matrices(busquedas, Xtr, ytr, Xte, yte)
    espacio, mejora = mejora_gridsearch(busquedas)
    pipe = busquedas[mejor].best_estimator_
    curva_u, u_f2, comp_u, cm_u = analisis_umbral(pipe, Xtr, ytr, gtr, Xte, yte)
    imp = importancia(pipe, Xte, yte)
    coef = coeficientes_logistica(busquedas["Regresión Logística"].best_estimator_)
    curvas = {f"{mejor} (mejor)": curva_aprendizaje(pipe, Xtr, ytr, gtr)}
    if mejor != "Random Forest":
        curvas["Random Forest"] = curva_aprendizaje(busquedas["Random Forest"].best_estimator_, Xtr, ytr, gtr)
    cl = clustering(d)
    smart = criterio_smart(tabla, mejor)

    r = dict(d=d, train=train, test=test, cols=cols, Xtr=Xtr, ytr=ytr, gtr=gtr, Xte=Xte, yte=yte, busquedas=busquedas,
             vecinos=vecinos, tabla=tabla, diag=diag, mejor=mejor, reportes=reportes, matrices=matrices, espacio=espacio,
             mejora=mejora, curva_u=curva_u, u_f2=u_f2, comp_u=comp_u, cm_u=cm_u, imp=imp, coef=coef, curvas=curvas,
             cl=cl, smart=smart)
    if guardar:
        guardar_todo(r)
    if verbose:
        with pd.option_context("display.width", 220, "display.max_columns", 30, "display.float_format", "{:.3f}".format):
            t = tabla[tabla["conjunto"].isin(["entrenamiento", "validación cruzada (media)", "prueba"])]
            print(t.drop(columns=["hiperparametros", "tipo", "segundos_busqueda"]).to_string(index=False))
            print("\n", diag.to_string(index=False))
            print(f"\nMejor (PR-AUC de CV): {mejor}")
            print("\n", comp_u.to_string(index=False))
            print("\n", cl["seleccion"].to_string(index=False))
            print("\n", cl["perfil_extra"].to_string(index=False))
            print("\n", smart.to_string(index=False))
    return r


def guardar_todo(r):
    OUT.mkdir(parents=True, exist_ok=True)
    tabla, mejor, cl = r["tabla"], r["mejor"], r["cl"]
    enc = {"index": False, "encoding": "utf-8-sig"}
    tabla.to_csv(OUT / "tabla_metricas.csv", **enc)
    r["diag"].to_csv(OUT / "diagnostico_ajuste.csv", **enc)
    r["reportes"].to_csv(OUT / "classification_report.csv", **enc)
    pd.DataFrame([{"modelo": n, "conjunto": c, "verdaderos_negativos": m[0, 0], "falsas_alarmas": m[0, 1],
                   "en_riesgo_no_detectados": m[1, 0], "en_riesgo_detectados": m[1, 1]}
                  for (n, c), m in r["matrices"].items()]).to_csv(OUT / "matrices_confusion.csv", **enc)
    r["espacio"].to_csv(OUT / "gridsearch_espacio.csv", **enc)
    r["mejora"].to_csv(OUT / "gridsearch_mejora.csv", **enc)
    r["comp_u"].to_csv(OUT / "umbral_decision.csv", **enc)
    r["imp"].to_csv(OUT / "importancia_permutacion.csv", **enc)
    r["coef"].to_csv(OUT / "coeficientes_regresion_logistica.csv", **enc)
    cl["seleccion"].to_csv(OUT / "clustering_seleccion_k.csv", **enc)
    cl["perfil_mejor"].to_csv(OUT / f"clustering_perfil_k{cl['k_mejor']}.csv", **enc)
    cl["perfil_extra"].to_csv(OUT / f"clustering_perfil_k{cl['k_extra']}.csv", **enc)
    r["smart"].to_csv(OUT / "criterio_smart.csv", **enc)
    for nombre, c in r["curvas"].items():
        c.assign(modelo=nombre).to_csv(OUT / f"curva_aprendizaje_{nombre.split(' (')[0].replace(' ', '_').lower()}.csv", **enc)

    # predicciones de prueba del mejor modelo, sin SN ni IP (sirven para el gráfico 6 del cliente)
    pipe = r["busquedas"][mejor].best_estimator_
    pred = r["test"][["Localidad", "slot_n", "pon_n", "ID", "Modelo_canonico", OBJETIVO]].assign(
        probabilidad=pipe.predict_proba(r["Xte"])[:, 1],
        marcado_umbral_f2=lambda x: (x["probabilidad"] >= r["u_f2"]).astype(int))
    (RAIZ / "results").mkdir(exist_ok=True)
    pred.to_csv(RAIZ / "results" / "tp3_predicciones_prueba.csv", **enc)

    umbrales = {n: gs.umbral_ for n, gs in r["busquedas"].items()}
    figs = {"tp3_matrices_confusion.png": fig_matrices(r["matrices"], INDIVIDUALES + ENSAMBLES + ["Dummy (prior)"], umbrales),
            "tp3_comparacion_modelos.png": fig_comparacion(tabla, mejor),
            "tp3_curvas_roc_pr.png": fig_curvas(r["busquedas"], r["Xte"], r["yte"], r["test"]),
            "tp3_umbral_decision.png": fig_umbral(r["curva_u"], r["comp_u"], mejor),
            "tp3_importancia_variables.png": fig_importancia(r["imp"], mejor),
            "tp3_curva_aprendizaje.png": fig_curva_aprendizaje(r["curvas"]),
            "tp3_arbol.png": fig_arbol(r["busquedas"]["Árbol de Decisión"]),
            "tp3_clustering.png": fig_clustering(cl, r["d"])}
    for nombre, fig in figs.items():
        guardar_figura(fig, nombre, carpeta=OUT); plt.close(fig)

    def por_modelo(conj, modelos):
        mets = ["accuracy", "accuracy_balanceada", "precision", "recall", "F1", "F1_ponderado", "kappa", "ROC_AUC", "PR_AUC"]
        out = {}
        for m in modelos:
            fila = tabla[(tabla["modelo"] == m) & (tabla["conjunto"] == conj)]
            if len(fila):
                out[m] = {k: float(fila[k].iloc[0]) for k in mets if pd.notna(fila[k].iloc[0])}
        return out
    todos = list(HIPERPARAMETROS) + ["Regla de los vecinos"]
    d, tr, te = r["d"], r["train"], r["test"]
    s = cl["seleccion"].set_index("k")
    guardar_metricas("obj14_tp3", {
        "datos": {"equipos": len(d), "en_riesgo": int(d[OBJETIVO].sum()), "pct_en_riesgo": float(d[OBJETIVO].mean()),
                  "pon": int(d[GRUPO].nunique()), "entrenamiento": len(tr), "prueba": len(te),
                  "pon_entrenamiento": int(tr[GRUPO].nunique()), "pon_prueba": int(te[GRUPO].nunique()),
                  "pct_en_riesgo_entrenamiento": float(tr[OBJETIVO].mean()), "pct_en_riesgo_prueba": float(te[OBJETIVO].mean()),
                  "vec_rxp_nulos": int(d["vec_rxp"].isna().sum())},
        "variables": {"categoricas": CATEGORICAS, "numericas": NUMERICAS, "prohibidas": PROHIBIDAS},
        "hiperparametros_elegidos": {n: tabla[tabla["modelo"] == n]["hiperparametros"].iloc[0] for n in HIPERPARAMETROS},
        "umbrales": umbrales,
        # efecto del desbalance: los modelos sin class_weight, con el umbral 0,5 por defecto, casi no detectan la clase chica
        "recall_prueba_con_umbral_05": {n: float(recall_score(r["yte"], (gs.best_estimator_.predict_proba(r["Xte"])[:, 1] >= 0.5).astype(int)))
                                        for n, gs in r["busquedas"].items() if gs.umbral_ != 0.5},
        "segundos_busqueda": {n: gs.segundos_ for n, gs in r["busquedas"].items()},
        "entrenamiento": por_modelo("entrenamiento", todos), "cv_media": por_modelo("validación cruzada (media)", todos),
        "cv_desvio": por_modelo("validación cruzada (desvío)", todos), "prueba": por_modelo("prueba", todos),
        "matrices_confusion_prueba": {n: r["matrices"][(n, "prueba")].tolist() for n in HIPERPARAMETROS},
        "diagnostico": {x.modelo: {"brecha_entrenamiento_cv": x.brecha_entrenamiento_cv,
                                   "brecha_entrenamiento_prueba": x.brecha_entrenamiento_prueba, "diagnostico": x.diagnostico}
                        for x in r["diag"].itertuples()},
        "umbrales_diagnostico": {"subajuste_ROC_entrenamiento": UMBRAL_SUBAJUSTE, "sobreajuste_brecha": UMBRAL_BRECHA},
        "mejor_modelo": mejor,
        "gridsearch_mejora": r["mejora"].set_index("modelo").to_dict("index"),
        "umbral_decision": {"umbral_f2": r["u_f2"], "recall_objetivo": RECALL_OBJETIVO,
                            "comparacion_prueba": r["comp_u"].set_index("umbral").to_dict("index"),
                            "matrices_confusion_prueba": {k: v.tolist() for k, v in r["cm_u"].items()}},
        "importancia_permutacion": dict(zip(r["imp"]["variable"], r["imp"]["caida_PR_AUC_media"])),
        "coeficientes_logistica_top8": dict(zip(r["coef"]["variable"].head(8), r["coef"]["coeficiente"].head(8))),
        "curva_aprendizaje": {n: {"PR_AUC_validacion_inicio": float(c["PR_AUC_validacion"].iloc[0]),
                                  "PR_AUC_validacion_final": float(c["PR_AUC_validacion"].iloc[-1]),
                                  "PR_AUC_entrenamiento_final": float(c["PR_AUC_entrenamiento"].iloc[-1]),
                                  "n_inicio": int(c["n_entrenamiento"].iloc[0]), "n_final": int(c["n_entrenamiento"].iloc[-1])}
                              for n, c in r["curvas"].items()},
        "clustering": {"k_mejor": cl["k_mejor"], "k_extra": cl["k_extra"],
                       "silueta": s["silueta"].to_dict(), "davies_bouldin": s["davies_bouldin"].to_dict(), "ARI": s["ARI"].to_dict(),
                       "pca_varianza": [float(v) for v in cl["pca_varianza"]],
                       "perfil_mejor": cl["perfil_mejor"].set_index("grupo").to_dict("index"),
                       "perfil_extra": cl["perfil_extra"].set_index("grupo").to_dict("index")},
        "mejor_entre_todos_cv": elegir_mejor(tabla, SUPERVISADOS),
        "criterio_smart": {"metas": {"ROC_AUC_prueba": META_ROC, "PR_AUC_prueba": META_PR},
                           "resultados": {f"{x.modelo} | {x.criterio}": {"rol": x.rol, "valor": x.valor, "cumple": x.cumple}
                                          for x in r["smart"].itertuples()},
                           "cumple_todo": bool(r["smart"][r["smart"]["rol"] == "elegido (individual)"]["cumple"].all())},
    })


def main():
    correr()
    from tp3_informe import escribir
    for ruta in escribir():
        print(f"Borrador: {ruta.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
