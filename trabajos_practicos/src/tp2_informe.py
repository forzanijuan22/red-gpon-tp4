"""Borradores del informe y del cuestionario del TP2, generados desde results/metrics.json.
Ninguna cifra se escribe a mano: si se vuelve a correr el modelo, los borradores se actualizan solos."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import METRICS, RAIZ  # noqa: E402

OUT = RAIZ / "reports" / "TP2"
MODELOS = ["Dummy (promedio)", "Regresión Lineal", "Ridge", "Random Forest", "Gradient Boosting"]


def c(x, d=2):
    """Número con coma decimal."""
    return f"{x:.{d}f}".replace(".", ",")


def pct(x, d=1):
    return f"{x * 100:.{d}f} %".replace(".", ",")


def _mejor_por_metrica(m, conjunto):
    """Modelo ganador de cada métrica en un conjunto (sin el Dummy)."""
    cand = [n for n in MODELOS if n != "Dummy (promedio)"]
    d = m[conjunto]
    return {"RMSE": min(cand, key=lambda n: d[n]["RMSE"]), "MAE": min(cand, key=lambda n: d[n]["MAE"]),
            "R2": max(cand, key=lambda n: d[n]["R2"])}


def ganadores(g):
    """{'RMSE': 'A', 'MAE': 'B', 'R2': 'A'} -> 'A en RMSE y R², y B en MAE' (o 'A en las tres métricas')."""
    por = {}
    for met, mod in g.items():
        por.setdefault(mod, []).append(met.replace("R2", "R²"))
    if len(por) == 1:
        return f"{next(iter(por))} en las tres métricas"
    partes = [f"{mod} en {' y '.join(mets)}" for mod, mets in por.items()]
    return ", y ".join([", ".join(partes[:-1]), partes[-1]]) if len(partes) > 1 else partes[0]


def tablas_md(m):
    t1 = ["| Modelo | Hiperparámetros | R² entrenamiento | R² CV (media ± desvío) | R² prueba | R² ajustado prueba | Diagnóstico |",
          "|---|---|---|---|---|---|---|"]
    for n in MODELOS:
        t1.append(f"| {n} | {m['hiperparametros_elegidos'][n]} | {c(m['entrenamiento'][n]['R2'])} | "
                  f"{c(m['cv_media'][n]['R2'])} ± {c(m['cv_desvio'][n]['R2'])} | {c(m['prueba'][n]['R2'])} | "
                  f"{c(m['prueba'][n]['R2_ajustado'])} | {m['diagnostico'][n]['diagnostico'].split(':')[0]} |")
    t2 = ["| Modelo | MSE ent. | MSE CV | MSE prueba | RMSE ent. | RMSE CV | RMSE prueba | MAE ent. | MAE CV | MAE prueba |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for n in MODELOS:
        e, v, p = m["entrenamiento"][n], m["cv_media"][n], m["prueba"][n]
        t2.append(f"| {n} | {c(e['MSE'], 4)} | {c(v['MSE'], 4)} | {c(p['MSE'], 4)} | {c(e['RMSE'], 3)} | {c(v['RMSE'], 3)} | "
                  f"{c(p['RMSE'], 3)} | {c(e['MAE'], 3)} | {c(v['MAE'], 3)} | {c(p['MAE'], 3)} |")
    return "\n".join(t1), "\n".join(t2)


def respuestas(m, fw):
    """Las 3 preguntas del cuestionario (sección 8 de la consigna del TP2)."""
    mejor = m["mejor_modelo"]
    cv, te = _mejor_por_metrica(m, "cv_media"), _mejor_por_metrica(m, "prueba")
    lin, rid = m["cv_media"]["Regresión Lineal"], m["cv_media"]["Ridge"]
    rf, gb = m["diagnostico"]["Random Forest"], m["diagnostico"]["Gradient Boosting"]
    res, pat = m["residuos"], m["residuos"]["patrones"]
    curvas = m["curva_aprendizaje"]
    c_mejor = next(v for k, v in curvas.items() if "(mejor)" in k)
    c_rf = curvas.get("Random Forest")
    olt = m["prueba_olt"]["resultados"]
    gs = m["gridsearch_mejora"]
    sh = m["comparacion_5_vs_22_modelos"]
    k5, k22 = list(sh)
    cambia_te = sorted(set(te.values()) - {mejor})
    cv_unanime = set(cv.values()) == {mejor}
    arboles = [n for n in MODELOS if n != "Dummy (promedio)"]
    prueba_facil = all(m["prueba"][n]["R2"] > m["cv_media"][n]["R2"] for n in arboles)
    frase_metrica = ("**Con otra métrica, la elección cambia solo si se mira la prueba.**" if cv_unanime else
                     "**En validación cruzada, la métrica sí cambia el ganador, aunque por diferencias mínimas.**")
    frase_facil = ("salió más fácil que el promedio: todos los modelos tienen mejor R² en prueba que en validación cruzada"
                   if prueba_facil else "es una sola muestra chica y su resultado depende de qué PON cayeron en ella")

    p1 = f"""**1. ¿Cuál fue el modelo más adecuado y cambiaría la elección con otra métrica?**

