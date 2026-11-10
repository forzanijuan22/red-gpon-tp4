# Predicción del porcentaje de ONTs con firmware fuera de estándar por puerto PON (borrador)

*TP2, Aprendizaje Automático y Grandes Datos (UNRaf), 2026. Borrador generado desde `results/metrics.json`;
las cifras se actualizan solas al volver a correr el pipeline. Pasar a formato de artículo (3 a 5 páginas) para la entrega.*

## Resumen

Se estimó el porcentaje de equipos con firmware distinto del estándar de su modelo en cada uno de los 301
puertos PON de una red GPON de 9 localidades. Se compararon una Regresión Lineal (línea base), Ridge, Random Forest y
Gradient Boosting contra un modelo que predice siempre el promedio. El mejor modelo en validación cruzada fue
**Ridge**, con R² 0,59, R² ajustado 0,38 y MAE
0,088 en prueba (R² 0,49 en validación cruzada). Cumple las tres
metas fijadas. Los modelos de árboles sobreajustan, y sumar variables
técnicas de la OLT no mejora la predicción.

## 1. Introducción

En el TP1 se encontró que el modelo de ONT instalado depende fuertemente de la localidad (respaldo R2). Casi 3 de cada
10 equipos no tienen la versión de firmware más usada de su modelo. Actualizar equipo por equipo es lento; lo práctico es
actualizar un puerto PON completo en una ventana de mantenimiento. La pregunta de este trabajo es si se puede estimar, a
partir de cómo está compuesto cada puerto, qué porcentaje de sus equipos está fuera de estándar. Así la empresa puede
priorizar los puertos donde una ventana de mantenimiento rinde más.

## 2. Marco experimental

- **Datos.** El inventario del TP1 (5114 ONTs), agregado por puerto PON: 301 filas.
- **Variable objetivo.** `pct_fw_fuera`, la proporción de equipos del PON con una versión de firmware distinta de la
  más frecuente de su modelo. Media 0,29, desvío 0,20; 26 PON
  tienen 0 % y 5 tienen 100 %.
- **Variables de entrada.** Localidad y tarjeta (one-hot), cantidad de equipos del puerto, % con TV, % de equipos
  modernos, cantidad de modelos distintos y la proporción de los 5 modelos más usados (EG8141A5, EG8143A5, CN1001, CN2002, RDC143).
- **Variables excluidas.**
  - Todo lo que sale de la versión de firmware (`pct_v3`, `n_versiones`), porque es la respuesta.
  - Los identificadores.
  - Las variables de huecos de ID, que no están validadas con la empresa.
- **Por qué 5 proporciones y no 22.** Con las 22 proporciones de modelo, la Regresión Lineal tiene
  38 predictores para 240 PON y su R²
  ajustado de prueba cae a -0,04. Con 5 queda en
  0,37.
- **Partición.** 80/20 con semilla 42 (240 PON de entrenamiento y 61 de prueba). Validación
  cruzada KFold de 5 partes (mezclada, semilla 42) sobre el entrenamiento, para elegir hiperparámetros y modelo. La
  prueba se usa una sola vez, al final. Cada fila es un PON, así que no hace falta agrupar.
- **Línea base.** Regresión Lineal (la que recomienda la consigna). Como piso, un `DummyRegressor` que predice siempre
  el promedio.
- **Métricas.**
  - MSE, RMSE, MAE, R² y R² ajustado, en entrenamiento, en validación cruzada (media ± desvío) y en prueba.
  - El R² ajustado usa los predictores efectivos (columnas one-hot menos una por variable categórica).
  - No se usa MAPE: 26 PON tienen 0 % y el MAPE divide por el valor real.

## 3. Métodos

Todo el preprocesamiento (one-hot con `handle_unknown="ignore"`, imputación por mediana y escalado) va dentro de un
`Pipeline` de scikit-learn, así nada se ajusta con datos de validación o de prueba. Los hiperparámetros se buscaron con
`GridSearchCV` (KFold de 5) minimizando el RMSE:

- **Ridge.** `alpha` ∈ {0,1; 1; 10}: de casi sin penalización a penalización fuerte. Elegido:
  {'alpha': 1}.
