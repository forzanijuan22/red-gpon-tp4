"""Borradores del informe y del cuestionario del TP3, generados desde results/metrics.json.
Ninguna cifra se escribe a mano: si se vuelve a correr el modelo, los borradores se actualizan solos."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import METRICS, RAIZ  # noqa: E402

OUT = RAIZ / "reports" / "TP3"
INDIVIDUALES = ["Regresión Logística", "Árbol de Decisión", "KNN", "Naive Bayes"]
ENSAMBLES = ["Random Forest", "Gradient Boosting"]
DUMMY, VECINOS = "Dummy (prior)", "Regla de los vecinos"


def c(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def pct(x, d=0):
    return f"{x * 100:.{d}f} %".replace(".", ",")


def tablas_md(m):
    mods = INDIVIDUALES + ENSAMBLES + [DUMMY]
    t1 = ["| Modelo | Hiperparámetros | Umbral | Accuracy | Acc. balanceada | Precisión | Recall | F1 | F1 ponderado | Kappa | ROC-AUC | PR-AUC |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n in mods:
        p = m["prueba"][n]
        t1.append(f"| {n} | {m['hiperparametros_elegidos'][n]} | {c(m['umbrales'][n])} | {c(p['accuracy'])} | "
                  f"{c(p['accuracy_balanceada'])} | {c(p['precision'])} | {c(p['recall'])} | {c(p['F1'])} | {c(p['F1_ponderado'])} | "
                  f"{c(p['kappa'])} | {c(p['ROC_AUC'])} | {c(p['PR_AUC'])} |")
    v = m["prueba"][VECINOS]
    t1.append(f"| {VECINOS} (sin ML) | puntaje = −vec_rxp | - | - | - | - | - | - | - | - | {c(v['ROC_AUC'])} | {c(v['PR_AUC'])} |")

    t2 = ["| Modelo | ROC-AUC entrenamiento | ROC-AUC CV (media ± desvío) | ROC-AUC prueba | PR-AUC entrenamiento | PR-AUC CV | PR-AUC prueba | F1 ent. | F1 prueba | Diagnóstico |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for n in mods:
        e, cv, sd, p = m["entrenamiento"][n], m["cv_media"][n], m["cv_desvio"][n], m["prueba"][n]
        t2.append(f"| {n} | {c(e['ROC_AUC'])} | {c(cv['ROC_AUC'])} ± {c(sd['ROC_AUC'])} | {c(p['ROC_AUC'])} | {c(e['PR_AUC'])} | "
                  f"{c(cv['PR_AUC'])} ± {c(sd['PR_AUC'])} | {c(p['PR_AUC'])} | {c(e['F1'])} | {c(p['F1'])} | "
                  f"{m['diagnostico'][n]['diagnostico'].split(':')[0]} |")

    t3 = ["| Modelo | En riesgo detectados | En riesgo NO detectados | Falsas alarmas | Sin riesgo bien clasificados |", "|---|---|---|---|---|"]
    for n in mods:
        (tn, fp), (fn, tp) = m["matrices_confusion_prueba"][n]
        t3.append(f"| {n} | {tp} | {fn} | {fp} | {tn} |")
    return "\n".join(t1), "\n".join(t2), "\n".join(t3)


def respuestas(m):
    mejor = m["mejor_modelo"]
    p, cv, sd, e = m["prueba"], m["cv_media"], m["cv_desvio"], m["entrenamiento"]
    modelos = INDIVIDUALES + ENSAMBLES
    max_rec = max(modelos, key=lambda n: p[n]["recall"])
    max_prec = max(modelos, key=lambda n: p[n]["precision"])
    (tn, fp), (fn, tp) = m["matrices_confusion_prueba"][mejor]
    (tn_p, fp_p), (fn_p, tp_p) = m["matrices_confusion_prueba"][max_prec]
    v = p[VECINOS]
    u = m["umbral_decision"]
    r80 = u["comparacion_prueba"][next(k for k in u["comparacion_prueba"] if k.startswith("recall"))]
    f2 = u["comparacion_prueba"]["F2 máximo en CV"]
    d = m["datos"]
    sobre = [n for n in modelos if m["diagnostico"][n]["diagnostico"].startswith("sobreajuste")]
    equil = [n for n in modelos if m["diagnostico"][n]["diagnostico"].startswith("ajuste")]
    r05 = m["recall_prueba_con_umbral_05"]
    gs = m["gridsearch_mejora"]
    imp = m["importancia_permutacion"]
    top_var = max(imp, key=imp.get)
    resto = sorted(((k, x) for k, x in imp.items() if k != top_var), key=lambda t: -t[1])
    cl = m["clustering"]
    kb, kx = str(cl["k_mejor"]), cl["k_extra"]
    pe = cl["perfil_extra"]
    g_top = max(pe, key=lambda g: pe[g]["pct_en_riesgo"])
    otros = [pe[g]["pct_en_riesgo"] for g in pe if g != g_top]
    rf, gb = "Random Forest", "Gradient Boosting"
    seg = m["segundos_busqueda"]
    general = m["mejor_entre_todos_cv"]
    vecinos_gana = v["ROC_AUC"] >= p[mejor]["ROC_AUC"] and v["PR_AUC"] >= p[mejor]["PR_AUC"]

    p1 = f"""**1. ¿Cuál es el clasificador más adecuado? ¿Cambia si se prioriza el recall o la precisión?**

