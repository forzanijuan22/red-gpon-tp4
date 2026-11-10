"""Helpers compartidos: métricas, figuras, formato en español."""
import json
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
METRICS = RAIZ / "results" / "metrics.json"
FIG_DIR = RAIZ / "reports" / "figures"
TABLAS = RAIZ / "reports" / "tables"

# La consola de Windows usa cp1252 por defecto: forzamos UTF-8 para que se vean tildes y "Sí".
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _a_json(x):
    """Convierte tipos de numpy/pandas a tipos nativos para guardar en JSON."""
    if isinstance(x, dict):
        return {str(k): _a_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_a_json(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if np.isnan(x) else float(x)
    return x


def guardar_metricas(clave, valores):
    """Agrega/reemplaza la clave de un objetivo en results/metrics.json (todas las cifras salen del código)."""
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    datos = json.loads(METRICS.read_text(encoding="utf-8")) if METRICS.exists() else {}
    datos[clave] = _a_json(valores)
    METRICS.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def guardar_tabla(df, nombre, index=False):
    """Guarda una tabla en reports/tables/ (UTF-8 con BOM, para que Excel respete las tildes)."""
    TABLAS.mkdir(parents=True, exist_ok=True)
    ruta = TABLAS / nombre
    df.to_csv(ruta, index=index, encoding="utf-8-sig")
    return ruta


def guardar_figura(fig, nombre, carpeta=None, dpi=150):
    carpeta = Path(carpeta) if carpeta else FIG_DIR
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre
    fig.savefig(ruta, dpi=dpi, facecolor="white", bbox_inches="tight")
    return ruta


def pct_es(x, dec=1):
    """12.34 -> '12,3 %' (coma decimal)."""
    return f"{x:.{dec}f} %".replace(".", ",")


def miles_es(n):
    return f"{int(n):,}".replace(",", ".")
