# ¿Tiene el cliente la señal de la fibra en riesgo? Clasificación de ONTs de una red GPON (borrador)

*TP3, Aprendizaje Automático y Grandes Datos (UNRaf), 2026. Borrador generado desde `results/metrics.json`;
las cifras se actualizan solas al volver a correr el pipeline. Pasar a formato de artículo (3 a 5 páginas) para la entrega.*

## Resumen

Se clasificaron 4872 ONTs online según si la potencia óptica recibida está por debajo de −25 dBm. Para eso se
usaron datos que ya se conocen al instalar a un cliente: su ubicación, su equipo y la señal de sus vecinos de puerto, pero
no su propia señal.
- **Clasificadores comparados:** Regresión Logística (línea base), Árbol de Decisión, KNN y Naive Bayes, contra un
  clasificador que predice la clase mayoritaria y contra una regla sin ML basada en la señal de los vecinos.
- **El elegido:** la **Regresión Logística**, con ROC-AUC 0,70 y PR-AUC 0,39
  en prueba. Cumple las metas.
- **La regla de los vecinos rinde igual** (ROC-AUC 0,71): la señal depende de la fibra compartida, no del
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
- **Clases.** 548 en riesgo de 4872 (11,2 %): desbalance de 1 a 8.
- **Variables de entrada.**
  - Categóricas (one-hot): localidad, modelo, puertos LAN y Wi-Fi.
  - Numéricas (mediana + escalado): slot, PON, ID, posición relativa en el PON, equipos del PON, generación de
    firmware, firmware fuera de estándar, distancia a la OLT y `vec_rxp`, la señal media de los **otros** equipos online
    del mismo PON.
- **Variables prohibidas.** La potencia recibida y transmitida, el estado y el nivel de señal del propio equipo, porque
  son la respuesta.
- **Por qué `vec_rxp` sí entra.** Cuando se instala un cliente, la señal de sus vecinos ya está medida; la suya, no.
- **Partición.** `StratifiedGroupKFold(5, shuffle=True, random_state=42)` con grupos = PON. La prueba es una de las 5
  particiones: 973 equipos de 63 PON. Ningún PON está a la vez en entrenamiento y en prueba,
  porque los equipos de un PON comparten la fibra; si no se agrupara, el modelo vería la misma fibra en los dos lados.
  La validación cruzada usa la misma estrategia sobre los 3899 equipos restantes.
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

| Modelo | Hiperparámetros | Umbral | Accuracy | Acc. balanceada | Precisión | Recall | F1 | F1 ponderado | Kappa | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Regresión Logística | {'C': 0.01} | 0,50 | 0,77 | 0,68 | 0,25 | 0,56 | 0,35 | 0,80 | 0,23 | 0,70 | 0,39 |
| Árbol de Decisión | {'max_depth': 8, 'min_samples_leaf': 50} | 0,50 | 0,75 | 0,65 | 0,23 | 0,52 | 0,32 | 0,79 | 0,19 | 0,71 | 0,40 |
| KNN | {'n_neighbors': 101, 'weights': 'distance'} | 0,17 | 0,85 | 0,63 | 0,34 | 0,33 | 0,33 | 0,85 | 0,25 | 0,66 | 0,26 |
| Naive Bayes | {'var_smoothing': 0.1} | 0,19 | 0,80 | 0,61 | 0,24 | 0,36 | 0,29 | 0,82 | 0,18 | 0,67 | 0,28 |
| Random Forest | {'max_depth': 10, 'min_samples_leaf': 5} | 0,50 | 0,85 | 0,65 | 0,35 | 0,40 | 0,37 | 0,85 | 0,29 | 0,68 | 0,31 |
| Gradient Boosting | {'learning_rate': 0.05, 'max_depth': 2} | 0,18 | 0,88 | 0,66 | 0,46 | 0,37 | 0,41 | 0,88 | 0,35 | 0,71 | 0,43 |
| Dummy (prior) | - | 0,50 | 0,89 | 0,50 | 0,00 | 0,00 | 0,00 | 0,84 | 0,00 | 0,50 | 0,11 |
| Regla de los vecinos (sin ML) | puntaje = −vec_rxp | - | - | - | - | - | - | - | - | 0,71 | 0,40 |

**Tabla 2.** Entrenamiento, validación cruzada y prueba; diagnóstico de ajuste. Hay sobreajuste si la ROC-AUC de
entrenamiento supera a la de validación o a la de prueba por más de 0,10.