El elegido es la **{mejor}**. Tiene la mayor PR-AUC media en validación cruzada entre los cuatro clasificadores
individuales ({c(cv[mejor]['PR_AUC'])} ± {c(sd[mejor]['PR_AUC'])}), y la elección se hizo sin mirar la prueba. En prueba
obtiene ROC-AUC {c(p[mejor]['ROC_AUC'])} y PR-AUC {c(p[mejor]['PR_AUC'])}; el azar da {c(p[DUMMY]['PR_AUC'])}. Con el umbral 0,5:
- detecta **{tp} de los {tp + fn} clientes en riesgo** (recall {c(p[mejor]['recall'])});
- a cambio, da **{fp} falsas alarmas** (precisión {c(p[mejor]['precision'])}).

**La elección sí depende de qué se priorice.**
- **Recall.** {'La ' + mejor + ' es' if max_rec == mejor else max_rec + ' es'} el modelo que más clientes en riesgo encuentra en
  prueba (recall {c(p[max_rec]['recall'])}).
- **Precisión.** Si importa no mandar técnicos de más, gana el {max_prec} (precisión {c(p[max_prec]['precision'])}): detecta
  {tp_p} y da solo {fp_p} falsas alarmas. Pero deja sin detectar a {fn_p} de {tp_p + fn_p} clientes en riesgo.

En este problema un cliente en riesgo no detectado termina en reclamo, así que **conviene priorizar el recall**. El análisis
del umbral muestra el costo:
- **Con el umbral que maximiza F2** ({c(u['umbral_f2'])}, casi igual a 0,5 porque `class_weight="balanced"` ya lo corre), se
  marcan {f2['marcados']} equipos y se detecta el {pct(f2['recall'])}.
- **Para detectar el {pct(u['recall_objetivo'])} en validación cruzada**, hay que bajar el umbral. En prueba eso da recall
  {c(r80['recall'])}, pero marca {r80['marcados']} de {d['prueba']} equipos y solo {pct(r80['precision'])} de las alarmas
  son reales.

**Hallazgo: la regla de los vecinos.** La regla sin ML, que ordena a los clientes por la señal media de sus vecinos de
PON, da ROC-AUC {c(v['ROC_AUC'])} y PR-AUC {c(v['PR_AUC'])} en prueba. Es {'igual o apenas mejor que' if vecinos_gana else 'casi igual a'}
la {mejor}. Toda la información útil está en la fibra compartida del puerto: el modelo de equipo, el firmware y la
distancia casi no agregan nada."""

    p2 = f"""**2. ¿Hubo sobreajuste o subajuste? ¿Qué impacto tuvo el desbalance?**

**Sobreajustan {', '.join(sobre)}.** Se detecta comparando la ROC-AUC de entrenamiento con la de validación cruzada
(agrupada por PON) y con la de prueba:
""" + "\n".join(f"- {n}: {c(e[n]['ROC_AUC'])} en entrenamiento contra {c(cv[n]['ROC_AUC'])} en validación cruzada." for n in sobre) + f"""