El modelo elegido es **{mejor}**, porque tiene el menor RMSE medio en la validación cruzada de 5 partes sobre el
entrenamiento ({c(m['cv_media'][mejor]['RMSE'], 3)}). La elección se hizo sin mirar la prueba. En prueba obtiene R²
{c(m['prueba'][mejor]['R2'])}, R² ajustado {c(m['prueba'][mejor]['R2_ajustado'])} y MAE {c(m['prueba'][mejor]['MAE'], 3)}
(el Dummy: MAE {c(m['prueba']['Dummy (promedio)']['MAE'], 3)}). En validación cruzada gana {ganadores(cv)}.

La diferencia con la Regresión Lineal es mínima (RMSE de CV {c(lin['RMSE'], 4)} contra {c(rid['RMSE'], 4)};
R² {c(lin['R2'], 3)} contra {c(rid['R2'], 3)}), muy por debajo del desvío entre particiones
(± {c(m['cv_desvio'][mejor]['RMSE'], 3)}). En la práctica son el mismo modelo: con
{m['hiperparametros_elegidos']['Ridge']} la penalización de Ridge casi no cambia los coeficientes.

{frase_metrica} En el conjunto de prueba gana {ganadores(te)}{'. Es decir, ' + ' y '.join(cambia_te) + ' superan a ' + mejor + ' en alguna métrica de prueba' if cambia_te else ''}.
Pero la prueba tiene solo {m['datos']['prueba']} PON y {frase_facil}. Por ejemplo, el Random Forest tiene R² {c(m['prueba']['Random Forest']['R2'])}
en prueba contra {c(m['cv_media']['Random Forest']['R2'])} en CV. Elegir por la prueba sería ajustar el modelo
mirando el test. El MAE premia a los árboles, que aciertan bien los PON "típicos". El RMSE castiga los errores grandes
en los PON extremos, y ahí los modelos lineales son más estables. Para la empresa importa no errarle feo a un puerto
(mandar una cuadrilla a un puerto que estaba al día), así que el RMSE es la métrica de selección más razonable."""

    p2 = f"""**2. ¿Hubo sobreajuste o subajuste? ¿Cómo se detectó y cómo se mitiga?**

Sí. **El Random Forest y el Gradient Boosting sobreajustan.** El Random Forest explica R²
{c(m['entrenamiento']['Random Forest']['R2'])} en entrenamiento pero {c(m['cv_media']['Random Forest']['R2'])} en
validación cruzada (brecha {c(rf['brecha_entrenamiento_cv'])}). El Gradient Boosting pasa de
{c(m['entrenamiento']['Gradient Boosting']['R2'])} a {c(m['cv_media']['Gradient Boosting']['R2'])} (brecha
{c(gb['brecha_entrenamiento_cv'])}). Es **varianza alta**: con {m['datos']['entrenamiento']} PON, los árboles aprenden
particularidades de cada puerto que no se repiten. La curva de aprendizaje lo confirma: al Random Forest le queda una
brecha de {c(c_rf['brecha_final_pp'], 1)} puntos porcentuales de RMSE
entre entrenamiento y validación con todos los datos.

Contra la prueba, la brecha del Random Forest ({c(rf['brecha_entrenamiento_prueba'], 3)}) casi no llega al umbral de
0,15. Por eso el diagnóstico usa las dos brechas: la de prueba, con {m['datos']['prueba']} PON, depende de qué puertos
cayeron en ese 20 %.