| Modelo | ROC-AUC entrenamiento | ROC-AUC CV (media ± desvío) | ROC-AUC prueba | PR-AUC entrenamiento | PR-AUC CV | PR-AUC prueba | F1 ent. | F1 prueba | Diagnóstico |
|---|---|---|---|---|---|---|---|---|---|
| Regresión Logística | 0,74 | 0,72 ± 0,04 | 0,70 | 0,34 | 0,32 ± 0,11 | 0,39 | 0,35 | 0,35 | ajuste razonable |
| Árbol de Decisión | 0,84 | 0,67 ± 0,08 | 0,71 | 0,43 | 0,30 ± 0,13 | 0,40 | 0,43 | 0,32 | sobreajuste |
| KNN | 1,00 | 0,69 ± 0,04 | 0,66 | 1,00 | 0,30 ± 0,09 | 0,26 | 1,00 | 0,33 | sobreajuste |
| Naive Bayes | 0,73 | 0,71 ± 0,06 | 0,67 | 0,29 | 0,28 ± 0,08 | 0,28 | 0,36 | 0,29 | ajuste razonable |
| Random Forest | 0,92 | 0,71 ± 0,06 | 0,68 | 0,65 | 0,34 ± 0,15 | 0,31 | 0,54 | 0,37 | sobreajuste |
| Gradient Boosting | 0,80 | 0,66 ± 0,06 | 0,71 | 0,54 | 0,25 ± 0,04 | 0,43 | 0,48 | 0,41 | sobreajuste |
| Dummy (prior) | 0,50 | 0,50 ± 0,00 | 0,50 | 0,11 | 0,11 ± 0,00 | 0,11 | 0,00 | 0,00 | subajuste |

**Tabla 3.** Matrices de confusión en prueba (973 equipos). La figura `tp3_matrices_confusion.png` muestra cada una.

| Modelo | En riesgo detectados | En riesgo NO detectados | Falsas alarmas | Sin riesgo bien clasificados |
|---|---|---|---|---|
| Regresión Logística | 60 | 48 | 177 | 688 |
| Árbol de Decisión | 56 | 52 | 191 | 674 |
| KNN | 36 | 72 | 71 | 794 |
| Naive Bayes | 39 | 69 | 123 | 742 |
| Random Forest | 43 | 65 | 81 | 784 |
| Gradient Boosting | 40 | 68 | 47 | 818 |
| Dummy (prior) | 0 | 108 | 0 | 865 |

**Criterio SMART** (en prueba):

| Modelo | Rol | Criterio | Umbral | Valor | ¿Se cumple? |
|---|---|---|---|---|---|
| Regresión Logística | elegido (individual) | ROC-AUC en prueba | ≥ 0,68 | 0,698 | Sí |
| Regresión Logística | elegido (individual) | PR-AUC en prueba | ≥ 0,22 | 0,389 | Sí |
| Random Forest | mejor en CV entre todos | ROC-AUC en prueba | ≥ 0,68 | 0,675 | No |
| Random Forest | mejor en CV entre todos | PR-AUC en prueba | ≥ 0,22 | 0,314 | Sí |

Figuras (en `reports/TP3/`):
- `tp3_matrices_confusion.png`, `tp3_comparacion_modelos.png` y `tp3_curvas_roc_pr.png`;
- `tp3_umbral_decision.png`, `tp3_importancia_variables.png` y `tp3_curva_aprendizaje.png`;
- `tp3_arbol.png` y `tp3_clustering.png`.

## 5. Plus: ensamble y clustering

**Ensamble.** Random Forest (bagging, 300 árboles) y Gradient Boosting (boosting, 200 árboles). Sus resultados están en
las tablas 1 a 3 y se discuten en la pregunta 3.

**Clustering.** K-Means con las mismas variables, sin la etiqueta, con k de 2 a 8:

| k | Silueta | Davies-Bouldin | ARI con la clase |
|---|---|---|---|
| 2 | 0,24 | 2,12 | 0,16 |
| 3 | 0,22 | 1,85 | 0,10 |
| 4 | 0,16 | 1,91 | 0,04 |
| 5 | 0,17 | 1,80 | 0,04 |
| 6 | 0,15 | 1,90 | 0,02 |
| 7 | 0,17 | 1,68 | 0,02 |
| 8 | 0,15 | 1,66 | 0,01 |

Perfil de los grupos con k = 4:

| Grupo | Equipos | % en riesgo | Señal media de vecinos (dBm) | Distancia mediana (km) | Localidad principal |
|---|---|---|---|---|---|
| 0 | 553 | 11,2 % | -21,2 | 1,5 km | Frontera (37 %) |
| 1 | 675 | 26,7 % | -23,3 | 8,2 km | Bernardo de Irigoyen (52 %) |
| 2 | 1100 | 7,6 % | -20,3 | 1,4 km | San Vicente (31 %) |
| 3 | 2544 | 8,7 % | -20,2 | 1,4 km | San Vicente (34 %) |

## 6. Discusión: cuestionario de interpretación

**1. ¿Cuál es el clasificador más adecuado? ¿Cambia si se prioriza el recall o la precisión?**

El elegido es la **Regresión Logística**. Tiene la mayor PR-AUC media en validación cruzada entre los cuatro clasificadores
individuales (0,32 ± 0,11), y la elección se hizo sin mirar la prueba. En prueba
obtiene ROC-AUC 0,70 y PR-AUC 0,39; el azar da 0,11. Con el umbral 0,5:
- detecta **60 de los 108 clientes en riesgo** (recall 0,56);
- a cambio, da **177 falsas alarmas** (precisión 0,25).

**La elección sí depende de qué se priorice.**
- **Recall.** La Regresión Logística es el modelo que más clientes en riesgo encuentra en
  prueba (recall 0,56).
- **Precisión.** Si importa no mandar técnicos de más, gana el Gradient Boosting (precisión 0,46): detecta
  40 y da solo 47 falsas alarmas. Pero deja sin detectar a 68 de 108 clientes en riesgo.

En este problema un cliente en riesgo no detectado termina en reclamo, así que **conviene priorizar el recall**. El análisis
del umbral muestra el costo:
- **Con el umbral que maximiza F2** (0,51, casi igual a 0,5 porque `class_weight="balanced"` ya lo corre), se
  marcan 225 equipos y se detecta el 53 %.
- **Para detectar el 80 % en validación cruzada**, hay que bajar el umbral. En prueba eso da recall
  0,74, pero marca 547 de 973 equipos y solo 15 % de las alarmas
  son reales.

**Hallazgo: la regla de los vecinos.** La regla sin ML, que ordena a los clientes por la señal media de sus vecinos de
PON, da ROC-AUC 0,71 y PR-AUC 0,40 en prueba. Es igual o apenas mejor que
la Regresión Logística. Toda la información útil está en la fibra compartida del puerto: el modelo de equipo, el firmware y la
distancia casi no agregan nada.

**2. ¿Hubo sobreajuste o subajuste? ¿Qué impacto tuvo el desbalance?**

**Sobreajustan Árbol de Decisión, KNN, Random Forest, Gradient Boosting.** Se detecta comparando la ROC-AUC de entrenamiento con la de validación cruzada
(agrupada por PON) y con la de prueba:
- Árbol de Decisión: 0,84 en entrenamiento contra 0,67 en validación cruzada.
- KNN: 1,00 en entrenamiento contra 0,69 en validación cruzada.
- Random Forest: 0,92 en entrenamiento contra 0,71 en validación cruzada.
- Gradient Boosting: 0,80 en entrenamiento contra 0,66 en validación cruzada.

Es varianza alta: aprenden características de los PON de entrenamiento que no se repiten en PON nuevos. El caso extremo
es el KNN con `weights="distance"`, que en entrenamiento se reconoce a sí mismo y acierta el 100 %.

**Regresión Logística y Naive Bayes están equilibrados** (brechas de
0,02, 0,02). Tienen **sesgo alto**: su ROC-AUC no
pasa de 0,74 ni siquiera en entrenamiento. El límite está en la información
disponible: la curva de aprendizaje de la Regresión Logística queda plana (PR-AUC de validación
0,30 con
467 equipos y 0,32
con 3116).

**Mitigación.** La búsqueda de hiperparámetros ya recortó la varianza:
- al Árbol lo limitó a {'max_depth': 8, 'min_samples_leaf': 50} (PR-AUC de CV +0,11
  contra un árbol sin límite);
- al KNN lo llevó a {'n_neighbors': 101, 'weights': 'distance'}.

Se puede ir más lejos con hojas más grandes, menos variables o regularización más fuerte. Pero el problema de fondo no es
de varianza: los datos no tienen información para separar mejor las clases.

**Desbalance.** Solo el 11,2 % de los equipos está en riesgo (548 de 4872).
- **La accuracy engaña.** Decir siempre "sin riesgo" (el Dummy) da accuracy 0,89 y no detecta a nadie
  (recall 0, Kappa 0). La Regresión Logística tiene una accuracy menor (0,77), pero detecta el
  56 % de los clientes en riesgo. Por eso se reportan recall, F1, accuracy balanceada, Kappa y PR-AUC.