Es varianza alta: aprenden características de los PON de entrenamiento que no se repiten en PON nuevos. El caso extremo
es el KNN con `weights="distance"`, que en entrenamiento se reconoce a sí mismo y acierta el 100 %.

**{' y '.join(equil)} {'están equilibrados' if len(equil) > 1 else 'está equilibrado'}** (brechas de
{', '.join(c(m['diagnostico'][n]['brecha_entrenamiento_cv']) for n in equil)}). Tienen **sesgo alto**: su ROC-AUC no
pasa de {c(max(e[n]['ROC_AUC'] for n in equil))} ni siquiera en entrenamiento. El límite está en la información
disponible: la curva de aprendizaje de la {mejor} queda plana (PR-AUC de validación
{c(m['curva_aprendizaje'][mejor + ' (mejor)']['PR_AUC_validacion_inicio'])} con
{m['curva_aprendizaje'][mejor + ' (mejor)']['n_inicio']} equipos y {c(m['curva_aprendizaje'][mejor + ' (mejor)']['PR_AUC_validacion_final'])}
con {m['curva_aprendizaje'][mejor + ' (mejor)']['n_final']}).

**Mitigación.** La búsqueda de hiperparámetros ya recortó la varianza:
- al Árbol lo limitó a {gs['Árbol de Decisión']['mejores_hiperparametros']} (PR-AUC de CV +{c(gs['Árbol de Decisión']['mejora_puntos'])}
  contra un árbol sin límite);
- al KNN lo llevó a {gs['KNN']['mejores_hiperparametros']}.

Se puede ir más lejos con hojas más grandes, menos variables o regularización más fuerte. Pero el problema de fondo no es
de varianza: los datos no tienen información para separar mejor las clases.

**Desbalance.** Solo el {pct(d['pct_en_riesgo'], 1)} de los equipos está en riesgo ({d['en_riesgo']} de {d['equipos']}).
- **La accuracy engaña.** Decir siempre "sin riesgo" (el Dummy) da accuracy {c(p[DUMMY]['accuracy'])} y no detecta a nadie
  (recall 0, Kappa 0). La {mejor} tiene una accuracy menor ({c(p[mejor]['accuracy'])}), pero detecta el
  {pct(p[mejor]['recall'])} de los clientes en riesgo. Por eso se reportan recall, F1, accuracy balanceada, Kappa y PR-AUC.
- **Qué se hizo:**
  - `class_weight="balanced"` en la Regresión Logística, el Árbol y el Random Forest;
  - umbral elegido en validación cruzada (máximo F1) para los modelos sin pesos.
- **Efecto del umbral en los modelos sin pesos.** Con el umbral 0,5 por defecto, el recall en prueba sería
  {', '.join(f'{n} {c(x)}' for n, x in r05.items())}. Con el umbral elegido sube a
  {', '.join(f'{n} {c(p[n]["recall"])}' for n in r05)}.
- **La partición es estratificada y agrupada por PON:** {pct(d['pct_en_riesgo_entrenamiento'], 1)} en riesgo en
  entrenamiento y {pct(d['pct_en_riesgo_prueba'], 1)} en prueba."""

    p3 = f"""**3. ¿Qué factores del dominio explican el desempeño? ¿El clustering coincide con las clases? ¿El ensamble vale la pena?**

- **La señal depende de la fibra, no del equipo.** La importancia por permutación muestra que casi todo lo aporta
  `{top_var}`, la señal media de los vecinos del PON (caída de PR-AUC de {c(imp[top_var], 3)}). La segunda variable aporta
  {c(resto[0][1], 3)}. La potencia que llega a un cliente depende del splitter, los empalmes y los conectores que comparte
  con su puerto. El modelo de ONT, el firmware o la posición en el puerto casi no influyen. Por eso un modelo lineal
  simple, que básicamente pondera `vec_rxp`, rinde igual que modelos más complejos.
- **Hay pocas unidades independientes.** Hay {d['equipos']} equipos, pero la información relevante vive en {d['pon']} PON.
  Al separar por PON (para no "ver" en la prueba la misma fibra que en el entrenamiento), los modelos flexibles aprenden
  ruido de cada puerto.
- **Las clases se separan poco.** Ningún modelo pasa de ROC-AUC {c(max(cv[n]['ROC_AUC'] for n in modelos))} en validación
  cruzada. Las curvas ROC de todos los modelos quedan juntas.

