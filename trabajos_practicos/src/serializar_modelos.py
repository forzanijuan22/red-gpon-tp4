"""TP4: serializa (joblib) los modelos elegidos del TP2 y del TP3 para que la aplicación web los use sin reentrenar.

- modelos/tp2_ridge.joblib               Ridge del TP2 (pipeline completo: codificación + escalado + modelo)
- modelos/tp3_regresion_logistica.joblib Regresión logística del TP3 (pipeline completo)
- data/processed/tp3_clientes.csv        dataset del objetivo 14 sin datos sensibles (sin SN ni IP), con la partición

Cada archivo .joblib guarda un diccionario con el pipeline, las columnas de entrada en orden y las versiones usadas.
Se verifica que los modelos guardados reproduzcan exactamente las métricas de prueba del informe.
Correr:  python src/serializar_modelos.py"""
import ast
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score, mean_absolute_error, r2_score, roc_auc_score
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tp2_regresion as t2  # noqa: E402
import tp3_clasificacion as t3  # noqa: E402
from utils import METRICS, RAIZ, guardar_metricas  # noqa: E402

MODELOS = RAIZ / "modelos"
APP = RAIZ / "data" / "app"      # datos agregados que muestra la aplicación
COLUMNAS_TP3 = ["Localidad", "pon_key", "slot_n", "pon_n", "ID", "id_rel", "onts_pon", "Modelo_canonico", "Puertos_LAN",
                "WiFi_Tecnologia", "fw_generacion", "fw_fuera_estandar", "Distancia_m", "vec_rxp", "RXP_dBm", "en_riesgo"]


def tp2(m):
    """Ridge con los hiperparámetros elegidos por GridSearchCV, entrenado con los mismos 240 puertos del informe."""
    T = m["obj09_tp2"]
    train, test = t2.particion(t2.cargar_pons())
    num = T["variables"]["numericas"]
    columnas = t2.CATEGORICAS + num
    pipe = Pipeline([("prep", t2.preprocesador(num)),
                     ("modelo", Ridge(**ast.literal_eval(T["hiperparametros_elegidos"][T["mejor_modelo"]])))])
    pipe.fit(train[columnas], train[t2.OBJETIVO])
    pred = pipe.predict(test[columnas])
    r2, mae = r2_score(test[t2.OBJETIVO], pred), mean_absolute_error(test[t2.OBJETIVO], pred)
    assert np.isclose(r2, T["prueba"][T["mejor_modelo"]]["R2"]) and np.isclose(mae, T["prueba"][T["mejor_modelo"]]["MAE"]), \
        "el modelo serializado del TP2 no reproduce las métricas del informe"
    joblib.dump({"pipeline": pipe, "columnas": columnas, "objetivo": t2.OBJETIVO, "modelo": T["mejor_modelo"],
                 "sklearn": sklearn.__version__}, MODELOS / "tp2_ridge.joblib")
    return {"archivo": "modelos/tp2_ridge.joblib", "R2_prueba": r2, "MAE_prueba": mae}


def tp3(m):
    """Regresión logística con los hiperparámetros elegidos, entrenada con los mismos 3.899 clientes del informe."""
    T = m["obj14_tp3"]
    d = t3.cargar_datos()
    train, test = t3.particion(d)
    columnas = t3.CATEGORICAS + t3.NUMERICAS
    est = clone(t3.HIPERPARAMETROS[T["mejor_modelo"]][0]).set_params(**ast.literal_eval(T["hiperparametros_elegidos"][T["mejor_modelo"]]))
    pipe = Pipeline([("prep", t3.preprocesador()), ("modelo", est)]).fit(train[columnas], train[t3.OBJETIVO])
    proba = pipe.predict_proba(test[columnas])[:, 1]
    roc, pr = roc_auc_score(test[t3.OBJETIVO], proba), average_precision_score(test[t3.OBJETIVO], proba)
    assert np.isclose(roc, T["prueba"][T["mejor_modelo"]]["ROC_AUC"]) and np.isclose(pr, T["prueba"][T["mejor_modelo"]]["PR_AUC"]), \
        "el modelo serializado del TP3 no reproduce las métricas del informe"
    joblib.dump({"pipeline": pipe, "categoricas": t3.CATEGORICAS, "numericas": t3.NUMERICAS, "objetivo": t3.OBJETIVO,
                 "modelo": T["mejor_modelo"], "sklearn": sklearn.__version__}, MODELOS / "tp3_regresion_logistica.joblib")
    # dataset interno (sin SN ni IP) con la partición; lo usan las figuras del artículo, no la aplicación
    clientes = pd.concat([train[COLUMNAS_TP3].assign(conjunto="entrenamiento"), test[COLUMNAS_TP3].assign(conjunto="prueba")],
                         ignore_index=True)
    clientes.to_csv(RAIZ / "data" / "processed" / "tp3_clientes.csv", index=False, encoding="utf-8")
    datos_app(clientes, pipe.predict_proba(clientes[columnas])[:, 1], test[t3.OBJETIVO].to_numpy(), proba)
    return {"archivo": "modelos/tp3_regresion_logistica.joblib", "ROC_AUC_prueba": roc, "PR_AUC_prueba": pr,
            "clientes_en_csv": len(clientes)}


