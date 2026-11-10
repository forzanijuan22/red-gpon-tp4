"""Fase 1: carga, limpieza mínima y variables derivadas del inventario de ONTs.
Reproduce y verifica (como asserts) todas las cifras de la sección 3 del CLAUDE.md."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import RAIZ, guardar_metricas  # noqa: E402

RAW = RAIZ / "data" / "raw" / "datos_normalizados.xlsx"

ALIAS_MODELO = {          # alias -> nombre canónico (según EQUIVALENCIAS_CONSOLIDADO)
    "546M": "HG8546M",
    "247H": "HG8247H5",
    "8247H5": "HG8247H5",
    "8546V": "HS8546V",
    "8545M": "HS8545M",
    "8245H5": "HG8245H5",
}
NOMBRE_LOCALIDAD = {      # solo etiquetas; confirmar nombres con el equipo
    "Bernardo de IrigoyenIrigoyenSan": "Bernardo de Irigoyen",
    "CastelarCrispi": "Castelar / Crispi",
}


def cargar():
    df = pd.read_excel(RAW, sheet_name="DATOS_NORMALIZADOS")
    eq = pd.read_excel(RAW, sheet_name="EQUIVALENCIAS_CONSOLIDADO")
    return df, eq


def preparar_onts(df):
    df = df.copy()
    df["Localidad"] = df["Localidad"].replace(NOMBRE_LOCALIDAD)
    df["Modelo_canonico"] = df["Modelo"].replace(ALIAS_MODELO)
    df["slot_n"] = df["Slot"].str.rstrip("/").astype(int)
    df["pon_n"] = df["PON"].str.rstrip("/").astype(int)
    df["card_key"] = df["Localidad"] + "|" + df["Slot"]
    df["pon_key"] = df["Localidad"] + "|" + df["Slot"] + "|" + df["PON"]
    df["onts_pon"] = df.groupby("pon_key")["ID"].transform("size")
    df["id_rel"] = df.groupby("pon_key")["ID"].rank(pct=True)   # posición relativa 0-1 dentro del PON
    df["id_alto"] = df["ID"] >= 120                              # IDs asignados a mano (124-127)
    df["moderno"] = df["Puertos_LAN"].isin(["4 GE", "2 GE + 2 FE"]) | df["WiFi_Tecnologia"].str.contains(r"Wi-Fi [56]")
    df["catv"] = df["CATV"].eq("Sí")
    df["fw_generacion"] = df["Version"].str.extract(r"^V(\d+)")[0].astype(int)
    fw_std = df.groupby("Modelo_canonico")["Version"].agg(lambda s: s.mode().iloc[0])
    df["fw_estandar"] = df["Modelo_canonico"].map(fw_std)
    df["fw_fuera_estandar"] = (df["Version"] != df["fw_estandar"]).astype(int)
    return df


def preparar_pons(onts):
    base = onts[onts["ID"] < 64]                 # los IDs altos son manuales: no cuentan para huecos
    huecos = base.groupby("pon_key")["ID"].agg(lambda s: (s.max() + 1) - s.size)
    max_id = base.groupby("pon_key")["ID"].max()
    pons = onts.groupby("pon_key").agg(
        Localidad=("Localidad", "first"), Slot=("Slot", "first"), PON=("PON", "first"),
        onts=("ID", "size"), id_medio=("ID", "mean"),
        pct_moderno=("moderno", "mean"), pct_catv=("catv", "mean"),
        pct_v3=("fw_generacion", lambda s: (s == 3).mean()),
        n_modelos=("Modelo_canonico", "nunique"), n_versiones=("Version", "nunique"),
        pct_fw_fuera=("fw_fuera_estandar", "mean"),
    )
    pons["huecos"] = huecos.reindex(pons.index).fillna(0)
    pons["pct_huecos"] = (huecos / (max_id + 1)).reindex(pons.index).fillna(0)
    shares = pd.crosstab(onts["pon_key"], onts["Modelo_canonico"], normalize="index").add_prefix("share_")
    return pons.join(shares).reset_index()


# ---------------------------------------------------------------- chequeos (sección 3)
def inconsistencias_equivalencias(df, eq):
    """Filas del inventario cuyos atributos de hardware no coinciden con EQUIVALENCIAS (por Modelo original)."""
    cols = ["Puertos_LAN", "WiFi_Tecnologia", "Modulo_Optico", "Puertos_POTS", "CATV"]
    ref = eq.drop_duplicates("Modelo_ONT").set_index("Modelo_ONT")[cols]
    esperado = ref.reindex(df["Modelo"]).reset_index(drop=True)
    real = df[cols].reset_index(drop=True)
    return int((real.astype(str) != esperado.astype(str)).any(axis=1).sum())


def chequeos_inventario(df, eq, onts, pons):
    lan = onts["Puertos_LAN"].value_counts()
    wifi = onts["WiFi_Tecnologia"].value_counts()
    por_card = onts.groupby("card_key").size()
    loc = onts.groupby("Localidad").agg(id_medio=("ID", "mean"), n=("ID", "size"), p=("pon_key", "nunique"))
    corr_loc = loc["id_medio"].corr(loc["n"] / loc["p"])
    eg = onts[(onts["Modelo_canonico"] == "EG8143A5") & (onts["Version"] == "V3R017C10S125")]
    wifi4 = wifi[wifi.index.str.startswith("Wi-Fi 4")].sum()
    wifi5 = wifi[wifi.index.str.startswith("Wi-Fi 5")].sum()
    wifi6 = wifi[wifi.index.str.startswith("Wi-Fi 6")].sum()
    bridge = wifi[wifi.index.str.contains("Bridge")].sum()
    # (nombre, esperado, obtenido, tolerancia)
    return [
        ("Filas", 5114, len(onts), 0),
        ("Localidades", 9, onts["Localidad"].nunique(), 0),
        ("Tarjetas (Localidad+Slot)", 23, onts["card_key"].nunique(), 0),
        ("Puertos PON (Localidad+Slot+PON)", 301, onts["pon_key"].nunique(), 0),
        ("Modelos (nombres originales)", 24, onts["Modelo"].nunique(), 0),
        ("Modelos canónicos", 22, onts["Modelo_canonico"].nunique(), 0),
        ("Versiones de firmware", 29, onts["Version"].nunique(), 0),
        ("Puertos 1 GE + 3 FE", 4868, lan.get("1 GE + 3 FE", 0), 0),
        ("Puertos 4 GE", 243, lan.get("4 GE", 0), 0),
        ("Puertos 1 GE", 2, lan.get("1 GE", 0), 0),
        ("Puertos 2 GE + 2 FE", 1, lan.get("2 GE + 2 FE", 0), 0),
        ("Wi-Fi 4", 4973, wifi4, 0),
        ("Wi-Fi 5", 138, wifi5, 0),
        ("Bridge (sin Wi-Fi)", 2, bridge, 0),
        ("Wi-Fi 6", 1, wifi6, 0),
        ("Equipos moderno", 244, int(onts["moderno"].sum()), 0),
        ("% moderno", 4.8, round(onts["moderno"].mean() * 100, 1), 0.05),
        ("fw_fuera_estandar = 1", 1476, int(onts["fw_fuera_estandar"].sum()), 0),
        ("% fw_fuera_estandar", 28.9, round(onts["fw_fuera_estandar"].mean() * 100, 1), 0.05),
        ("Versiones de HG8546M (con 546M)", 10, onts.loc[onts["Modelo_canonico"] == "HG8546M", "Version"].nunique(), 0),
        ("Inconsistencias contra EQUIVALENCIAS", 0, inconsistencias_equivalencias(df, eq), 0),
        ("Duplicados en Localidad+Board+Slot+PON+ID", 0,
         int(onts.duplicated(["Localidad", "Board", "Slot", "PON", "ID"]).sum()), 0),
        ("ONTs con ID >= 120 (id_alto)", 45, int(onts["id_alto"].sum()), 0),
        ("ONTs con ID 127", 31, int((onts["ID"] == 127).sum()), 0),
        ("Percentil 25 de ONTs por tarjeta", 120.5, float(por_card.quantile(0.25)), 0.05),
        ("Corr. ID medio por localidad vs ONTs por PON", 0.95, round(corr_loc, 2), 0.005),
        ("Corr. ID medio por PON vs ONTs del PON (aprox.)", 0.87, round(pons["id_medio"].corr(pons["onts"]), 2), 0.01),
        ("EG8143A5 con firmware V3R017C10S125", 391, len(eg), 0),
        ("Equipos con CATV = Sí", 1025, int(onts["catv"].sum()), 0),
        ("% con CATV", 20.0, round(onts["catv"].mean() * 100, 1), 0.05),
    ]


def chequeos_olt(onts):
    from olt import cargar_olt, preparar_obj14
    olt = cargar_olt()
    est = olt["Estado"].value_counts()
    valida = olt.dropna(subset=["Slot", "PON", "ID"])
    d = preparar_obj14(onts, olt)
    return [
        ("OLT: filas", 5804, len(olt), 0),
        ("OLT: con ubicación válida", 5780, len(valida), 0),
        ("OLT: que cruzan con el inventario", 5052, int((olt["En_inventario"] == "Sí").sum()), 0),
        ("OLT: Online", 5244, est.get("Online", 0), 0),
        ("OLT: Offline", 312, est.get("Offline", 0), 0),
        ("OLT: DyingGasp", 211, est.get("DyingGasp", 0), 0),
        ("OLT: Loss (LOS)", 33, est.get("Loss (LOS)", 0), 0),
        ("OLT: LOFi", 1, est.get("LOFi", 0), 0),
        ("OLT: Desconocido", 3, est.get("Desconocido", 0), 0),
        ("Obj. 14: dataset (online, cruzan, lectura válida)", 4872, len(d), 0),
        ("Obj. 14: en riesgo (< -25 dBm)", 548, int(d["en_riesgo"].sum()), 0),
        ("Obj. 14: % en riesgo", 11.2, round(d["en_riesgo"].mean() * 100, 1), 0.05),
    ]


def evaluar(chequeos):
    filas = []
    for nombre, esp, obt, tol in chequeos:
        ok = abs(float(obt) - float(esp)) <= tol
        obt = obt.item() if hasattr(obt, "item") else obt
        filas.append({"chequeo": nombre, "esperado": esp, "obtenido": obt, "ok": bool(ok)})
    return pd.DataFrame(filas)


def main():
    df, eq = cargar()
    onts = preparar_onts(df)
    pons = preparar_pons(onts)
    (RAIZ / "data" / "processed").mkdir(parents=True, exist_ok=True)
    onts.to_csv(RAIZ / "data" / "processed" / "onts.csv", index=False, encoding="utf-8")
    pons.to_csv(RAIZ / "data" / "processed" / "pons.csv", index=False, encoding="utf-8")

    res = evaluar(chequeos_inventario(df, eq, onts, pons) + chequeos_olt(onts))
    with pd.option_context("display.width", 200, "display.max_rows", 200, "display.max_colwidth", 60):
        print(res.to_string(index=False))
    guardar_metricas("fase1_chequeos", {
        "total": len(res), "ok": int(res["ok"].sum()),
        "detalle": {r.chequeo: {"esperado": r.esperado, "obtenido": r.obtenido, "ok": r.ok} for r in res.itertuples()},
    })
    fallan = res[~res["ok"]]
    assert fallan.empty, f"Chequeos que NO dan igual (frenar y avisar):\n{fallan.to_string(index=False)}"
    print(f"\nOK: {len(res)} de {len(res)} chequeos de la sección 3 dan igual.")
    print(f"onts.csv: {onts.shape}, pons.csv: {pons.shape}")


if __name__ == "__main__":
    main()