**Clustering (K-Means, mismas variables, sin la etiqueta).**
- **Los grupos no coinciden con las clases.** El mejor k por silueta es {kb} (silueta {c(cl['silueta'][kb])}, estructura
  débil), y el acuerdo con la clase real es bajo: ARI {c(cl['ARI'][kb])} en una escala de 0 a 1.
- **Pero revela una subestructura.** Con k = {kx}, un grupo de {pe[g_top]['equipos']} equipos tiene el
  {pct(pe[g_top]['pct_en_riesgo'])} en riesgo, contra {pct(min(otros))} a {pct(max(otros))} en los demás. Es un grupo de
  tendidos largos (distancia mediana {c(pe[g_top]['distancia_mediana_m'] / 1000, 1)} km), con señal de vecinos débil
  (media {c(pe[g_top]['vec_rxp_media'], 1)} dBm) y concentrado en {pe[g_top]['localidad_principal']}
  ({pct(pe[g_top]['pct_localidad_principal'])} del grupo). Eso no aparece en la clasificación supervisada: indica dónde
  mirar primero.

**Ensamble.** No se justifica.
- **Random Forest.** Tiene la PR-AUC de validación cruzada más alta ({c(cv[rf]['PR_AUC'])} contra {c(cv[mejor]['PR_AUC'])}),
  pero la diferencia es mucho menor que su desvío entre particiones (± {c(sd[rf]['PR_AUC'])}). Además sobreajusta (ROC-AUC
  {c(e[rf]['ROC_AUC'])} en entrenamiento) y en prueba queda por debajo de la {mejor}: ROC-AUC {c(p[rf]['ROC_AUC'], 3)}
  {'(no llega a la meta de 0,68)' if p[rf]['ROC_AUC'] < 0.68 else ''}.
- **Gradient Boosting.** Tiene la peor PR-AUC de validación cruzada ({c(cv[gb]['PR_AUC'])}). En prueba sale mejor
  ({c(p[gb]['PR_AUC'])}), lo que muestra que es inestable.
- **Costo.** La búsqueda de hiperparámetros tardó {c(seg[rf], 0)} s y {c(seg[gb], 0)} s, contra {c(seg[mejor], 1)} s de la
  {mejor}, y se pierde la interpretabilidad de los coeficientes.
{'- **Si se hubiera elegido entre todos los modelos** por validación cruzada, el elegido sería el ' + general + ', y no cumpliría la meta de ROC-AUC en prueba.' if general != mejor and p[general]['ROC_AUC'] < 0.68 else ''}"""
    return p1, p2, p3


def escribir():
    m = json.loads(METRICS.read_text(encoding="utf-8"))["obj14_tp3"]
    p1, p2, p3 = respuestas(m)
    t1, t2, t3 = tablas_md(m)
    mejor, d, s = m["mejor_modelo"], m["datos"], m["criterio_smart"]
    smart_md = "\n".join(["| Modelo | Rol | Criterio | Umbral | Valor | ¿Se cumple? |", "|---|---|---|---|---|---|"] + [
        f"| {k.split(' | ')[0]} | {v['rol']} | {k.split(' | ')[1]} | ≥ {c(s['metas']['ROC_AUC_prueba'] if 'ROC' in k else s['metas']['PR_AUC_prueba'])} | "
        f"{c(v['valor'], 3)} | {'Sí' if v['cumple'] else 'No'} |" for k, v in s["resultados"].items()])
    cl = m["clustering"]
    sel = "\n".join(["| k | Silueta | Davies-Bouldin | ARI con la clase |", "|---|---|---|---|"] + [
        f"| {k} | {c(cl['silueta'][k])} | {c(cl['davies_bouldin'][k])} | {c(cl['ARI'][k])} |" for k in cl["silueta"]])
    perf = "\n".join(["| Grupo | Equipos | % en riesgo | Señal media de vecinos (dBm) | Distancia mediana (km) | Localidad principal |",
                      "|---|---|---|---|---|---|"] + [
        f"| {g} | {v['equipos']} | {pct(v['pct_en_riesgo'], 1)} | {c(v['vec_rxp_media'], 1)} | {c(v['distancia_mediana_m'] / 1000, 1)} km | "
        f"{v['localidad_principal']} ({pct(v['pct_localidad_principal'])}) |" for g, v in cl["perfil_extra"].items()])
    v = m["prueba"]["Regla de los vecinos"]

    cuestionario = f"""# TP3: cuestionario de interpretación (borrador)