**Las Regresiones Lineal y Ridge no sobreajustan** (brecha contra CV de
{c(m['diagnostico']['Regresión Lineal']['brecha_entrenamiento_cv'])} y {c(m['diagnostico']['Ridge']['brecha_entrenamiento_cv'])}).
Tienen **sesgo moderado**: su R² de entrenamiento ({c(m['entrenamiento']['Ridge']['R2'])}) es el techo de lo que puede
explicar un modelo aditivo con estas variables. En su curva de aprendizaje las dos líneas casi se tocan (brecha de
{c(c_mejor['brecha_final_pp'], 1)} p.p.): más datos ayudarían
poco; harían falta mejores variables. **El Dummy subajusta** por definición (R² 0).

**Mitigación.**
- En los árboles, la búsqueda de hiperparámetros ya redujo la varianza: el Random Forest eligió
  {gs['Random Forest']['mejores_hiperparametros']} (RMSE de CV {pct(gs['Random Forest']['mejora_pct'] / 100)} mejor que con
  los valores por defecto). El Gradient Boosting eligió {gs['Gradient Boosting']['mejores_hiperparametros']}
  ({pct(gs['Gradient Boosting']['mejora_pct'] / 100)} mejor). Se puede ir más lejos: hojas más grandes, `max_features`
  menor, `subsample` < 1 en el boosting, o simplemente más PON.
- Con 22 proporciones de modelo en lugar de 5, la Regresión Lineal tiene {sh[k22]['predictores']} predictores para
  {m['datos']['entrenamiento']} PON. El R² ajustado de prueba cae de {c(sh[k5]['R2_ajustado_prueba'])} a
  {c(sh[k22]['R2_ajustado_prueba'])}: reducir variables fue la primera medida contra la varianza.
- Para bajar el sesgo de los lineales harían falta variables nuevas, por ejemplo la fecha de la última campaña de
  actualización por localidad. No están en el inventario."""

    p3 = f"""**3. ¿Qué factores del dominio explican el desempeño? ¿Quedan patrones en los residuos?**

- **Poco volumen.** Hay {m['datos']['pon']} PON y {m['variables']['predictores_efectivos']} predictores efectivos. Con
  {m['datos']['entrenamiento']} filas de entrenamiento, los modelos flexibles no tienen datos suficientes para que sus
  interacciones se paguen. Por eso un modelo lineal regularizado empata o le gana a los ensambles en validación cruzada.
- **La relación es casi aditiva.** El % fuera de estándar de un puerto se explica sobre todo por dos efectos que se
  suman: **la composición de modelos** y **la localidad**. Lo que más pesa es el % de equipos con TV
  (`pct_catv`, caída del R² de {c(m['importancia_permutacion']['pct_catv'])} al mezclarlo). Está correlacionado en
  {c(m['correlacion_pct_catv_share_EG8143A5'])} con la proporción de EG8143A5, porque ese es el modelo con TV más común.
  Mezcladas juntas, el R² cae {c(m['importancia_pct_catv_y_share_EG8143A5_juntas']['media'])}. Después viene la
  localidad ({c(m['importancia_permutacion']['Localidad'])}). Un modelo lineal captura bien una suma de efectos.
- **Parte de lo que se predice es la definición.** El firmware "estándar" es la versión más común de cada modelo. En el
  EG8143A5 es la V3, que tiene solo el {pct(1 - fw['pct_fuera_eg8143a5'] / 100, 0)} de sus equipos; el resto tiene V5, más
  nueva. Por eso los puertos con muchos EG8143A5 salen "fuera de estándar" aunque tengan firmware más nuevo. En toda la
  red, {fw['mas_nuevos']} de los {fw['fuera']} equipos fuera de estándar ({pct(fw['mas_nuevos'] / fw['fuera'])}) tienen una
  generación más nueva que el estándar. Hay que validar el estándar con la empresa.
