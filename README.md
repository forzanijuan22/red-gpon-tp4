# Red GPON: firmware por puerto y señal de la fibra en riesgo

Aplicación web del proyecto integrador de **Aprendizaje Automático y Grandes Datos** (UNRaf, 2026). Despliega los dos
modelos elegidos sobre el inventario de equipos (ONT) de una empresa de fibra óptica y el listado de su central (OLT):

| Apartado | Modelo | Qué hace |
|---|---|---|
| TP2 · Regresión | Ridge (`modelos/tp2_ridge.joblib`) | Estima qué % de los equipos de cada puerto PON tiene el firmware fuera de estándar y ordena qué puertos actualizar primero. |
| TP3 · Clasificación | Regresión logística (`modelos/tp3_regresion_logistica.joblib`) | Estima si un cliente nuevo quedaría con la señal de la fibra en riesgo (menos de −25 dBm) según el puerto donde se lo conecte. |

Además tiene un resumen del TP1, una vista de los tres trabajos y la metodología. En las pestañas **Probar un caso nuevo**
el usuario carga valores con controles (rangos validados) y el modelo responde en el momento; si un valor está fuera de
lo que el modelo vio, la aplicación lo avisa.

## Ejecutar en la computadora

Requiere Python 3.13 (probado con 3.13.14).

```
pip install -r requirements.txt
streamlit run dashboards/app.py
```

Se abre en http://localhost:8501 (o `python dashboards/lanzar.py`, que aplica el mismo tema y puerto).

## Estructura

```
dashboards/          código de la aplicación (app.py arma el menú; paginas/ tiene un archivo por apartado)
modelos/             modelos serializados con joblib (pipeline completo: codificación, escalado y modelo)
data/app/            resúmenes por puerto, por localidad, por modelo y por tramos de señal
data/processed/      resumen por puerto PON (TP2)
results/, reports/   métricas y tablas que muestra la aplicación
.streamlit/          tema de colores
trabajos_practicos/  material académico: notebooks, informes, presentaciones y código de los TP1 a TP3
```

El material académico de los TP1, TP2 y TP3 (notebooks ejecutados, informes, presentaciones, código y figuras) está en [`trabajos_practicos/`](trabajos_practicos/).

Los modelos se entrenaron con scikit-learn 1.9.1; por eso esa versión está fija en `requirements.txt`
(un modelo guardado con joblib se debe cargar con la misma versión).

## Datos

Los datos son de una empresa de telecomunicaciones. La aplicación usa una versión **anonimizada**: las localidades se
reemplazaron por letras («Localidad A» a «Localidad I») y solo trae resúmenes por puerto, por localidad y por modelo. El
repositorio no incluye el inventario equipo por equipo, la señal de cada cliente, números de serie, direcciones IP ni
los archivos originales de la empresa.

## Autores

Juan Ignacio Forzani, Alejo Racca y Agustín Cesano. Universidad Nacional de Rafaela (UNRaf), Rafaela, Santa Fe, Argentina.