> Generado por `src/tp3_informe.py` desde `results/metrics.json`. No editar las cifras a mano: si cambia el modelo,
> se vuelve a generar con `python run_all.py`.

{p1}

{p2}

{p3}
"""

    informe = f"""# ¿Tiene el cliente la señal de la fibra en riesgo? Clasificación de ONTs de una red GPON (borrador)

*TP3, Aprendizaje Automático y Grandes Datos (UNRaf), 2026. Borrador generado desde `results/metrics.json`;
las cifras se actualizan solas al volver a correr el pipeline. Pasar a formato de artículo (3 a 5 páginas) para la entrega.*

## Resumen

Se clasificaron {d['equipos']} ONTs online según si la potencia óptica recibida está por debajo de −25 dBm. Para eso se
usaron datos que ya se conocen al instalar a un cliente: su ubicación, su equipo y la señal de sus vecinos de puerto, pero
no su propia señal.
- **Clasificadores comparados:** Regresión Logística (línea base), Árbol de Decisión, KNN y Naive Bayes, contra un
  clasificador que predice la clase mayoritaria y contra una regla sin ML basada en la señal de los vecinos.
- **El elegido:** la **{mejor}**, con ROC-AUC {c(m['prueba'][mejor]['ROC_AUC'])} y PR-AUC {c(m['prueba'][mejor]['PR_AUC'])}
  en prueba. Cumple las metas{'' if s['cumple_todo'] else ' solo en parte'}.
- **La regla de los vecinos rinde igual** (ROC-AUC {c(v['ROC_AUC'])}): la señal depende de la fibra compartida, no del
  equipo.
- **Los ensambles no mejoran y sobreajustan.**
- **El clustering encuentra un grupo de tendidos largos** con más del doble de clientes en riesgo.

## 1. Introducción

En el TP1 detectamos una fuga de datos (respaldo R3): un modelo que usa la señal del propio equipo para predecir su
estado "acierta" sin aprender nada. Esta pregunta la evita a propósito: **¿se puede anticipar que un cliente va a quedar
con la señal al límite antes de medirla?**
- **Datos.** El inventario del TP1 cruzado con el listado de la OLT que entregó la empresa (29/10/2026). La cátedra
  confirmó que el TP3 puede usar ese cruce.
- **Utilidad.**
  - elegir el puerto de cada alta nueva para que el cliente no quede al límite;
  - anticiparse a los reclamos;
  - distinguir si el problema está en la fibra o en el módem.

## 2. Marco experimental

- **Problema.** Clasificación binaria. `en_riesgo` = 1 si la potencia recibida es menor que −25 dBm. La sensibilidad
  mínima del equipo (clase B+) es −27 dBm, así que −25 deja 2 dB de margen.
- **Clases.** {d['en_riesgo']} en riesgo de {d['equipos']} ({pct(d['pct_en_riesgo'], 1)}): desbalance de 1 a 8.
- **Variables de entrada.**
  - Categóricas (one-hot): localidad, modelo, puertos LAN y Wi-Fi.
  - Numéricas (mediana + escalado): slot, PON, ID, posición relativa en el PON, equipos del PON, generación de
    firmware, firmware fuera de estándar, distancia a la OLT y `vec_rxp`, la señal media de los **otros** equipos online
    del mismo PON.
- **Variables prohibidas.** La potencia recibida y transmitida, el estado y el nivel de señal del propio equipo, porque
  son la respuesta.
- **Por qué `vec_rxp` sí entra.** Cuando se instala un cliente, la señal de sus vecinos ya está medida; la suya, no.
- **Partición.** `StratifiedGroupKFold(5, shuffle=True, random_state=42)` con grupos = PON. La prueba es una de las 5
  particiones: {d['prueba']} equipos de {d['pon_prueba']} PON. Ningún PON está a la vez en entrenamiento y en prueba,
  porque los equipos de un PON comparten la fibra; si no se agrupara, el modelo vería la misma fibra en los dos lados.
  La validación cruzada usa la misma estrategia sobre los {d['entrenamiento']} equipos restantes.