- **Random Forest.** 300 árboles; `min_samples_leaf` ∈ {1, 3, 5} y `max_depth` ∈ {sin límite, 8}, para limitar la
  memorización con pocos PON. Elegido: {'max_depth': 8, 'min_samples_leaf': 3}. El RMSE de CV mejora
  4,0 % respecto de los valores por defecto.
- **Gradient Boosting.** 200 árboles; `learning_rate` ∈ {0,05; 0,1} y `max_depth` ∈ {2, 3}. Elegido:
  {'learning_rate': 0.05, 'max_depth': 2}. El RMSE de CV mejora
  11,1 %.

El mejor modelo se eligió por el RMSE de validación cruzada. Sobre ese modelo se calcularon:
- la importancia por permutación;
- el análisis de residuos (Shapiro-Wilk y Breusch-Pagan);
- la curva de aprendizaje.

Como prueba adicional, se repitió el mejor modelo sumando tres variables por PON del listado de la OLT del 29/10/2026:
% de equipos online, distancia mediana y potencia recibida mediana.

## 4. Resultados

**Tabla 1.** R² y diagnóstico de ajuste. El diagnóstico marca sobreajuste cuando el R² de entrenamiento supera al de
validación o al de prueba por más de 0,15.

| Modelo | Hiperparámetros | R² entrenamiento | R² CV (media ± desvío) | R² prueba | R² ajustado prueba | Diagnóstico |
|---|---|---|---|---|---|---|
| Dummy (promedio) | - | 0,00 | -0,01 ± 0,01 | -0,01 | -0,01 | subajuste |
| Regresión Lineal | - | 0,58 | 0,49 ± 0,11 | 0,59 | 0,37 | ajuste razonable |
| Ridge | {'alpha': 1} | 0,57 | 0,49 ± 0,10 | 0,59 | 0,38 | ajuste razonable |
| Random Forest | {'max_depth': 8, 'min_samples_leaf': 3} | 0,76 | 0,46 ± 0,12 | 0,62 | 0,41 | sobreajuste |
| Gradient Boosting | {'learning_rate': 0.05, 'max_depth': 2} | 0,73 | 0,39 ± 0,22 | 0,60 | 0,39 | sobreajuste |

**Tabla 2.** Errores (en proporción: 0,10 = 10 puntos porcentuales).

| Modelo | MSE ent. | MSE CV | MSE prueba | RMSE ent. | RMSE CV | RMSE prueba | MAE ent. | MAE CV | MAE prueba |
|---|---|---|---|---|---|---|---|---|---|
| Dummy (promedio) | 0,0407 | 0,0408 | 0,0337 | 0,202 | 0,202 | 0,184 | 0,147 | 0,147 | 0,128 |
| Regresión Lineal | 0,0172 | 0,0207 | 0,0138 | 0,131 | 0,143 | 0,118 | 0,099 | 0,110 | 0,089 |
| Ridge | 0,0173 | 0,0205 | 0,0136 | 0,132 | 0,142 | 0,117 | 0,100 | 0,109 | 0,088 |
| Random Forest | 0,0096 | 0,0216 | 0,0129 | 0,098 | 0,146 | 0,113 | 0,073 | 0,110 | 0,085 |
| Gradient Boosting | 0,0108 | 0,0243 | 0,0134 | 0,104 | 0,154 | 0,116 | 0,078 | 0,113 | 0,083 |

Figuras (en `reports/TP2/`):
- `tp2_comparacion_modelos.png`: métricas por modelo.
- `tp2_predicho_vs_real.png`: predicho contra real.
- `tp2_residuos.png`: residuos del mejor modelo.
- `tp2_curva_aprendizaje.png`: curvas de aprendizaje.
- `tp2_importancia_variables.png`: importancia de variables.

**Prueba con datos de la OLT.**

| Variables | R² CV | R² prueba | R² ajustado prueba | MAE prueba |
|---|---|---|---|---|
| Sin OLT | 0,49 | 0,59 | 0,38 | 0,088 |
| Con OLT | 0,46 | 0,51 | 0,18 | 0,096 |