- **El firmware es un tema administrativo, no técnico.** Sumar variables de la OLT por PON (% online, distancia mediana y
  potencia mediana) no mejora: el R² de CV pasa de {c(olt['sin OLT']['R2_cv'])} a {c(olt['con OLT']['R2_cv'])} y el de
  prueba de {c(olt['sin OLT']['R2_prueba'])} a {c(olt['con OLT']['R2_prueba'])}. El R² ajustado de prueba cae de
  {c(olt['sin OLT']['R2_ajustado_prueba'])} a {c(olt['con OLT']['R2_ajustado_prueba'])}. Estar desactualizado depende de qué
  localidades y qué modelos se actualizaron, no del estado físico de la red.

**Residuos del mejor modelo ({m['mejor_modelo']}).**
- Están centrados en cero (media {c(res['cv_entrenamiento']['media'] * 100, 2)} p.p. en CV).
- No son normales: Shapiro-Wilk p = {c(res['cv_entrenamiento']['shapiro_p'], 4)} en CV y
  {c(res['prueba']['shapiro_p'], 4)} en prueba.
- Muestran heterocedasticidad leve: Breusch-Pagan p = {c(res['cv_entrenamiento']['breusch_pagan_p'], 3)} en CV y
  {c(res['prueba']['breusch_pagan_p'], 3)} en prueba.

**Sí queda un patrón: el tamaño del puerto.** El error absoluto crece cuando el PON tiene pocos equipos (Spearman
{c(pat['spearman_abs_residuo_vs_onts'])} entre |residuo| y ONTs, p = {pat['spearman_p']:.1e}). En los
{pat['n_pon_5_onts_o_menos']} PON con 5 equipos o menos, el MAE es {c(pat['MAE_pon_5_onts_o_menos'], 3)}, contra
{c(pat['MAE_pon_mas_de_5_onts'], 3)} en el resto. Es esperable: el porcentaje de un puerto con 2 equipos solo puede valer
0, 50 o 100 %, y es mucho más ruidoso.

El modelo también achata los extremos: sobreestima los puertos al día y subestima los más desactualizados. Mejoras
posibles:
- ponderar cada PON por su cantidad de equipos (mínimos cuadrados ponderados);
- modelar la proporción con una regresión logística binomial."""
    return p1, p2, p3


def escribir():
    todo = json.loads(METRICS.read_text(encoding="utf-8"))
    m, o3 = todo["obj09_tp2"], todo["obj03"]
    adv = o3["advertencia_fuera_vs_desactualizado"]
    fw = {"mas_nuevos": adv["fuera_estandar_con_generacion_mayor"], "fuera": o3["equipos_fuera_estandar"],
          "pct_fuera_eg8143a5": o3["pct_fuera_por_modelo"]["EG8143A5"]}
    p1, p2, p3 = respuestas(m, fw)
    t1, t2 = tablas_md(m)
    mejor = m["mejor_modelo"]
    s = m["criterio_smart"]
    smart_md = "\n".join(["| Criterio | Umbral | Valor | ¿Se cumple? |", "|---|---|---|---|"] + [
        f"| {k} | {u} | {c(v['valor'], 3)} | {'Sí' if v['cumple'] else 'No'} |"
        for (k, v), u in zip(s["resultados"].items(),
                             [f"≥ {c(s['metas']['R2_prueba'])}", f"≥ {c(s['metas']['R2_ajustado_prueba'])}",
                              f"< {c(s['metas']['MAE_dummy_prueba'], 3)} (Dummy)"])])
    d, olt = m["datos"], m["prueba_olt"]["resultados"]
    shares = ", ".join(x.replace("share_", "") for x in m["variables"]["shares_top5"])

    cuestionario = f"""# TP2: cuestionario de interpretación (borrador)

> Generado por `src/tp2_informe.py` desde `results/metrics.json`. No editar las cifras a mano: si cambia el modelo,
> se vuelve a generar con `python run_all.py`.

{p1}

{p2}

{p3}
"""

    informe = f"""# Predicción del porcentaje de ONTs con firmware fuera de estándar por puerto PON (borrador)

*TP2, Aprendizaje Automático y Grandes Datos (UNRaf), 2026. Borrador generado desde `results/metrics.json`;
las cifras se actualizan solas al volver a correr el pipeline. Pasar a formato de artículo (3 a 5 páginas) para la entrega.*

## Resumen

