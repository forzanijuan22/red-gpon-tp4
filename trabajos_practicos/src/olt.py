"""Carga del listado de la OLT y dataset del objetivo 14 (usado desde la Fase 4)."""
from pathlib import Path

import numpy as np
import pandas as pd

OLT = Path(__file__).resolve().parent.parent / "data" / "raw" / "ONTs_OLT_limpio_29-10-2026.xlsx"   # hoja "ONTs": listado de la OLT ya limpio


def cargar_olt():
    return pd.read_excel(OLT, sheet_name="ONTs")


def preparar_obj14(onts, olt):
    """Dataset del objetivo 14: equipos online que cruzan con el inventario y tienen lectura válida."""
    o = olt.dropna(subset=["Slot", "PON", "ID"]).copy()
    o[["Slot", "PON", "ID"]] = o[["Slot", "PON", "ID"]].astype(int)
    # señal media de los VECINOS del mismo PON (online, sin contar al propio equipo)
    o["pk"] = o["Localidad"] + "|" + o["Slot"].astype(str) + "|" + o["PON"].astype(str)
    on_all = o[o["Estado"].eq("Online")]
    s = on_all.groupby("pk")["RXP_dBm"].agg(["sum", "count"])
    d = onts.merge(o[["Localidad", "Slot", "PON", "ID", "pk", "Estado", "RXP_dBm", "Distancia_m"]],
                   left_on=["Localidad", "slot_n", "pon_n", "ID"], right_on=["Localidad", "Slot", "PON", "ID"], how="inner")
    d = d[d["Estado"].eq("Online") & d["RXP_dBm"].notna()].copy()
    ss = s.reindex(d["pk"])
    with np.errstate(invalid="ignore", divide="ignore"):
        d["vec_rxp"] = (ss["sum"].values - d["RXP_dBm"].values) / (ss["count"].values - 1)
    d["vec_rxp"] = d["vec_rxp"].replace([np.inf, -np.inf], np.nan)   # PON con un solo equipo: imputar en el pipeline
    d["en_riesgo"] = (d["RXP_dBm"] < -25).astype(int)          # objetivo
    return d.reset_index(drop=True)