**Criterio SMART** (sobre Ridge, en prueba):

| Criterio | Umbral | Valor | ¿Se cumple? |
|---|---|---|---|
| R² en prueba | ≥ 0,45 | 0,595 | Sí |
| R² ajustado en prueba | ≥ 0,30 | 0,376 | Sí |
| MAE en prueba menor que el del Dummy | < 0,128 (Dummy) | 0,088 | Sí |

## 5. Discusión: cuestionario de interpretación

**1. ¿Cuál fue el modelo más adecuado y cambiaría la elección con otra métrica?**

El modelo elegido es **Ridge**, porque tiene el menor RMSE medio en la validación cruzada de 5 partes sobre el
entrenamiento (0,142). La elección se hizo sin mirar la prueba. En prueba obtiene R²
0,59, R² ajustado 0,38 y MAE 0,088
(el Dummy: MAE 0,128). En validación cruzada gana Ridge en las tres métricas.

La diferencia con la Regresión Lineal es mínima (RMSE de CV 0,1430 contra 0,1423;
R² 0,489 contra 0,494), muy por debajo del desvío entre particiones
(± 0,017). En la práctica son el mismo modelo: con
{'alpha': 1} la penalización de Ridge casi no cambia los coeficientes.

**Con otra métrica, la elección cambia solo si se mira la prueba.** En el conjunto de prueba gana Random Forest en RMSE y R², y Gradient Boosting en MAE. Es decir, Gradient Boosting y Random Forest superan a Ridge en alguna métrica de prueba.
Pero la prueba tiene solo 61 PON y salió más fácil que el promedio: todos los modelos tienen mejor R² en prueba que en validación cruzada. Por ejemplo, el Random Forest tiene R² 0,62
en prueba contra 0,46 en CV. Elegir por la prueba sería ajustar el modelo
mirando el test. El MAE premia a los árboles, que aciertan bien los PON "típicos". El RMSE castiga los errores grandes
en los PON extremos, y ahí los modelos lineales son más estables. Para la empresa importa no errarle feo a un puerto
(mandar una cuadrilla a un puerto que estaba al día), así que el RMSE es la métrica de selección más razonable.

**2. ¿Hubo sobreajuste o subajuste? ¿Cómo se detectó y cómo se mitiga?**

Sí. **El Random Forest y el Gradient Boosting sobreajustan.** El Random Forest explica R²
0,76 en entrenamiento pero 0,46 en
validación cruzada (brecha 0,30). El Gradient Boosting pasa de
0,73 a 0,39 (brecha
0,35). Es **varianza alta**: con 240 PON, los árboles aprenden
particularidades de cada puerto que no se repiten. La curva de aprendizaje lo confirma: al Random Forest le queda una
brecha de 5,0 puntos porcentuales de RMSE
entre entrenamiento y validación con todos los datos.

Contra la prueba, la brecha del Random Forest (0,148) casi no llega al umbral de
0,15. Por eso el diagnóstico usa las dos brechas: la de prueba, con 61 PON, depende de qué puertos
cayeron en ese 20 %.

**Las Regresiones Lineal y Ridge no sobreajustan** (brecha contra CV de
0,09 y 0,08).
Tienen **sesgo moderado**: su R² de entrenamiento (0,57) es el techo de lo que puede
explicar un modelo aditivo con estas variables. En su curva de aprendizaje las dos líneas casi se tocan (brecha de
1,2 p.p.): más datos ayudarían
poco; harían falta mejores variables. **El Dummy subajusta** por definición (R² 0).

**Mitigación.**
- En los árboles, la búsqueda de hiperparámetros ya redujo la varianza: el Random Forest eligió
  {'max_depth': 8, 'min_samples_leaf': 3} (RMSE de CV 4,0 % mejor que con
  los valores por defecto). El Gradient Boosting eligió {'learning_rate': 0.05, 'max_depth': 2}
  (11,1 % mejor). Se puede ir más lejos: hojas más grandes, `max_features`
  menor, `subsample` < 1 en el boosting, o simplemente más PON.