- **Referencias.**
  - `DummyClassifier(strategy="prior")`.
  - La **regla de los vecinos** (puntaje = −`vec_rxp`): no es un clasificador más, es la vara para saber cuánto agrega el ML.
- **Métricas.** Accuracy y accuracy balanceada; precisión, recall y F1 de la clase "en riesgo" y ponderados; Kappa de
  Cohen; ROC-AUC y PR-AUC. Todas en entrenamiento, en validación cruzada (media ± desvío) y en prueba.

## 3. Métodos

- **Pipeline.** Todo el preprocesamiento va dentro de un `Pipeline` con `ColumnTransformer`.
- **Búsqueda de hiperparámetros.** `GridSearchCV` con la misma validación agrupada, eligiendo por PR-AUC.
- **Desbalance.**
  - `class_weight="balanced"` en la Regresión Logística, el Árbol y el Random Forest;
  - en KNN, Naive Bayes y Gradient Boosting, el umbral de decisión se elige en validación cruzada (máximo F1 sobre
    probabilidades fuera de muestra). Para medir esos modelos en la validación cruzada, el umbral se vuelve a elegir
    dentro de cada partición, solo con su parte de entrenamiento.
- **Selección.** El clasificador se elige entre los cuatro individuales por PR-AUC de validación cruzada.
- **Extras:**
  - importancia por permutación;
  - análisis del umbral (F2 y recall del 80 %);
  - curva de aprendizaje;
  - árbol dibujado.

## 4. Resultados

**Tabla 1.** Métricas en prueba (clase "en riesgo").

{t1}

**Tabla 2.** Entrenamiento, validación cruzada y prueba; diagnóstico de ajuste. Hay sobreajuste si la ROC-AUC de
entrenamiento supera a la de validación o a la de prueba por más de 0,10.

{t2}

**Tabla 3.** Matrices de confusión en prueba ({d['prueba']} equipos). La figura `tp3_matrices_confusion.png` muestra cada una.

{t3}

**Criterio SMART** (en prueba):

{smart_md}

Figuras (en `reports/TP3/`):
- `tp3_matrices_confusion.png`, `tp3_comparacion_modelos.png` y `tp3_curvas_roc_pr.png`;
- `tp3_umbral_decision.png`, `tp3_importancia_variables.png` y `tp3_curva_aprendizaje.png`;
- `tp3_arbol.png` y `tp3_clustering.png`.

## 5. Plus: ensamble y clustering

**Ensamble.** Random Forest (bagging, 300 árboles) y Gradient Boosting (boosting, 200 árboles). Sus resultados están en
las tablas 1 a 3 y se discuten en la pregunta 3.

**Clustering.** K-Means con las mismas variables, sin la etiqueta, con k de 2 a 8:

{sel}

Perfil de los grupos con k = {cl['k_extra']}:

{perf}

## 6. Discusión: cuestionario de interpretación

{p1}

{p2}

{p3}

## 7. Conclusiones

- **La {mejor} identifica a los clientes con señal en riesgo mucho mejor que el azar.** PR-AUC {c(m['prueba'][mejor]['PR_AUC'])}
  contra {c(m['prueba']['Dummy (prior)']['PR_AUC'])}, y detecta a {pct(m['prueba'][mejor]['recall'])} de los clientes en
  riesgo de la prueba.
- **Casi todo ese poder viene de la señal de los vecinos del puerto.** Una regla sin ML que solo mira esa señal rinde
  igual. Para la empresa la conclusión es práctica: **el riesgo está en la fibra compartida del puerto, no en el módem**.
  Para elegir dónde conectar a un cliente nuevo, alcanza con mirar cómo les llega la señal a los vecinos.
- **Los modelos más complejos memorizan y no mejoran la prueba.** Pasa con el Árbol, el KNN y los ensambles: la
  complejidad no se justifica.
- **El clustering señala un grupo de tendidos largos** con riesgo mucho mayor que el resto. Es un buen punto de partida
  para el mantenimiento preventivo.
"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cuestionario_borrador.md").write_text(cuestionario, encoding="utf-8")
    (OUT / "informe_borrador.md").write_text(informe, encoding="utf-8")
    return OUT / "informe_borrador.md", OUT / "cuestionario_borrador.md"


if __name__ == "__main__":
    print(escribir())
