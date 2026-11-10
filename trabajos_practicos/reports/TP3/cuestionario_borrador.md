# TP3: cuestionario de interpretación (borrador)

> Generado por `src/tp3_informe.py` desde `results/metrics.json`. No editar las cifras a mano: si cambia el modelo,
> se vuelve a generar con `python run_all.py`.

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