- Con 22 proporciones de modelo en lugar de 5, la Regresión Lineal tiene 38 predictores para
  240 PON. El R² ajustado de prueba cae de 0,37 a
  -0,04: reducir variables fue la primera medida contra la varianza.
- Para bajar el sesgo de los lineales harían falta variables nuevas, por ejemplo la fecha de la última campaña de
  actualización por localidad. No están en el inventario.

**3. ¿Qué factores del dominio explican el desempeño? ¿Quedan patrones en los residuos?**

- **Poco volumen.** Hay 301 PON y 21 predictores efectivos. Con
  240 filas de entrenamiento, los modelos flexibles no tienen datos suficientes para que sus
  interacciones se paguen. Por eso un modelo lineal regularizado empata o le gana a los ensambles en validación cruzada.
- **La relación es casi aditiva.** El % fuera de estándar de un puerto se explica sobre todo por dos efectos que se
  suman: **la composición de modelos** y **la localidad**. Lo que más pesa es el % de equipos con TV
  (`pct_catv`, caída del R² de 0,91 al mezclarlo). Está correlacionado en
  0,99 con la proporción de EG8143A5, porque ese es el modelo con TV más común.
  Mezcladas juntas, el R² cae 1,34. Después viene la
  localidad (0,27). Un modelo lineal captura bien una suma de efectos.
- **Parte de lo que se predice es la definición.** El firmware "estándar" es la versión más común de cada modelo. En el
  EG8143A5 es la V3, que tiene solo el 40 % de sus equipos; el resto tiene V5, más
  nueva. Por eso los puertos con muchos EG8143A5 salen "fuera de estándar" aunque tengan firmware más nuevo. En toda la
  red, 578 de los 1476 equipos fuera de estándar (39,2 %) tienen una
  generación más nueva que el estándar. Hay que validar el estándar con la empresa.
- **El firmware es un tema administrativo, no técnico.** Sumar variables de la OLT por PON (% online, distancia mediana y
  potencia mediana) no mejora: el R² de CV pasa de 0,49 a 0,46 y el de
  prueba de 0,59 a 0,51. El R² ajustado de prueba cae de
  0,38 a 0,18. Estar desactualizado depende de qué
  localidades y qué modelos se actualizaron, no del estado físico de la red.

**Residuos del mejor modelo (Ridge).**
- Están centrados en cero (media -0,13 p.p. en CV).
- No son normales: Shapiro-Wilk p = 0,0032 en CV y
  0,0083 en prueba.
- Muestran heterocedasticidad leve: Breusch-Pagan p = 0,017 en CV y
  0,109 en prueba.

**Sí queda un patrón: el tamaño del puerto.** El error absoluto crece cuando el PON tiene pocos equipos (Spearman
-0,35 entre |residuo| y ONTs, p = 1.8e-08). En los
35 PON con 5 equipos o menos, el MAE es 0,157, contra
0,101 en el resto. Es esperable: el porcentaje de un puerto con 2 equipos solo puede valer
0, 50 o 100 %, y es mucho más ruidoso.

El modelo también achata los extremos: sobreestima los puertos al día y subestima los más desactualizados. Mejoras
posibles:
- ponderar cada PON por su cantidad de equipos (mínimos cuadrados ponderados);
- modelar la proporción con una regresión logística binomial.

## 6. Conclusiones

- **Ridge predice el % de firmware fuera de estándar de cada puerto** con un error medio de
  8,8 puntos porcentuales en prueba. Explica alrededor de la mitad de las diferencias
  entre puertos (R² 0,49 en validación cruzada y 0,59 en prueba).
- **Los modelos complejos no se justifican.** Con 301 puertos, el Random Forest y el Gradient Boosting memorizan
  el entrenamiento y no generalizan mejor que un modelo lineal.
- **Lo que explica el firmware fuera de estándar es administrativo.** Pesan la composición de modelos (sobre todo la
  proporción de EG8143A5) y la localidad; las variables técnicas de la OLT no agregan información.
- **Antes de usar el modelo para planificar, hay que validar con la empresa el firmware estándar de cada modelo.** Con la
  definición actual, muchos EG8143A5 con firmware más nuevo cuentan como "fuera de estándar".
