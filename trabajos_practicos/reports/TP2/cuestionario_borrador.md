# TP2: cuestionario de interpretación (borrador)

> Generado por `src/tp2_informe.py` desde `results/metrics.json`. No editar las cifras a mano: si cambia el modelo,
> se vuelve a generar con `python run_all.py`.

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