- **Qué se hizo:**
  - `class_weight="balanced"` en la Regresión Logística, el Árbol y el Random Forest;
  - umbral elegido en validación cruzada (máximo F1) para los modelos sin pesos.
- **Efecto del umbral en los modelos sin pesos.** Con el umbral 0,5 por defecto, el recall en prueba sería
  KNN 0,00, Naive Bayes 0,24, Gradient Boosting 0,24. Con el umbral elegido sube a
  KNN 0,33, Naive Bayes 0,36, Gradient Boosting 0,37.
- **La partición es estratificada y agrupada por PON:** 11,3 % en riesgo en
  entrenamiento y 11,1 % en prueba.

**3. ¿Qué factores del dominio explican el desempeño? ¿El clustering coincide con las clases? ¿El ensamble vale la pena?**

- **La señal depende de la fibra, no del equipo.** La importancia por permutación muestra que casi todo lo aporta
  `vec_rxp`, la señal media de los vecinos del PON (caída de PR-AUC de 0,265). La segunda variable aporta
  0,000. La potencia que llega a un cliente depende del splitter, los empalmes y los conectores que comparte
  con su puerto. El modelo de ONT, el firmware o la posición en el puerto casi no influyen. Por eso un modelo lineal
  simple, que básicamente pondera `vec_rxp`, rinde igual que modelos más complejos.
- **Hay pocas unidades independientes.** Hay 4872 equipos, pero la información relevante vive en 300 PON.
  Al separar por PON (para no "ver" en la prueba la misma fibra que en el entrenamiento), los modelos flexibles aprenden
  ruido de cada puerto.
- **Las clases se separan poco.** Ningún modelo pasa de ROC-AUC 0,72 en validación
  cruzada. Las curvas ROC de todos los modelos quedan juntas.

**Clustering (K-Means, mismas variables, sin la etiqueta).**
- **Los grupos no coinciden con las clases.** El mejor k por silueta es 2 (silueta 0,24, estructura
  débil), y el acuerdo con la clase real es bajo: ARI 0,16 en una escala de 0 a 1.
- **Pero revela una subestructura.** Con k = 4, un grupo de 675 equipos tiene el
  27 % en riesgo, contra 8 % a 11 % en los demás. Es un grupo de
  tendidos largos (distancia mediana 8,2 km), con señal de vecinos débil
  (media -23,3 dBm) y concentrado en Bernardo de Irigoyen
  (52 % del grupo). Eso no aparece en la clasificación supervisada: indica dónde
  mirar primero.

**Ensamble.** No se justifica.
- **Random Forest.** Tiene la PR-AUC de validación cruzada más alta (0,34 contra 0,32),
  pero la diferencia es mucho menor que su desvío entre particiones (± 0,15). Además sobreajusta (ROC-AUC
  0,92 en entrenamiento) y en prueba queda por debajo de la Regresión Logística: ROC-AUC 0,675
  (no llega a la meta de 0,68).
- **Gradient Boosting.** Tiene la peor PR-AUC de validación cruzada (0,25). En prueba sale mejor
  (0,43), lo que muestra que es inestable.
- **Costo.** La búsqueda de hiperparámetros tardó 28 s y 26 s, contra 3,3 s de la
  Regresión Logística, y se pierde la interpretabilidad de los coeficientes.
- **Si se hubiera elegido entre todos los modelos** por validación cruzada, el elegido sería el Random Forest, y no cumpliría la meta de ROC-AUC en prueba.

## 7. Conclusiones

- **La Regresión Logística identifica a los clientes con señal en riesgo mucho mejor que el azar.** PR-AUC 0,39
  contra 0,11, y detecta a 56 % de los clientes en
  riesgo de la prueba.
- **Casi todo ese poder viene de la señal de los vecinos del puerto.** Una regla sin ML que solo mira esa señal rinde
  igual. Para la empresa la conclusión es práctica: **el riesgo está en la fibra compartida del puerto, no en el módem**.
  Para elegir dónde conectar a un cliente nuevo, alcanza con mirar cómo les llega la señal a los vecinos.
- **Los modelos más complejos memorizan y no mejoran la prueba.** Pasa con el Árbol, el KNN y los ensambles: la
  complejidad no se justifica.
- **El clustering señala un grupo de tendidos largos** con riesgo mucho mayor que el resto. Es un buen punto de partida
  para el mantenimiento preventivo.