def datos_app(d, puntajes, y_prueba, proba_prueba):
    """Datos que muestra la aplicación, todos agregados: por puerto, por localidad, por modelo y por tramos de señal.
    No hay filas por equipo ni la señal de cada cliente; los puntajes del modelo van sin ubicación ni identificador."""
    APP.mkdir(parents=True, exist_ok=True)
    enc = {"index": False, "encoding": "utf-8"}
    onts = pd.read_csv(RAIZ / "data" / "processed" / "onts.csv", encoding="utf-8-sig")
    # TP1: equipos por modelo y por localidad
    (onts["Modelo_canonico"].value_counts().rename_axis("Modelo_canonico").reset_index(name="equipos")
     .to_csv(APP / "tp1_modelos.csv", **enc))
    (onts.groupby("Localidad").agg(equipos=("ID", "size"),
                                   pct_wifi4=("WiFi_Tecnologia", lambda s: s.str.startswith("Wi-Fi 4").mean() * 100),
                                   eg8141a5=("Modelo_canonico", lambda s: int((s == "EG8141A5").sum())))
     .reset_index().to_csv(APP / "tp1_localidades.csv", **enc))
    # TP3: un renglón por puerto (lo que necesita la pestaña «A qué puerto conectar»)
    (d.groupby("pon_key").agg(Localidad=("Localidad", "first"), slot_n=("slot_n", "first"), pon_n=("pon_n", "first"),
                              clientes=("ID", "size"), senal=("RXP_dBm", "mean"), en_riesgo=("en_riesgo", "mean"),
                              distancia=("Distancia_m", "median"), id_max=("ID", "max"))
     .reset_index().to_csv(APP / "tp3_puertos.csv", **enc))
    (d.groupby("Localidad").agg(clientes=("ID", "size"), en_riesgo=("en_riesgo", "mean"),
                                slot_moda=("slot_n", lambda s: int(s.mode().iloc[0])),
                                pon_moda=("pon_n", lambda s: int(s.mode().iloc[0])),
                                modelos=("Modelo_canonico", lambda s: "|".join(sorted(s.unique()))))
     .reset_index().to_csv(APP / "tp3_localidades.csv", **enc))
    (d.groupby("Modelo_canonico").agg(n=("ID", "size"), lan=("Puertos_LAN", "first"), wifi=("WiFi_Tecnologia", "first"),
                                      gen=("fw_generacion", lambda s: int(s.mode().iloc[0])))
     .sort_values("n", ascending=False).reset_index().to_csv(APP / "tp3_equipos.csv", **enc))
    # distribución de la señal en tramos de 0,5 dB y % en riesgo según la señal de los vecinos en tramos de 1 dB
    clase = np.where(d["RXP_dBm"] >= -25, "sin riesgo", np.where(d["RXP_dBm"] >= -27, "en riesgo", "degradada"))
    (pd.DataFrame({"desde_dBm": np.floor(d["RXP_dBm"] * 2) / 2, "clase": clase}).value_counts().rename("clientes")
     .reset_index().sort_values("desde_dBm").to_csv(APP / "tp3_histograma.csv", **enc))
    v = d.dropna(subset=["vec_rxp"])
    (v.groupby(np.floor(v["vec_rxp"]).rename("vecinos_desde_dBm"))
     .agg(clientes=("en_riesgo", "size"), pct_en_riesgo=("en_riesgo", "mean"))
     .reset_index().to_csv(APP / "tp3_vecinos.csv", **enc))
    # puntajes del modelo: referencia del percentil (todos los clientes) y prueba (para el umbral), ordenados
    pd.DataFrame({"puntaje": np.sort(puntajes)}).to_csv(APP / "tp3_referencia.csv", **enc)
    (pd.DataFrame({"puntaje": proba_prueba, "en_riesgo": y_prueba}).sort_values("puntaje", kind="stable")
     .to_csv(APP / "tp3_prueba.csv", **enc))
    rangos = {"clientes": int(len(d)), "en_riesgo": int(d["en_riesgo"].sum()), "pct_en_riesgo": float(d["en_riesgo"].mean()),
              "vec_min": float(d["vec_rxp"].min()), "vec_max": float(d["vec_rxp"].max()),
              "dist_max": float(d["Distancia_m"].max()), "onts_pon_max": int(d["onts_pon"].max())}
    (APP / "tp3_rangos.json").write_text(json.dumps(rangos, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    MODELOS.mkdir(exist_ok=True)
    m = json.loads(METRICS.read_text(encoding="utf-8"))
    r = {"tp2": tp2(m), "tp3": tp3(m), "sklearn": sklearn.__version__, "formato": "joblib"}
    guardar_metricas("tp4_despliegue", r)
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