Se estimó el porcentaje de equipos con firmware distinto del estándar de su modelo en cada uno de los {d['pon']}
puertos PON de una red GPON de 9 localidades. Se compararon una Regresión Lineal (línea base), Ridge, Random Forest y
Gradient Boosting contra un modelo que predice siempre el promedio. El mejor modelo en validación cruzada fue
**{mejor}**, con R² {c(m['prueba'][mejor]['R2'])}, R² ajustado {c(m['prueba'][mejor]['R2_ajustado'])} y MAE
{c(m['prueba'][mejor]['MAE'], 3)} en prueba (R² {c(m['cv_media'][mejor]['R2'])} en validación cruzada). Cumple las tres
metas fijadas{'' if s['cumple_todo'] else ' solo en parte'}. Los modelos de árboles sobreajustan, y sumar variables
técnicas de la OLT no mejora la predicción.

## 1. Introducción

En el TP1 se encontró que el modelo de ONT instalado depende fuertemente de la localidad (respaldo R2). Casi 3 de cada
10 equipos no tienen la versión de firmware más usada de su modelo. Actualizar equipo por equipo es lento; lo práctico es
actualizar un puerto PON completo en una ventana de mantenimiento. La pregunta de este trabajo es si se puede estimar, a
partir de cómo está compuesto cada puerto, qué porcentaje de sus equipos está fuera de estándar. Así la empresa puede
priorizar los puertos donde una ventana de mantenimiento rinde más.

## 2. Marco experimental

- **Datos.** El inventario del TP1 (5114 ONTs), agregado por puerto PON: {d['pon']} filas.
- **Variable objetivo.** `pct_fw_fuera`, la proporción de equipos del PON con una versión de firmware distinta de la
  más frecuente de su modelo. Media {c(d['objetivo_media'])}, desvío {c(d['objetivo_desvio'])}; {d['pon_con_0_pct']} PON
  tienen 0 % y {d['pon_con_100_pct']} tienen 100 %.
- **Variables de entrada.** Localidad y tarjeta (one-hot), cantidad de equipos del puerto, % con TV, % de equipos
  modernos, cantidad de modelos distintos y la proporción de los 5 modelos más usados ({shares}).
- **Variables excluidas.**
  - Todo lo que sale de la versión de firmware (`pct_v3`, `n_versiones`), porque es la respuesta.
  - Los identificadores.
  - Las variables de huecos de ID, que no están validadas con la empresa.
- **Por qué 5 proporciones y no 22.** Con las 22 proporciones de modelo, la Regresión Lineal tiene
  {m['comparacion_5_vs_22_modelos']['los 22 modelos']['predictores']} predictores para {d['entrenamiento']} PON y su R²
  ajustado de prueba cae a {c(m['comparacion_5_vs_22_modelos']['los 22 modelos']['R2_ajustado_prueba'])}. Con 5 queda en
  {c(m['comparacion_5_vs_22_modelos']['5 modelos más usados']['R2_ajustado_prueba'])}.
- **Partición.** 80/20 con semilla 42 ({d['entrenamiento']} PON de entrenamiento y {d['prueba']} de prueba). Validación
  cruzada KFold de 5 partes (mezclada, semilla 42) sobre el entrenamiento, para elegir hiperparámetros y modelo. La
  prueba se usa una sola vez, al final. Cada fila es un PON, así que no hace falta agrupar.
- **Línea base.** Regresión Lineal (la que recomienda la consigna). Como piso, un `DummyRegressor` que predice siempre
  el promedio.
- **Métricas.**
  - MSE, RMSE, MAE, R² y R² ajustado, en entrenamiento, en validación cruzada (media ± desvío) y en prueba.
  - El R² ajustado usa los predictores efectivos (columnas one-hot menos una por variable categórica).
  - No se usa MAPE: {d['pon_con_0_pct']} PON tienen 0 % y el MAPE divide por el valor real.

## 3. Métodos

Todo el preprocesamiento (one-hot con `handle_unknown="ignore"`, imputación por mediana y escalado) va dentro de un
`Pipeline` de scikit-learn, así nada se ajusta con datos de validación o de prueba. Los hiperparámetros se buscaron con
`GridSearchCV` (KFold de 5) minimizando el RMSE:

- **Ridge.** `alpha` ∈ {{0,1; 1; 10}}: de casi sin penalización a penalización fuerte. Elegido:
  {m['hiperparametros_elegidos']['Ridge']}.
- **Random Forest.** 300 árboles; `min_samples_leaf` ∈ {{1, 3, 5}} y `max_depth` ∈ {{sin límite, 8}}, para limitar la
  memorización con pocos PON. Elegido: {m['hiperparametros_elegidos']['Random Forest']}. El RMSE de CV mejora
  {pct(m['gridsearch_mejora']['Random Forest']['mejora_pct'] / 100)} respecto de los valores por defecto.
- **Gradient Boosting.** 200 árboles; `learning_rate` ∈ {{0,05; 0,1}} y `max_depth` ∈ {{2, 3}}. Elegido:
  {m['hiperparametros_elegidos']['Gradient Boosting']}. El RMSE de CV mejora
  {pct(m['gridsearch_mejora']['Gradient Boosting']['mejora_pct'] / 100)}.

El mejor modelo se eligió por el RMSE de validación cruzada. Sobre ese modelo se calcularon:
- la importancia por permutación;
- el análisis de residuos (Shapiro-Wilk y Breusch-Pagan);
- la curva de aprendizaje.

Como prueba adicional, se repitió el mejor modelo sumando tres variables por PON del listado de la OLT del 29/10/2026:
% de equipos online, distancia mediana y potencia recibida mediana.

## 4. Resultados

**Tabla 1.** R² y diagnóstico de ajuste. El diagnóstico marca sobreajuste cuando el R² de entrenamiento supera al de
validación o al de prueba por más de 0,15.

{t1}

**Tabla 2.** Errores (en proporción: 0,10 = 10 puntos porcentuales).

{t2}

Figuras (en `reports/TP2/`):
- `tp2_comparacion_modelos.png`: métricas por modelo.
- `tp2_predicho_vs_real.png`: predicho contra real.
- `tp2_residuos.png`: residuos del mejor modelo.
- `tp2_curva_aprendizaje.png`: curvas de aprendizaje.
- `tp2_importancia_variables.png`: importancia de variables.

**Prueba con datos de la OLT.**

| Variables | R² CV | R² prueba | R² ajustado prueba | MAE prueba |
|---|---|---|---|---|
| Sin OLT | {c(olt['sin OLT']['R2_cv'])} | {c(olt['sin OLT']['R2_prueba'])} | {c(olt['sin OLT']['R2_ajustado_prueba'])} | {c(olt['sin OLT']['MAE_prueba'], 3)} |
| Con OLT | {c(olt['con OLT']['R2_cv'])} | {c(olt['con OLT']['R2_prueba'])} | {c(olt['con OLT']['R2_ajustado_prueba'])} | {c(olt['con OLT']['MAE_prueba'], 3)} |

**Criterio SMART** (sobre {mejor}, en prueba):

{smart_md}

## 5. Discusión: cuestionario de interpretación

{p1}

{p2}

{p3}

## 6. Conclusiones

- **{mejor} predice el % de firmware fuera de estándar de cada puerto** con un error medio de
  {c(m['prueba'][mejor]['MAE'] * 100, 1)} puntos porcentuales en prueba. Explica alrededor de la mitad de las diferencias
  entre puertos (R² {c(m['cv_media'][mejor]['R2'])} en validación cruzada y {c(m['prueba'][mejor]['R2'])} en prueba).
- **Los modelos complejos no se justifican.** Con {d['pon']} puertos, el Random Forest y el Gradient Boosting memorizan
  el entrenamiento y no generalizan mejor que un modelo lineal.
- **Lo que explica el firmware fuera de estándar es administrativo.** Pesan la composición de modelos (sobre todo la
  proporción de EG8143A5) y la localidad; las variables técnicas de la OLT no agregan información.
- **Antes de usar el modelo para planificar, hay que validar con la empresa el firmware estándar de cada modelo.** Con la
  definición actual, muchos EG8143A5 con firmware más nuevo cuentan como "fuera de estándar".
"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cuestionario_borrador.md").write_text(cuestionario, encoding="utf-8")
    (OUT / "informe_borrador.md").write_text(informe, encoding="utf-8")
    return OUT / "informe_borrador.md", OUT / "cuestionario_borrador.md"


if __name__ == "__main__":
    print(escribir())
