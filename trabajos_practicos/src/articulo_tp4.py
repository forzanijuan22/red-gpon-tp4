"""TP4: artículo científico integrador, armado sobre la plantilla de la cátedra (reports/TP4/plantilla/Plantilla_Paper.docx).

Conserva la plantilla tal cual (encabezado, márgenes, estilos, secciones de una y dos columnas) y reemplaza su contenido de
ejemplo por el artículo. Todas las cifras salen de results/metrics.json; las figuras, de src/articulo_figuras.py y de las
capturas de la aplicación (reports/TP4/capturas). Las partes que el equipo tiene que completar (correo del autor de
correspondencia, URL de la aplicación y del repositorio) quedan resaltadas en amarillo.

Correr:  python src/articulo_tp4.py          (genera el .docx)
         python src/articulo_tp4.py --pdf    (además lo exporta a PDF con Microsoft Word, solo en Windows)"""
import ast
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm
from docx.text.paragraph import Paragraph
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import METRICS, RAIZ  # noqa: E402

PLANTILLA = RAIZ / "reports" / "TP4" / "plantilla" / "Plantilla_Paper.docx"
FIGURAS = RAIZ / "reports" / "TP4" / "figuras"
CAPTURAS = RAIZ / "reports" / "TP4" / "capturas"
DESTINO = RAIZ / "informes y presentaciones" / "TP4_articulo.docx"
DESTINO_CORTO = RAIZ / "informes y presentaciones" / "version_8_paginas" / "TP4_articulo_8p.docx"
ANCHO_COLUMNA = 6.9    # cm: la columna angosta de la plantilla mide 7,05 cm
ANCHO_PAGINA = 12.0    # cm: el texto a una columna mide 16,5 cm
AUTORES = "Juan Ignacio Forzani**; Alejo Racca**; Agustín Cesano**"
# Completar después de publicar la aplicación y volver a correr:  python src/articulo_tp4.py --pdf
# (mientras estén vacíos, el artículo muestra un texto resaltado en amarillo para completar)
CORREO = "forzanijuan@gmail.com; alejoracca07@gmail.com; agustincesano09@gmail.com"   # en el orden de AUTORES
URL_APP = "https://red-gpon-tp4.streamlit.app"
URL_REPO = "https://github.com/forzanijuan22/red-gpon-tp4"
# Versión oficial: 10 páginas (el profe aceptó hasta 13). Con --8 se arma la versión reducida de 8 páginas, sin las
# figuras y secciones extra (importancia de variables, umbral, segunda figura de la aplicación, reproducibilidad).
LARGO = "--8" not in sys.argv
TITULO = ("Del inventario al despliegue: modelos de aprendizaje automático para priorizar el mantenimiento de una red GPON")


def W(tag):
    return qn("w:" + tag)


# ------------------------------------------------------------------ formato de números
def c(x, d=2):
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def n(x):
    return f"{int(round(x)):,}".replace(",", ".")


# ------------------------------------------------------------------ armado de párrafos sobre los modelos de la plantilla
def rpr(sz=None, b=False, i=False, resaltar=False, sup=False, sub=False):
    """Propiedades de un fragmento de texto: Arial, en español, con el tamaño y el estilo pedidos."""
    r = OxmlElement("w:rPr")
    f = OxmlElement("w:rFonts")
    for a in ("ascii", "eastAsia", "hAnsi", "cs"):
        f.set(W(a), "Arial")
    r.append(f)
    if b:
        r.append(OxmlElement("w:b"))
    if i:
        r.append(OxmlElement("w:i"))
    if sz:
        for t in ("sz", "szCs"):
            e = OxmlElement("w:" + t); e.set(W("val"), str(sz)); r.append(e)
    if resaltar:
        e = OxmlElement("w:highlight"); e.set(W("val"), "yellow"); r.append(e)
    if sup or sub:
        e = OxmlElement("w:vertAlign"); e.set(W("val"), "superscript" if sup else "subscript"); r.append(e)
    lang = OxmlElement("w:lang"); lang.set(W("val"), "es-AR"); r.append(lang)
    return r


def fragmento(texto, **kw):
    r = OxmlElement("w:r")
    r.append(rpr(**kw))
    t = OxmlElement("w:t"); t.text = texto; t.set(qn("xml:space"), "preserve")
    r.append(t)
    return r


CITA = re.compile(r"\[@([\w@, ]+)\]")
ORDEN_CITAS = {}


def citar(texto):
    def numero(mo):
        claves = [k.strip().lstrip("@") for k in mo.group(1).split(",")]
        for k in claves:
            assert k in REFERENCIAS, f"cita desconocida: {k}"
            ORDEN_CITAS.setdefault(k, len(ORDEN_CITAS) + 1)
        return ", ".join(f"[{ORDEN_CITAS[k]}]" for k in claves)
    return CITA.sub(numero, texto)


MARCAS = re.compile(r"(\*\*.+?\*\*|\*.+?\*|\[\[.+?\]\]|_\{.+?\})")


def escribir(p, texto, sz=None, b=False, i=False, marcas=True):
    """Agrega texto con marcas simples: *cursiva* (términos en inglés), **negrita** y [[para completar]] (resaltado)."""
    partes = MARCAS.split(citar(texto)) if marcas else [texto]
    for parte in partes:
        if not parte:
            continue
        if marcas and parte.startswith("**"):
            p.append(fragmento(parte[2:-2], sz=sz, b=True, i=i))
        elif marcas and parte.startswith("*"):
            p.append(fragmento(parte[1:-1], sz=sz, b=b, i=not i))   # dentro de un texto en cursiva, la marca la quita
        elif marcas and parte.startswith("_{"):
            p.append(fragmento(parte[2:-1], sz=sz, b=b, i=i, sub=True))
        elif marcas and parte.startswith("[["):
            p.append(fragmento(parte[2:-2], sz=sz, b=b, i=i, resaltar=True))
        else:
            p.append(fragmento(parte, sz=sz, b=b, i=i))
    return p


def vaciar(p):
    for hijo in list(p):
        if hijo.tag != W("pPr"):
            p.remove(hijo)
    return p


ORDEN_PPR = ["pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
             "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
             "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind",
             "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc", "textDirection", "textAlignment",
             "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr", "pPrChange"]


def poner_ppr(p, tag, attrs=None):
    """Agrega (o reemplaza) una propiedad de párrafo en el lugar que exige el esquema de Word."""
    ppr = p.find(W("pPr"))
    vieja = ppr.find(W(tag))
    if vieja is not None:
        ppr.remove(vieja)
    e = OxmlElement("w:" + tag)
    for k, v in (attrs or {}).items():
        e.set(W(k), v)
    pos = ORDEN_PPR.index(tag)
    ref = next((x for x in ppr if x.tag.split("}")[1] in ORDEN_PPR and ORDEN_PPR.index(x.tag.split("}")[1]) > pos), None)
    if ref is not None:
        ref.addprevious(e)
    else:
        ppr.append(e)


class Articulo:
    def __init__(self):
        self.doc = Document(PLANTILLA)
        self.body = self.doc.element.body
        els = list(self.body)
        self.modelo = {k: copy.deepcopy(els[i]) for k, i in
                       dict(h1=14, p=15, h2=24, img=31, pie=33, ttab=37, tabla=38, h_ref=63, ref=65).items()}
        self.final = self.body.sectPr          # sección de dos columnas (la del cuerpo)
        self.nfig = 0
        self.ntab = 0
        self.portada(els)
        for e in els[14:]:
            if e is not self.final:
                self.body.remove(e)

    # --- portada: título, autores, afiliación, resumen y palabras clave
    def portada(self, els):
        escribir(vaciar(els[0]), TITULO, sz=32, marcas=False)
        escribir(vaciar(els[2]), AUTORES, sz=22, marcas=False)
        self.body.remove(els[4])            # afiliación de las carreras AGRO / BIO: no corresponde a este equipo
        p = vaciar(els[6])
        p.append(fragmento("(**) Autores Corresp.: " if ";" in CORREO else "(**) Autor Corresp.: ", sz=18))
        p.append(fragmento(CORREO or "[completar con el correo del autor de correspondencia]", sz=18, resaltar=not CORREO))
        escribir(vaciar(els[8]), "Resumen", b=True)
        self.p_resumen = vaciar(els[9])
        self.body.remove(els[10])
        self.p_claves = vaciar(els[11])

    def resumen(self, texto, claves):
        palabras = len(MARCAS.sub(lambda mo: mo.group(0).strip("*[]_{}"), texto).split())
        assert palabras <= 200, f"el resumen tiene {palabras} palabras (máximo 200)"
        escribir(self.p_resumen, texto)
        assert len(claves) <= 6
        self.p_claves.append(fragmento("Palabras claves:", b=True))
        escribir(self.p_claves, " " + ", ".join(claves) + ".")
        return palabras

    # --- cuerpo
    def _agregar(self, e):
        self.final.addprevious(e)
        return e

    def h1(self, texto):
        return self._agregar(escribir(vaciar(copy.deepcopy(self.modelo["h1"])), texto))

    def h2(self, texto):
        return self._agregar(escribir(vaciar(copy.deepcopy(self.modelo["h2"])), texto))

    def p(self, texto):
        return self._agregar(escribir(vaciar(copy.deepcopy(self.modelo["p"])), texto))

    def ecuacion(self, texto):
        p = vaciar(copy.deepcopy(self.modelo["p"]))
        poner_ppr(p, "spacing", {"before": "60", "after": "60"})
        poner_ppr(p, "ind", {"firstLine": "0"})
        poner_ppr(p, "jc", {"val": "center"})
        return self._agregar(escribir(p, texto))

    def figura(self, ruta, pie, ancho=ANCHO_COLUMNA):
        self.nfig += 1
        p = vaciar(copy.deepcopy(self.modelo["img"]))
        poner_ppr(p, "keepNext")
        poner_ppr(p, "spacing", {"before": "120", "after": "40"})
        poner_ppr(p, "jc", {"val": "center"})
        self._agregar(p)
        Paragraph(p, self.doc._body).add_run().add_picture(str(ruta), width=Cm(ancho))
        q = vaciar(copy.deepcopy(self.modelo["pie"]))
        poner_ppr(q, "ind", {"firstLine": "0"})
        poner_ppr(q, "spacing", {"after": "120"})
        self._agregar(escribir(q, f"Fig. {self.nfig}: {pie}", sz=18, i=True))
        return self.nfig

    def tabla(self, titulo, encabezado, filas, anchos, centrar=(), negrita=()):
        self.ntab += 1
        t = vaciar(copy.deepcopy(self.modelo["ttab"]))
        self._agregar(escribir(t, f"Tabla {self.ntab}. {titulo}", sz=18))
        tbl = copy.deepcopy(self.modelo["tabla"])
        tw = [int(a / 2.54 * 1440) for a in anchos]
        tblpr = tbl.find(W("tblPr"))
        tblpr.find(W("tblW")).set(W("w"), str(sum(tw)))
        jc = OxmlElement("w:jc"); jc.set(W("val"), "center")
        tblpr.find(W("tblW")).addnext(jc)
        grid = tbl.find(W("tblGrid"))
        for g in list(grid):
            grid.remove(g)
        for w in tw:
            g = OxmlElement("w:gridCol"); g.set(W("w"), str(w)); grid.append(g)
        filas_modelo = tbl.findall(W("tr"))
        tr_enc, tr_dat = filas_modelo[0], filas_modelo[1]
        tc_enc, tc_dat = tr_enc.find(W("tc")), tr_dat.find(W("tc"))
        for tr in filas_modelo:
            tbl.remove(tr)
        for k, fila in enumerate([encabezado] + filas):
            es_enc = k == 0
            tr = copy.deepcopy(tr_enc if es_enc else tr_dat)
            for tc in tr.findall(W("tc")):
                tr.remove(tc)
            for j, (texto, w) in enumerate(zip(fila, tw)):
                tc = copy.deepcopy(tc_enc if es_enc else tc_dat)
                tcpr = tc.find(W("tcPr"))
                tcpr.find(W("tcW")).set(W("w"), str(w))
                mar = tcpr.find(W("tcMar"))
                for lado in ("left", "right"):
                    e = mar.find(W(lado))
                    if e is None:
                        e = OxmlElement("w:" + lado); mar.append(e)
                    e.set(W("w"), "30"); e.set(W("type"), "dxa")
                orden = [mar.find(W(x)) for x in ("top", "left", "bottom", "right")]
                for e in orden:
                    mar.remove(e)
                for e in orden:
                    mar.append(e)
                for extra in tc.findall(W("p"))[1:]:
                    tc.remove(extra)
                p = vaciar(tc.find(W("p")))
                poner_ppr(p, "jc", {"val": "center" if es_enc or j in centrar else "left"})
                escribir(p, str(texto), sz=18, b=es_enc or (k - 1) in negrita)
                tr.append(tc)
            tbl.append(tr)
        self._agregar(tbl)
        esp = OxmlElement("w:p")          # respiro después de la tabla
        ppr = OxmlElement("w:pPr"); s = OxmlElement("w:spacing"); s.set(W("after"), "0"); s.set(W("line"), "120")
        s.set(W("lineRule"), "exact"); ppr.append(s); esp.append(ppr)
        self._agregar(esp)
        return self.ntab

    def figura_ancha(self, ruta, pie, ancho=ANCHO_PAGINA):
        """Figura a todo el ancho, flotante y anclada arriba de la página (como en las revistas a dos columnas):
        una tabla flotante sin bordes con la imagen y su epígrafe; el texto de ambas columnas sigue debajo."""
        self.nfig += 1
        ancho_tw = 11907 - 1418 - 1134          # ancho útil de la página en la plantilla (twips)
        tbl = OxmlElement("w:tbl")
        tblpr = OxmlElement("w:tblPr")
        pos = OxmlElement("w:tblpPr")
        for k, v in dict(leftFromText="0", rightFromText="0", topFromText="0", bottomFromText="240",
                         vertAnchor="margin", horzAnchor="margin", tblpXSpec="center", tblpYSpec="top").items():
            pos.set(W(k), v)
        tblpr.append(pos)
        sup = OxmlElement("w:tblOverlap"); sup.set(W("val"), "never"); tblpr.append(sup)
        tw = OxmlElement("w:tblW"); tw.set(W("w"), str(ancho_tw)); tw.set(W("type"), "dxa"); tblpr.append(tw)
        bordes = OxmlElement("w:tblBorders")
        for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement("w:" + lado); e.set(W("val"), "nil"); bordes.append(e)
        tblpr.append(bordes)
        lay = OxmlElement("w:tblLayout"); lay.set(W("type"), "fixed"); tblpr.append(lay)
        mar = OxmlElement("w:tblCellMar")
        for lado in ("left", "right"):
            e = OxmlElement("w:" + lado); e.set(W("w"), "0"); e.set(W("type"), "dxa"); mar.append(e)
        tblpr.append(mar)
        tbl.append(tblpr)
        grid = OxmlElement("w:tblGrid"); g = OxmlElement("w:gridCol"); g.set(W("w"), str(ancho_tw)); grid.append(g)
        tbl.append(grid)
        tr = OxmlElement("w:tr"); tc = OxmlElement("w:tc")
        tcpr = OxmlElement("w:tcPr"); w = OxmlElement("w:tcW"); w.set(W("w"), str(ancho_tw)); w.set(W("type"), "dxa")
        tcpr.append(w); tc.append(tcpr)
        p = vaciar(copy.deepcopy(self.modelo["img"]))
        poner_ppr(p, "keepNext")
        poner_ppr(p, "spacing", {"before": "0", "after": "40"})
        poner_ppr(p, "jc", {"val": "center"})
        tc.append(p)
        q = vaciar(copy.deepcopy(self.modelo["pie"]))
        poner_ppr(q, "ind", {"firstLine": "0"})
        poner_ppr(q, "spacing", {"after": "0"})
        escribir(q, f"Fig. {self.nfig}: {pie}", sz=18, i=True)
        tc.append(q)
        tr.append(tc); tbl.append(tr)
        self._agregar(tbl)
        Paragraph(p, self.doc._body).add_run().add_picture(str(ruta), width=Cm(ancho))
        return self.nfig

    def corte(self, columnas):
        """Salto de sección continuo: cierra la sección anterior con 1 o 2 columnas (para figuras a todo el ancho)."""
        p = OxmlElement("w:p")
        ppr = OxmlElement("w:pPr")
        s = OxmlElement("w:spacing"); s.set(W("before"), "0"); s.set(W("after"), "0"); s.set(W("line"), "20")
        s.set(W("lineRule"), "exact"); ppr.append(s)
        r = OxmlElement("w:rPr"); z = OxmlElement("w:sz"); z.set(W("val"), "2"); r.append(z); ppr.append(r)
        sect = copy.deepcopy(self.final)
        if columnas == 1:
            cols = sect.find(W("cols"))
            nueva = OxmlElement("w:cols"); nueva.set(W("space"), "720")
            cols.addprevious(nueva); sect.remove(cols)
        ppr.append(sect)
        p.append(ppr)
        return self._agregar(p)

    def referencia(self, k, texto):
        return self._agregar(escribir(vaciar(copy.deepcopy(self.modelo["ref"])), f"[{k}] {texto}", sz=18))

    def guardar(self, ruta):
        cp = self.doc.core_properties
        cp.title, cp.author, cp.last_modified_by = TITULO, "J. I. Forzani, A. Racca y A. Cesano", "J. I. Forzani"
        cp.subject, cp.keywords, cp.comments = "TP4 · Aprendizaje Automático y Grandes Datos (UNRaf)", "GPON", ""
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(ruta)


# ------------------------------------------------------------------ figura 8: capturas de la aplicación
def fig_capturas(nombre, recortes):
    """Recorta dos capturas (sin el menú lateral ni el espacio vacío) y las apila con su letra (a) y (b)."""
    partes = [Image.open(CAPTURAS / r).convert("RGB").crop(caja) for r, caja in recortes]
    sep = 36
    lienzo = Image.new("RGB", (partes[0].width, sum(p.height for p in partes) + sep), "white")
    letra = ImageFont.truetype("arialbd.ttf", 46)
    y = 0
    for etiqueta, parte in zip(("(a)", "(b)"), partes):
        lienzo.paste(parte, (0, y))
        d = ImageDraw.Draw(lienzo)
        d.rounded_rectangle((parte.width - 112, y + 8, parte.width - 10, y + 70), 10, fill="white")
        d.text((parte.width - 99, y + 12), etiqueta, font=letra, fill="black")
        y += parte.height + sep
    ruta = FIGURAS / nombre
    lienzo.save(ruta, dpi=(300, 300))
    return ruta


# ------------------------------------------------------------------ hiperparámetros (Tabla 2)
NOMBRE_PARAM = {"alpha": "α", "max_depth": "prof.", "min_samples_leaf": "mín. hoja", "learning_rate": "tasa", "C": "C",
                "n_neighbors": "vecinos", "weights": "peso", "var_smoothing": "suavizado"}


def valor(v):
    if v is None:
        return "∞"
    if isinstance(v, str):
        return {"uniform": "unif.", "distance": "dist."}.get(v, v)
    if isinstance(v, float) and v < 1e-2 and v != 0:
        exp = int(round(__import__("math").log10(v)))
        return "10" + str(exp).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    return c(v, 2).rstrip("0").rstrip(",") if isinstance(v, float) else str(v)


def espacio(csv, modelo, elegido_txt):
    g = pd.read_csv(csv, encoding="utf-8-sig")
    combos = [ast.literal_eval(h) for h in g.loc[g["modelo"] == modelo, "hiperparametros"]]
    claves = list(combos[0])
    eleg = ast.literal_eval(elegido_txt)
    marca = lambda k, v: f"**{valor(v)}**" if v == eleg[k] else valor(v)
    return ", ".join(f"{NOMBRE_PARAM[k]} ∈ {{{'; '.join(marca(k, v) for v in dict.fromkeys(cmb[k] for cmb in combos))}}}"
                     for k in claves)


def elegido(texto):
    d = ast.literal_eval(texto)
    return ", ".join(f"{NOMBRE_PARAM[k]} = {valor(v)}" for k, v in d.items())


# ------------------------------------------------------------------ el artículo
def armar(m):
    f = {k: v["obtenido"] for k, v in m["fase1_chequeos"]["detalle"].items()}
    O1, O2, O3, O6 = m["obj01"], m["obj02"], m["obj03"], m["obj06"]
    T2, T3 = m["obj09_tp2"], m["obj14_tp3"]
    D2, D3 = T2["datos"], T3["datos"]
    M2, M3 = T2["mejor_modelo"], T3["mejor_modelo"]
    P2, E2, V2 = T2["prueba"], T2["entrenamiento"], T2["cv_media"]
    P3, E3, V3 = T3["prueba"], T3["entrenamiento"], T3["cv_media"]
    meta2, meta3 = T2["criterio_smart"]["metas"], T3["criterio_smart"]["metas"]
    res, pat = T2["residuos"], T2["residuos"]["patrones"]
    olt = T2["prueba_olt"]["resultados"]
    cm_lr = T3["matrices_confusion_prueba"][M3]
    tn, fp, fn, tp = cm_lr[0][0], cm_lr[0][1], cm_lr[1][0], cm_lr[1][1]
    cm_gb = T3["matrices_confusion_prueba"]["Gradient Boosting"]
    pos = tp + fn
    imp3 = T3["importancia_permutacion"]
    otra_max = max(v for k, v in imp3.items() if k != "vec_rxp")
    umb = T3["umbral_decision"]["comparacion_prueba"]["recall 80 % en CV"]
    cl = T3["clustering"]
    pm, px = cl["perfil_mejor"], cl["perfil_extra"]
    g_alto, g_bajo = max(pm.values(), key=lambda g: g["pct_en_riesgo"]), min(pm.values(), key=lambda g: g["pct_en_riesgo"])
    gx_alto = max(px.values(), key=lambda g: g["pct_en_riesgo"])
    gx_resto = [g["pct_en_riesgo"] for g in px.values() if g is not gx_alto]
    adv = O3["advertencia_fuera_vs_desactualizado"]
    brecha2 = {k: v["brecha_entrenamiento_cv"] for k, v in T2["diagnostico"].items()}
    brecha3 = {k: v["brecha_entrenamiento_cv"] for k, v in T3["diagnostico"].items()}
    k22 = T2["comparacion_5_vs_22_modelos"]["los 22 modelos"]
    rf_smart = T3["criterio_smart"]["resultados"]["Random Forest | ROC-AUC en prueba"]["valor"]
    total = sum(v["equipos"] for v in O2["total"].values())
    eg = O1["ranking_top5"][0]
    wifi_hoy, wifi_meta = O2["equipos_wifi_moderno"] / total * 100, (O2["equipos_wifi_moderno"] + eg["cantidad"]) / total * 100
    ca = T2["curva_aprendizaje"]
    ca_r, ca_rf = ca["Ridge (mejor)"], ca["Random Forest"]
    rk = pd.read_csv(RAIZ / "results" / "cli_05_ranking_puertos.csv", encoding="utf-8-sig")
    rk["equipos"] = rk["previsto"].clip(0, 1) * rk["onts"]
    eq10 = rk.nlargest(10, "equipos")["equipos"].sum()     # lo mismo que muestra la pestaña «Qué actualizar»
    tops = ", ".join(s.split("_")[1] for s in T2["variables"]["shares_top5"])
    gm2 = pd.read_csv(RAIZ / "reports" / "TP2" / "gridsearch_mejora.csv", encoding="utf-8-sig").set_index("modelo")
    gm3 = pd.read_csv(RAIZ / "reports" / "TP3" / "gridsearch_mejora.csv", encoding="utf-8-sig").set_index("modelo")

    # chequeos: el texto afirma que se cumplen las metas, así que se verifica
    assert P2[M2]["R2"] >= meta2["R2_prueba"] and P2[M2]["R2_ajustado"] >= meta2["R2_ajustado_prueba"]
    assert P2[M2]["MAE"] < P2["Dummy (promedio)"]["MAE"]
    assert P3[M3]["ROC_AUC"] >= meta3["ROC_AUC_prueba"] and P3[M3]["PR_AUC"] >= meta3["PR_AUC_prueba"]

    a = Articulo()

    class _Nada:   # en la versión de 8 páginas, los bloques marcados con L. no se agregan
        def __getattr__(self, _):
            return lambda *args, **kwargs: None

    L = a if LARGO else _Nada()
    palabras = a.resumen(
        f"Las empresas de fibra óptica registran el inventario de los equipos de sus clientes (ONT), pero rara vez lo "
        f"analizan para planificar el mantenimiento. Este trabajo integra las cuatro etapas de un proyecto de aprendizaje "
        f"automático sobre el inventario de {n(f['Filas'])} ONT de una red GPON de Santa Fe y el listado de su central "
        f"(OLT). El propósito fue apoyar dos decisiones: qué puertos actualizar primero y a qué puerto conectar a un cliente "
        f"nuevo. Tras el análisis exploratorio, se compararon cuatro algoritmos de regresión para estimar el "
        f"porcentaje de equipos con *firmware* fuera de estándar en los {n(D2['pon'])} puertos PON, y cuatro "
        f"clasificadores, dos ensambles y *K-Means* para anticipar si un cliente queda con la señal en riesgo, con "
        f"validación agrupada por puerto. La regresión *Ridge* logró un R² de "
        f"{c(P2[M2]['R2'])} en prueba y la regresión logística, un ROC-AUC de {c(P3[M3]['ROC_AUC'])} y un PR-AUC de "
        f"{c(P3[M3]['PR_AUC'])}, igual que una regla basada en la señal de los vecinos del puerto: el riesgo depende de la "
        f"fibra compartida, no del equipo. Ambos modelos se serializaron y se desplegaron en una aplicación web. "
        f"Cumplen sus metas, pero sirven para ordenar prioridades, no para decidir caso por caso.",
        ["Redes GPON", "Aprendizaje Automático", "Regresión *Ridge*", "Regresión Logística", "Validación Agrupada",
         "Despliegue de Modelos"])

    # ============================================================== 1. Introducción
    a.h1("Introducción")
    a.p("Las redes ópticas pasivas con capacidad de *gigabit* (GPON) llevan la fibra hasta el hogar desde una terminal de "
        "línea óptica (OLT), ubicada en la central y dividida en tarjetas y puertos PON. Cada puerto atiende, por un mismo "
        "tendido, a decenas de terminales de red óptica (ONT): el módem que el cliente tiene en su casa. Para un proveedor "
        "regional, dos tareas consumen buena parte del mantenimiento: actualizar el *firmware* de los equipos, que se hace "
        "de a un puerto entero dentro de una ventana de mantenimiento, y conectar a cada cliente nuevo en un puerto donde "
        "la señal le llegue con margen. La norma G.984.2 fija para los equipos de clase B+ una sensibilidad mínima de "
        "−27 dBm [@g984]: un cliente que recibe menos de −25 dBm queda a solo 2 dB de perder el servicio.")
    L.p("El proyecto usó datos reales de una empresa de fibra óptica de la región. Mantener el *firmware* al día "
        "corrige fallas de seguridad y de compatibilidad, pero cada actualización deja sin servicio a un puerto entero "
        "durante la ventana; y con poco margen de señal, un empalme degradado alcanza para cortar el servicio. Hoy ambas "
        "decisiones se toman con planillas y con la experiencia del personal técnico.")
    a.p("El aprendizaje automático se aplica a las redes ópticas desde hace más de una década" + (
        ": Zibar *et al.* [@zibar] y Khan *et al.* [@khan] muestran cómo pasó del procesamiento de la señal en el receptor a "
        "la gestión de la red. Las r" if LARGO else ". Las r") + "evisiones de Musumeci *et al.* [@musumeci] y de Mata *et al.* [@mata] agrupan sus usos en estimación de la calidad de transmisión, gestión "
        "de fallas, predicción de tráfico y monitoreo del desempeño, y Rafique y Velasco [@rafique] proponen arquitecturas para "
        "automatizar la red con esos modelos. En casi todos los casos se entrena con series de monitoreo (potencia óptica, "
        "tasa de errores, alarmas) de redes troncales o metropolitanas y con grandes volúmenes de datos. Con tablas "
        "pequeñas conviene comparar modelos lineales regularizados como *Ridge* [@hoerl,@hastie] con ensambles de árboles "
        "como *Random Forest* [@breiman] o *Gradient Boosting* [@friedman], más flexibles pero propensos al sobreajuste. "
        + ("Con clases desbalanceadas conviene ajustar los pesos de clase o el umbral [@he], y la curva " if LARGO
           else "Con clases desbalanceadas, la curva ") +
        "precisión-*recall* es más informativa que la ROC [@saito]. Dos errores frecuentes invalidan los resultados: la "
        "fuga de información, cuando una entrada contiene la respuesta [@kaufman], y la validación aleatoria sobre datos "
        "agrupados, que reparte entre entrenamiento y prueba observaciones casi idénticas [@roberts]. Por último, llevar un "
        "modelo a producción agrega costos que no se ven en un *notebook*: dependencias, datos que cambian y "
        "monitoreo " + ("[@sculley,@breck]." if LARGO else "[@sculley]."))
    a.p("Esos trabajos suponen datos de monitoreo continuos. Un proveedor regional, en cambio, suele tener solo el "
        "inventario de equipos (una foto estática, sin fechas ni fallas) y, a lo sumo, un listado puntual de la OLT. No "
        "encontramos trabajos que evalúen qué se puede aprender honestamente con esa información ni que lleven los modelos "
        "a una herramienta que el personal técnico pueda usar sin programar.")
    a.p(f"El objetivo general fue convertir el inventario de una red GPON real en herramientas de decisión para el "
        f"mantenimiento, en cuatro etapas: (i) limpiar y explorar el inventario (TP1); (ii) estimar el porcentaje de "
        f"equipos con *firmware* fuera de estándar de cada puerto PON, con la meta de alcanzar en prueba un R² de al menos "
        f"{c(meta2['R2_prueba'])}, un R² ajustado de al menos {c(meta2['R2_ajustado_prueba'])} y un error absoluto medio "
        f"menor que el de predecir el promedio (TP2); (iii) anticipar si un cliente queda con la señal en riesgo antes de "
        f"medirla, con un ROC-AUC de al menos {c(meta3['ROC_AUC_prueba'])} y un PR-AUC de al menos "
        f"{c(meta3['PR_AUC_prueba'])}, el doble de la tasa base (TP3), y (iv) desplegar los modelos elegidos en una "
        f"aplicación web (TP4).")
    a.p("La sección 2 describe los datos y los métodos; la 3, los resultados de los modelos y de la aplicación; la 4 los "
        "discute junto con sus limitaciones, y la 5 resume las conclusiones y el trabajo futuro.")

    # ============================================================== 2. Metodología
    a.h1("Metodología")
    a.h2("Conjunto de datos")
    a.p(f"Se trabajó con dos archivos entregados por una empresa de telecomunicaciones de la región. El inventario tiene "
        f"{n(f['Filas'])} filas, una por ONT, y 13 columnas: ubicación (localidad, tarjeta, puerto e identificador), "
        f"marca, modelo, versión de *firmware* y cinco atributos de *hardware* (puertos LAN, "
        f"tecnología Wi-Fi, módulo óptico, puertos telefónicos y salida de TV). Cubre {n(f['Localidades'])} localidades, "
        f"{n(f['Tarjetas (Localidad+Slot)'])} tarjetas y {n(f['Puertos PON (Localidad+Slot+PON)'])} puertos PON, y es una "
        f"foto estática: no trae fechas, estados, potencias ni fallas. El segundo archivo es el listado de la OLT del "
        f"29/10/2026, con {n(f['OLT: filas'])} equipos, su estado, las potencias transmitida y recibida y la distancia de "
        f"fibra hasta la central; {n(f['OLT: que cruzan con el inventario'])} de ellos cruzan con el inventario por "
        f"localidad, *slot*, PON e identificador. La Fig. 1 resume el flujo del proyecto y la Tabla 1, cómo se usó cada "
        f"fuente en los dos problemas supervisados.")
    a.figura(FIGURAS / "fig1_flujo.png", ancho=6.0, pie="Flujo del proyecto: fuentes de datos, etapas (TP1 a TP4) y modelos que llegan a "
             "la aplicación.")
    a.tabla("Problemas supervisados del proyecto.", ["", "TP2 (regresión)", "TP3 (clasificación)"], [
        ["Unidad", "Puerto PON", "Cliente online"],
        ["Filas", n(D2["pon"]), n(D3["equipos"])],
        ["Objetivo", "% de equipos con *firmware* fuera de estándar", f"Señal < −25 dBm ({c(D3['pct_en_riesgo'] * 100, 1)} %)"],
        ["Entradas", "Ubicación, tamaño del puerto, % con TV, % modernos y mezcla de modelos",
         "Ubicación, equipo, *firmware*, distancia y señal de los vecinos"],
        ["Excluidas", "Todo lo derivado de la versión de *firmware*", "Potencia, estado y nivel de señal del propio equipo"],
        ["Partición", "Aleatoria 80/20 y *KFold* de 5", "Agrupada por PON (5 particiones)"],
    ], [1.65, 2.65, 2.65])

    a.h2("Preprocesamiento y análisis exploratorio (TP1)")
    a.p(f"En el TP1 se normalizaron los nombres de las localidades, se consolidaron los alias de modelo (por ejemplo, "
        f"«546M» y «HG8546M»), lo que redujo los {n(f['Modelos (nombres originales)'])} nombres a "
        f"{n(f['Modelos canónicos'])} equipos físicos, y se armaron claves únicas de tarjeta y de puerto. Se derivaron "
        f"variables por equipo: cantidad de equipos del puerto, posición relativa del identificador dentro del puerto, "
        f"generación del *firmware* (el número que sigue a la «V» de la versión), equipo moderno (cuatro puertos *gigabit* "
        f"o Wi-Fi 5/6) y *firmware* fuera de estándar, definido como una "
        f"versión distinta de la más frecuente (la moda) de su modelo, una definición de negocio que la empresa puede "
        f"reemplazar. Luego se agregaron por puerto (proporción de equipos modernos, con TV y de cada modelo, y cantidad "
        f"de modelos y de versiones). {m['fase1_chequeos']['total']} chequeos automáticos (cantidades, duplicados y "
        f"consistencia con la tabla de equivalencias de *hardware*) verifican que el procesamiento reproduce siempre las "
        f"mismas cifras.")
    a.p("El análisis exploratorio dejó una advertencia que condicionó todo lo que siguió: los cinco atributos de "
        "*hardware* son una función determinística del modelo, de modo que un clasificador que los use para predecir el "
        "modelo, o al revés, «acierta» sin aprender nada. Es la fuga de información que describen Kaufman *et al.* [@kaufman]. "
        "Por eso cada problema supervisado declara qué variables quedan prohibidas como entrada (Tabla 1).")

    a.h2("Regresión: firmware por puerto (TP2)")
    a.p(f"El objetivo es el porcentaje de equipos con *firmware* fuera de estándar de cada puerto PON, que indica cuántos "
        f"equipos se actualizarían si se interviene ese puerto. Se excluyeron como entradas la proporción de equipos con "
        f"*firmware* de generación 3 y la cantidad de versiones, porque se calculan a partir de la misma versión que define "
        f"la respuesta. De los {n(f['Modelos canónicos'])} modelos solo entran las proporciones de los cinco más usados: con "
        f"todos, el R² ajustado de prueba cae a {c(k22['R2_ajustado_prueba'])} porque quedan {k22['predictores']} "
        f"predictores. Los puertos se dividieron en entrenamiento ({D2['entrenamiento']}) y prueba ({D2['prueba']}) con "
        f"semilla 42, y los hiperparámetros se eligieron con *GridSearchCV* y *KFold* de cinco particiones sobre el "
        f"entrenamiento (Tabla 2). La codificación *one-hot* de localidad y *slot* y el escalado van dentro de un "
        f"*pipeline* de scikit-learn [@pedregosa], de modo que nada se ajusta con datos de prueba.")
    L.p(f"Cada entrada tiene un motivo. La localidad y la tarjeta capturan diferencias de gestión entre zonas; la cantidad "
        f"de equipos indica el tamaño del puerto; los porcentajes de equipos con salida de TV y de equipos modernos "
        f"describen su mezcla tecnológica, y la cantidad de modelos distintos mide cuán heterogéneo es. Las proporciones de "
        f"los cinco modelos más usados ({tops}) aportan la composición sin multiplicar los predictores. Como el estándar se "
        f"define por modelo, la mezcla de modelos es la vía legítima por la que el modelo puede aprender sin mirar la "
        f"versión de cada equipo.")
    a.p("Se compararon la regresión lineal como línea base, *Ridge* [@hoerl], *Random Forest* [@breiman] y *Gradient Boosting* [@friedman] "
        "contra un *DummyRegressor* que predice el promedio. Las métricas fueron MSE, RMSE, MAE, R² y R² ajustado, en "
        "entrenamiento, validación cruzada y prueba. El R² ajustado penaliza la cantidad de predictores *p* para "
        "*n* observaciones:")
    a.ecuacion("R²_{aj} = 1 − (1 − R²)(*n* − 1)/(*n* − *p* − 1)    (1)")
    a.p(f"Con *p* = {T2['variables']['predictores_efectivos']} predictores efectivos y *n* = {D2['prueba']} puertos de "
        f"prueba, la penalización es fuerte. No se usó el error porcentual (MAPE) porque {D2['pon_con_0_pct']} puertos "
        f"tienen 0 % de equipos fuera de estándar y el cociente se indefine.")
    filas_h = []
    for csv, modelos, tpx in ((RAIZ / "reports" / "TP2" / "gridsearch_espacio.csv", ["Ridge", "Random Forest", "Gradient Boosting"], T2),
                             (RAIZ / "reports" / "TP3" / "gridsearch_espacio.csv", ["Regresión Logística", "Árbol de Decisión", "KNN",
                                                                                     "Naive Bayes", "Random Forest", "Gradient Boosting"], T3)):
        etiqueta = "TP2" if tpx is T2 else "TP3"
        for mo in modelos:
            nombre = {"Regresión Logística": "Reg. logística", "Árbol de Decisión": "Árbol"}.get(mo, mo)
            if mo in ("Ridge", "Random Forest", "Gradient Boosting"):
                nombre = f"*{nombre}*"
            filas_h.append([f"{nombre} ({etiqueta})", espacio(csv, mo, tpx["hiperparametros_elegidos"][mo])])
    a.tabla("Hiperparámetros explorados con *GridSearchCV*; en negrita, el valor elegido (∞: sin límite de profundidad).",
            ["Modelo", "Espacio explorado"], filas_h, [2.0, 4.95])

    a.h2("Clasificación y agrupamiento: señal en riesgo (TP3)")
    a.p(f"El TP3 se planteó para evitar la fuga del TP1: ¿se puede anticipar que un cliente queda con la señal al límite "
        f"antes de medirla? Se usaron los {n(D3['equipos'])} equipos online que cruzan con el inventario y tienen lectura "
        f"válida; la clase positiva es una potencia recibida menor que −25 dBm ({n(D3['en_riesgo'])} casos, "
        f"{c(D3['pct_en_riesgo'] * 100, 1)} %), 2 dB por encima de la sensibilidad de la clase B+ [@g984]. La potencia, el "
        f"estado y el nivel de señal del propio equipo quedaron prohibidos como entradas. Sí entra la señal media de los "
        f"vecinos del mismo puerto sin contar al equipo (*vec_rxp*), porque ya está medida cuando se instala un cliente "
        f"nuevo." + (" Para el cliente *i* de un puerto *P* con *n*_{P} equipos online:" if LARGO else ""))
    L.ecuacion("*vec_rxp*_{i} = (Σ_{j∈P} RXP_{j} − RXP_{i}) / (*n*_{P} − 1)    (2)")
    L.p(f"Los {D3['vec_rxp_nulos']} clientes que son los únicos online de su puerto no tienen vecinos: su valor se imputa "
        f"con la mediana dentro del *pipeline*, que además codifica las variables categóricas con *one-hot* y escala las "
        f"numéricas.")
    a.p(f"Como los equipos de un puerto comparten la fibra, la partición se hizo con *StratifiedGroupKFold* de cinco "
        f"particiones agrupando por puerto [@roberts]: una de ellas ({n(D3['prueba'])} clientes de {D3['pon_prueba']} puertos) "
        f"quedó como prueba y la validación cruzada se hizo con la misma estrategia sobre el resto. Se compararon la "
        f"regresión logística (línea base), un árbol de decisión, KNN y *Naive Bayes* gaussiano contra un *DummyClassifier* "
        f"que respeta la proporción de clases y contra una regla sin aprendizaje que ordena a los clientes por la señal de "
        f"sus vecinos. Para el desbalance se usaron pesos de clase balanceados donde existen y, en KNN y *Naive Bayes*, "
        f"un umbral elegido en validación cruzada. Como extensión se entrenaron *Random Forest* y *Gradient Boosting*, y "
        f"*K-Means* con *k* de 2 a 8, elegido por silueta [@rousseeuw] y Davies-Bouldin y comparado con la clase real mediante el "
        f"índice de Rand ajustado (ARI). Se calcularon accuracy, precisión, *recall*, F1, Kappa, ROC-AUC y PR-AUC; la "
        f"búsqueda de hiperparámetros maximizó el PR-AUC.")

    a.h2("Estrategia de despliegue (TP4)")
    a.p("Se desplegó un modelo por problema, elegido con dos criterios fijados antes de mirar la prueba: el mejor "
        "desempeño en validación cruzada y una brecha chica entre entrenamiento y validación, porque un modelo que memoriza "
        "es frágil frente a datos nuevos. En el TP3 la elección se hizo entre los cuatro clasificadores individuales que "
        "pide la consigna; los ensambles quedaron como control. Cada modelo se reentrenó con el mismo conjunto de "
        "entrenamiento del informe y se serializó con *joblib* junto con su preprocesamiento: el archivo guarda el "
        "*pipeline* completo, las columnas de entrada en orden y la versión de scikit-learn. Un control automático "
        "verifica que el modelo guardado reproduce exactamente las métricas de prueba antes de publicarlo.")
    a.p(f"La aplicación se construyó con Streamlit [@streamlit] y Plotly. Un menú lateral agrupa un resumen del TP1, la "
        f"metodología y un apartado por modelo, organizado en pestañas que responden una pregunta cada una{' (Tabla 3)' if LARGO else ''}. El "
        f"margen de error que acompaña cada estimación del TP2 es el MAE de prueba ({c(P2[M2]['MAE'] * 100, 1)} puntos), y "
        f"el riesgo del TP3 se expresa de 0 a 100 como el percentil del puntaje del modelo entre los clientes actuales, con "
        f"un semáforo: menos de 50, conectar; de 50 a 80, revisar la fibra antes; 80 o más, elegir otro puerto. La carpeta "
        f"de la aplicación es autocontenida: incluye el código, los dos modelos, los datos procesados que muestra (sin "
        f"números de serie ni direcciones IP) y un archivo requirements.txt con versiones fijas, de modo que corre en "
        f"cualquier computadora con Python sin acceder a los datos originales."
        + (f" La aplicación está publicada en {URL_APP}, y su código, junto con el material de los cuatro trabajos, en "
           f"{URL_REPO}. La versión pública reemplaza los nombres de las localidades por letras y solo trae datos agregados; "
           f"las capturas de este artículo corresponden a la versión con los datos completos." if URL_APP and URL_REPO else "")
        + ("" if LARGO else " Todo el procesamiento corre desde cero con un único comando, con semilla 42, y cada cifra de "
           "este artículo se lee del archivo de métricas que genera el código."))
    L.tabla("Elementos que pide la consigna para la aplicación y cómo se cumplen.", ["Requisito", "Implementación"], [
        ["Título y descripción", "Encabezado de cada apartado con el problema y el modelo usado"],
        ["Entrada de datos", "Selectores y deslizadores que parten de los valores de un puerto o cliente real"],
        ["Salida", "% estimado con su margen de error (TP2); riesgo de 0 a 100 y un veredicto en palabras (TP3)"],
        ["Validación", "Rangos acotados y avisos cuando un valor o una combinación queda fuera de lo que vio el modelo"],
        ["Contexto", "Posición del caso frente a los puertos o clientes reales, importancia de variables y desempeño"],
        ["Extensiones", "Dos modelos, gráficos interactivos, explicabilidad y descarga de resultados en CSV"],
    ], [1.9, 5.05])
    L.h2("Reproducibilidad")
    L.p("Todo el procesamiento usa la semilla 42 y corre desde cero con un único comando (python run_all.py), que encadena "
        "la preparación de los datos, los dos trabajos, la serialización de los modelos, la carpeta de la aplicación y este "
        "artículo; los *notebooks* del TP2 y del TP3 se ejecutan de principio a fin como parte de la verificación. Cada "
        "cifra de los informes, de la aplicación y de este artículo se lee de un único archivo de métricas generado por el "
        "código: ninguna se copió a mano.")

    # ============================================================== 3. Resultados
    a.h1("Resultados")
    a.h2("Análisis exploratorio")
    a.p(f"La Fig. 2 resume los hallazgos del TP1 que motivaron los dos problemas supervisados. Toda la red es de una sola "
        f"marca (Huawei) y tres modelos concentran el {c(O1['pct_top3'], 1)} % de los equipos (Fig. 2a). El "
        f"{c(O2['total']['Wi-Fi 4']['pct'], 1)} % de las ONT solo tiene Wi-Fi 4 y el "
        f"{c(O1['pct_equipos_con_algun_puerto_fe'], 1)} % tiene al menos un puerto LAN de 100 Mb/s: el límite del servicio "
        f"está en el módem del cliente, no en la fibra. El {c(O3['pct_fuera_estandar'], 1)} % de los equipos tiene el "
        f"*firmware* fuera de estándar, con diferencias grandes entre localidades: en Larrechea llega al "
        f"{c(O3['pct_fuera_por_localidad']['Larrechea'], 1)} % (Fig. 2b). Además, {O6['tarjetas_bajo_p25']} de las "
        f"{O6['tarjetas']} tarjetas atienden menos de {c(O6['p25_onts_por_tarjeta'], 1)} equipos (el 25 % menos "
        f"ocupado), una señal de capacidad ociosa. Con ese diagnóstico, el TP1 propuso una meta medible: pasar de "
        f"{c(wifi_hoy, 1)} % a {c(wifi_meta, 1)} % de equipos con Wi-Fi 5 o superior antes del 31/12/2027, reemplazando "
        f"los {n(eg['cantidad'])} {eg['Modelo_canonico']}, el modelo más común.")
    a.figura(FIGURAS / "fig2_eda.png", "Análisis exploratorio del inventario (TP1). (a) Equipos por modelo: ninguno de los "
             "seis más usados tiene Wi-Fi 5 o 6. (b) Porcentaje de equipos con *firmware* fuera de estándar por localidad.")

    a.h2("Regresión")
    a.p(f"La Tabla {a.ntab + 1} y la Fig. {a.nfig + 1} comparan los modelos. Los cuatro superan con amplitud al *Dummy*, cuyo R² es nulo. "
        f"*Random Forest* y *Gradient Boosting* obtienen el R² de prueba más alto ({c(P2['Random Forest']['R2'])} y "
        f"{c(P2['Gradient Boosting']['R2'])}), pero su R² de entrenamiento ({c(E2['Random Forest']['R2'])} y "
        f"{c(E2['Gradient Boosting']['R2'])}) supera en {c(brecha2['Random Forest'])} y "
        f"{c(brecha2['Gradient Boosting'])} al de validación cruzada: memorizan. La regresión lineal y *Ridge* tienen "
        f"brechas de {c(brecha2['Regresión Lineal'])} y {c(brecha2['Ridge'])} y el mejor desempeño en validación cruzada; "
        f"se eligió *Ridge* (α = 1), con R² {c(P2[M2]['R2'])}, R² ajustado {c(P2[M2]['R2_ajustado'])} y MAE "
        f"{c(P2[M2]['MAE'], 3)} en prueba, frente a un MAE de {c(P2['Dummy (promedio)']['MAE'], 3)} del *Dummy*. Cumple "
        f"las tres metas. En términos prácticos, la estimación de cada puerto se equivoca en promedio en "
        f"{c(P2[M2]['MAE'] * 100, 1)} puntos porcentuales.")
    nombres2 = {"Dummy (promedio)": "*Dummy*", "Regresión Lineal": "Lineal", "Ridge": "*Ridge*",
                "Random Forest": "*Random Forest*", "Gradient Boosting": "*Gradient Boosting*"}
    a.tabla("Métricas de regresión (TP2): R² en entrenamiento (Ent.), validación cruzada (VC) y prueba; R² ajustado "
            "y MAE en prueba. En negrita, el modelo elegido.",
            ["Modelo", "Ent.", "VC", "Prueba", "R² aj.", "MAE"],
            [[nombres2[k], c(E2[k]["R2"]), c(V2[k]["R2"]), c(P2[k]["R2"]), c(P2[k]["R2_ajustado"]), c(P2[k]["MAE"], 3)]
             for k in nombres2], [1.75, 0.95, 0.95, 1.2, 1.05, 1.05], centrar=(1, 2, 3, 4, 5),
            negrita=(list(nombres2).index(M2),))
    a.figura(FIGURAS / "fig3_tp2_comparacion.png", "R² de cada modelo de regresión en entrenamiento, validación cruzada y "
             "prueba (TP2). La línea roja marca la meta en prueba.")
    a.p(f"La Fig. {a.nfig + 1} muestra el análisis de residuos de *Ridge*. Los puntos siguen la diagonal, pero el modelo sobreestima "
        f"los puertos con 0 % y subestima los cercanos a 100 %, algo esperable en una variable acotada. Los residuos de "
        f"prueba no son normales (Shapiro-Wilk, p = {c(res['prueba']['shapiro_p'], 3)}) ni muestran heterocedasticidad "
        f"significativa (Breusch-Pagan, p = {c(res['prueba']['breusch_pagan_p'])}). El error es mayor en los "
        f"{pat['n_pon_5_onts_o_menos']} puertos de entrenamiento con cinco equipos o menos (MAE de "
        f"{c(pat['MAE_pon_5_onts_o_menos'] * 100, 1)} puntos contra {c(pat['MAE_pon_mas_de_5_onts'] * 100, 1)}).")
    a.figura(FIGURAS / "fig4_tp2_residuos.png", "Residuos de *Ridge* (TP2). Gris: entrenamiento fuera de muestra (validación "
             "cruzada); azul: prueba. (a) Predicho contra real, con la diagonal de predicción perfecta. (b) Residuos contra "
             "predichos.")
    L.p(f"La curva de aprendizaje muestra que el error de validación de *Ridge* baja de "
        f"{c(ca_r['RMSE_validacion_inicio'] * 100, 1)} a {c(ca_r['RMSE_validacion_final'] * 100, 1)} puntos al pasar de "
        f"{ca_r['n_inicio']} a {ca_r['n_final']} puertos de entrenamiento, con una brecha final de "
        f"{c(ca_r['brecha_final_pp'], 1)} puntos frente a {c(ca_rf['brecha_final_pp'], 1)} de *Random Forest*. La curva "
        f"todavía desciende: con más puertos, por ejemplo de otras redes de la empresa, el modelo mejoraría.")
    a.p(f"Por permutación{(' (Fig. ' + str(a.nfig + 1) + 'a)') if LARGO else ''}, las variables más importantes fueron el porcentaje de equipos con TV, la "
        f"localidad y las proporciones de EG8141A5 y EG8143A5. El porcentaje con TV y la proporción de EG8143A5 tienen una correlación de "
        f"{c(T2['correlacion_pct_catv_share_EG8143A5'])} (el EG8143A5 es el modelo con salida de TV), así que su "
        f"importancia se reparte entre ambas. Sumar variables de la OLT por puerto (porcentaje online, distancia y potencia "
        f"medianas) no mejoró el modelo: el R² de prueba bajó de {c(olt['sin OLT']['R2_prueba'])} a "
        f"{c(olt['con OLT']['R2_prueba'])}. El *firmware* fuera de estándar responde a decisiones administrativas por "
        f"localidad y por modelo, no al estado físico de la red.")
    fig_imp = L.figura(FIGURAS / "fig_importancia.png", "Importancia por permutación en prueba, con su desvío: (a) caída "
                       "del R² de *Ridge* (TP2); (b) caída del PR-AUC de la regresión logística (TP3).")

    a.h2("Clasificación")
    a.p(f"La Tabla {a.ntab + 1} resume el desempeño en prueba. El *Dummy* tiene una accuracy de {c(P3['Dummy (prior)']['accuracy'], 3)} "
        f"porque nunca marca a nadie en riesgo: con este desbalance la accuracy engaña, y por eso la selección se basó en "
        f"ROC-AUC y PR-AUC. La regresión logística (C = 0,01) fue el mejor clasificador individual en validación cruzada "
        f"(ROC-AUC {c(V3[M3]['ROC_AUC'])} y PR-AUC {c(V3[M3]['PR_AUC'])}) y el de menor brecha con el entrenamiento "
        f"({c(brecha3[M3])}). En prueba logró un ROC-AUC de {c(P3[M3]['ROC_AUC'])} y un PR-AUC de {c(P3[M3]['PR_AUC'])}, por "
        f"encima de las metas. Detectó {tp} de los {pos} clientes en riesgo ({c(P3[M3]['recall'] * 100, 0)} % de *recall*) "
        f"a cambio de {fp} falsas alarmas (Fig. {a.nfig + 1}), con una precisión de {c(P3[M3]['precision'])}: de cada cuatro clientes "
        f"marcados, uno está realmente en riesgo.")
    nombres3 = {"Dummy (prior)": "*Dummy*", "Regla de los vecinos": "Regla de vecinos", "Regresión Logística": "Reg. logística",
                "Árbol de Decisión": "Árbol", "KNN": "KNN", "Naive Bayes": "*Naive Bayes*", "Random Forest": "*Random Forest*",
                "Gradient Boosting": "*Gradient Boosting*"}
    a.tabla(f"Métricas de clasificación (TP3): ROC-AUC en entrenamiento (Ent.) y en prueba (ROC); PR-AUC (PR), "
            f"*recall* (Rec.) y precisión (Prec.) en prueba ({n(D3['prueba'])} clientes, {pos} en riesgo). La regla de los "
            f"vecinos no tiene umbral.",
            ["Modelo", "Ent.", "ROC", "PR", "Rec.", "Prec."],
            [[nombres3[k], c(E3[k]["ROC_AUC"]), c(P3[k]["ROC_AUC"]), c(P3[k]["PR_AUC"]),
              c(P3[k]["recall"]) if "recall" in P3[k] else "—", c(P3[k]["precision"]) if "precision" in P3[k] else "—"]
             for k in nombres3], [1.95, 1.0, 1.0, 1.0, 1.0, 1.0], centrar=(1, 2, 3, 4, 5),
            negrita=(list(nombres3).index(M3),))
    a.figura(FIGURAS / "fig5_tp3_matrices.png", "Matrices de confusión en prueba (TP3). Filas: clase real; columnas: clase "
             "predicha. El asterisco marca el modelo elegido.")
    a.p(f"El hallazgo central es que la regla de los vecinos, sin aprendizaje, obtiene el mismo desempeño (ROC-AUC "
        f"{c(P3['Regla de los vecinos']['ROC_AUC'])} y PR-AUC {c(P3['Regla de los vecinos']['PR_AUC'])}; Fig. {a.nfig + 1}), y "
        f"la importancia por permutación lo confirma{(' (Fig. ' + str(fig_imp) + 'b)') if LARGO else ''}: desordenar *vec_rxp* hace caer el PR-AUC en "
        f"{c(imp3['vec_rxp'])}, mientras "
        f"que ninguna otra variable lo reduce en más de {c(max(otra_max, 0.001), 3)}. La señal de un cliente depende de la "
        f"fibra que comparte con su puerto; el modelo del equipo, el *firmware* y la distancia casi no agregan información. "
        f"El árbol y KNN sobreajustan (brechas de {c(brecha3['Árbol de Decisión'])} y {c(brecha3['KNN'])}) y *Naive Bayes* "
        f"queda por debajo. Los ensambles tampoco mejoran: *Random Forest*, "
        f"el mejor de todos en validación cruzada, pasa de {c(E3['Random Forest']['ROC_AUC'])} en entrenamiento a "
        f"{c(rf_smart, 3)} en prueba, debajo de la meta, y *Gradient Boosting*, aunque alcanza el mayor PR-AUC "
        f"({c(P3['Gradient Boosting']['PR_AUC'])}), detecta solo {cm_gb[1][1]} de los {pos} casos con su umbral.")
    a.figura(FIGURAS / "fig6_tp3_roc_pr.png", "Curvas ROC (a) y precisión-*recall* (b) en prueba (TP3). La regla de los "
             "vecinos (negro, discontinua) rinde igual que la regresión logística (azul).")
    a.p(f"El umbral de decisión define el compromiso entre encontrar clientes en riesgo y no generar falsas alarmas "
        f"{('(Fig. ' + str(a.nfig + 1) + ')') if LARGO else ''}. Si se prioriza no perder clientes en riesgo, el umbral que da un *recall* del 80 % en "
        f"validación cruzada ({c(umb['valor'])}) eleva el *recall* de prueba a {c(umb['recall'])}, pero marca a "
        f"{n(umb['marcados'])} clientes con una precisión de {c(umb['precision'])}. La aplicación deja elegir ese "
        f"compromiso con un deslizador.")
    L.figura(FIGURAS / "fig_umbral.png", "Precisión y *recall* de la regresión logística en prueba según el umbral (TP3). "
             "Las líneas punteadas marcan el umbral por defecto y el que da un *recall* del 80 % en validación cruzada.")
    L.p(f"La búsqueda de hiperparámetros (Tabla 2) mejoró sobre todo a los modelos flexibles: *Gradient Boosting* redujo "
        f"su RMSE de validación un {c(gm2.loc['Gradient Boosting', 'mejora_pct'], 1)} % en el TP2 y *Naive Bayes* sumó "
        f"{c(gm3.loc['Naive Bayes', 'mejora_puntos'], 2)} puntos de PR-AUC en el TP3, casi siempre eligiendo más "
        f"regularización (árboles menos profundos, hojas más grandes, más vecinos). La regresión logística "
        f"({c(gm3.loc['Regresión Logística', 'mejora_puntos'], 3)} puntos) y *Ridge* casi no cambiaron: están limitados por "
        f"la información disponible, no por sus hiperparámetros.")

    a.p(f"En la aplicación, cada modelo se traduce en una pantalla de decisión (Fig. {a.nfig + 1}), que se describe en "
        f"la sección 3.5.")
    nf = a.figura_ancha(fig_capturas("fig_app_decisiones.png", [("app_tp2_actualizar.png", (445, 175, 2975, 1400)),
                                                     ("app_tp3_puerto.png", (445, 175, 2975, 1455))]),
             "Pantallas de decisión de la aplicación. (a) TP2: qué puertos actualizar en la próxima ventana de "
             "mantenimiento. (b) TP3: a qué puerto conectar a un cliente nuevo.")
    a.h2("Agrupamiento")
    nclu = a.figura(FIGURAS / "fig7_tp3_clustering.png", "Agrupamiento con *K-Means* (TP3). (a) Grupos con *k* = 2 y (b) clase real "
             "(rojo: en riesgo) sobre las dos primeras componentes principales. (c) Silueta y ARI según *k*. (d) Porcentaje "
             "en riesgo por grupo con *k* = 4; la línea marca la tasa de la red.")
    a.p(f"*K-Means* encontró una estructura débil (Fig. {nclu}): la mejor silueta fue {c(cl['silueta']['2'])}, con *k* = 2, y el "
        f"acuerdo con la clase real es bajo (ARI {c(cl['ARI']['2'])}). Aun así, los grupos tienen sentido operativo. Con "
        f"*k* = 2, un grupo de {n(g_alto['equipos'])} clientes, con fibras más largas (mediana de "
        f"{c(g_alto['distancia_mediana_m'] / 1000, 1)} km contra {c(g_bajo['distancia_mediana_m'] / 1000, 1)} km) y vecinos "
        f"con peor señal ({c(g_alto['vec_rxp_media'], 1)} dBm contra {c(g_bajo['vec_rxp_media'], 1)} dBm), concentra el "
        f"{c(g_alto['pct_en_riesgo'] * 100, 1)} % de clientes en riesgo, contra {c(g_bajo['pct_en_riesgo'] * 100, 1)} % "
        f"del resto. Con *k* = 4 aparece un grupo de {n(gx_alto['equipos'])} clientes con "
        f"{c(gx_alto['pct_en_riesgo'] * 100, 1)} % en riesgo, contra {c(min(gx_resto) * 100, 1)} a "
        f"{c(max(gx_resto) * 100, 1)} % en los demás: son los tendidos largos, sobre todo de "
        f"{gx_alto['localidad_principal']}.")

    a.h2("Aplicación desplegada")
    a.p(f"La Fig. {nf} muestra las pantallas que responden las dos decisiones. En el apartado del TP2 "
        f"(Fig. {nf}a), el usuario elige la localidad y cuántos puertos entran en la ventana de mantenimiento, y la "
        f"aplicación ordena los puertos por la cantidad de equipos que se actualizarían según el modelo: con diez puertos "
        f"se actualizarían unos {n(eq10)} equipos, el {c(eq10 / O3['equipos_fuera_estandar'] * 100, 0)} % de los "
        f"{n(O3['equipos_fuera_estandar'])} fuera de estándar, y la lista se puede descargar. En el apartado del TP3 "
        f"(Fig. {nf}b), el técnico elige la localidad y el equipo a instalar, y la aplicación ordena los puertos "
        f"según el riesgo que tendría un cliente nuevo, con un veredicto en palabras: «conectar acá», «revisar la fibra "
        f"antes» o «elegir otro puerto». Los modelos serializados se cargan al iniciar y responden en el momento.")

    # ============================================================== 4. Discusión
    a.h1("Discusión")
    a.h2("Interpretación y comparación de los modelos")
    a.p(f"Los dos problemas supervisados llegan a una conclusión parecida por caminos distintos: en ambos, los modelos "
        f"simples y regularizados igualan o superan a los ensambles, y la información que importa está en el puerto, no en "
        f"el equipo individual. En el TP2, el *firmware* fuera de estándar se explica por la mezcla de modelos y la "
        f"localidad, que reflejan decisiones de compra y de gestión; en el TP3, la señal se explica por la fibra "
        f"compartida. Con {n(D2['pon'])} puertos y una foto estática, los ensambles tienen más capacidad que datos y "
        f"terminan memorizando, como anticipa el compromiso entre sesgo y varianza [@hastie]. Las referencias triviales "
        f"fueron decisivas: el *Dummy* evitó celebrar una accuracy de {c(P3['Dummy (prior)']['accuracy'])} que no "
        f"significa nada, y la regla de los vecinos mostró que la regresión logística, aunque cumple las metas, no agrega "
        f"información sobre una regla que un técnico puede aplicar con una planilla. Es coherente con las revisiones "
        f"[@musumeci,@mata]: la calidad de un enlace depende sobre todo de mediciones del propio enlace.")
    L.p("La comparación entre ambos problemas también es metodológica. En la regresión, el R² ajustado mostró que sumar "
        "predictores con pocos puertos empeora el modelo aunque el R² suba; en la clasificación, el PR-AUC y la matriz de "
        "confusión mostraron lo que la accuracy escondía. En los dos casos, la forma de validar evitó estimaciones "
        "optimistas: con una partición aleatoria por cliente en el TP3, la señal de cada cliente de prueba habría entrado "
        "en el entrenamiento a través de la variable de sus vecinos [@roberts].")
    a.h2("Decisiones metodológicas y limitaciones")
    a.p(f"La etapa más desafiante no fue entrenar los modelos sino formular preguntas que los datos pudieran responder "
        f"honestamente. El inventario es una foto estática y no permite predecir fallas: el primer planteo del TP3, "
        f"predecir caídas con el listado de la OLT, no le ganó al azar y se reemplazó por la pregunta de la señal en "
        f"riesgo. También costó detectar y cerrar las fugas: los atributos de *hardware* que dependen del modelo en el "
        f"TP1, la versión de *firmware* en el TP2 y la potencia del propio equipo en el TP3. Si reiniciáramos el proyecto, "
        f"pediríamos desde el principio lecturas periódicas de la OLT y el historial de reclamos, que permitirían un "
        f"problema temporal real; validaríamos con la empresa la definición de *firmware* estándar, porque «fuera de "
        f"estándar» no equivale a «desactualizado» ({n(adv['fuera_estandar_con_generacion_mayor'])} de los "
        f"{n(O3['equipos_fuera_estandar'])} equipos fuera de estándar, casi todos EG8143A5, tienen una generación de "
        f"*firmware* mayor que la moda), y usaríamos la validación agrupada por puerto desde el TP1.")
    a.p(f"¿Es útil la aplicación para un técnico de la empresa? Para ordenar prioridades, sí: la lista de puertos a "
        f"actualizar concentra el trabajo donde hay más equipos fuera de estándar, y el orden de puertos para un alta "
        f"nueva evita conectar clientes donde los vecinos ya están al límite. Para decidir caso por caso, no: con una "
        f"precisión de {c(P3[M3]['precision'])}, tres de cada cuatro clientes marcados no están en riesgo, y el TP2 se "
        f"equivoca en promedio en {c(P2[M2]['MAE'] * 100, 1)} puntos. Las limitaciones prácticas son tres. Primero, los "
        f"datos de entrada: el TP3 necesita la señal actual de los vecinos, pero la aplicación usa la foto del "
        f"29/10/2026; se mitiga conectándola a lecturas periódicas de la OLT. Segundo, el alcance: ambos modelos "
        f"aprendieron de una sola red y de un solo momento, y no deberían usarse en otra sin reentrenar; la aplicación ya "
        f"avisa cuando un caso queda fuera del rango conocido. Tercero, la confiabilidad: el resultado se muestra con su "
        f"margen de error y un veredicto en tres niveles, no como una certeza, y la decisión final es de un técnico.")
    nf = L.figura_ancha(fig_capturas("fig_app_casos.png", [("app_tp2_caso_nuevo.png", (445, 175, 2975, 1100)),
                                                ("app_tp3_caso_nuevo.png", (445, 175, 2975, 1390))]),
             "Pestañas «Probar un caso nuevo», con validación de entradas. (a) TP2: estimación para un puerto definido por "
             "el usuario. (b) TP3: riesgo de un cliente nuevo según la señal de sus vecinos.")
    L.p(f"La validación de entradas es la principal defensa ante esos límites. Las pestañas «Probar un caso nuevo» "
        f"(Fig. {nf}) permiten explorar casos que no existen, pero si un valor o una combinación queda fuera de lo que "
        f"vio el modelo (por ejemplo, modelos que suman más de 100 % o una señal que ningún puerto tiene), la aplicación "
        f"lo avisa en lugar de devolver un número sin sentido.")
    a.h2("Hacia un entorno profesional")
    a.p("Llevar la solución a producción exigiría pasos que hoy no están [@sculley]: un proceso automático que lea la OLT "
        "y el inventario, valide los datos y recalcule las variables; monitoreo de la deriva de las entradas y del "
        "desempeño, comparando las predicciones con las mediciones que llegan después de cada alta [@gama]; reentrenamiento "
        "periódico con control de versiones de datos y modelos; pruebas automáticas que, como ya hace el *pipeline*, "
        "bloqueen un modelo que no reproduce sus métricas, y una aplicación con autenticación alojada en la infraestructura "
        "de la empresa, porque los datos de la red son sensibles aunque se hayan quitado los números de serie y las IP. La "
        "escala no es un problema: la red tiene unos pocos miles de equipos y cada predicción toma milisegundos.")
    a.p("Los riesgos éticos son más sutiles. El riesgo de señal se concentra en los tendidos largos de algunas "
        "localidades; si la herramienta se usara para rechazar altas o para postergar inversiones en esas zonas, "
        "reforzaría una desigualdad de servicio entre clientes urbanos y rurales. Los puertos con pocos equipos y las "
        "localidades pequeñas tienen estimaciones menos confiables, y un error ahí afecta a clientes concretos. Antes de un "
        "despliegue a gran escala convendría documentar el modelo con una ficha que declare su alcance y sus límites [@mitchell], "
        "revisar el desempeño por localidad y usar la herramienta para priorizar mejoras de la fibra, no para excluir "
        "clientes.")

    # ============================================================== 5. Conclusiones
    a.h1("Conclusiones")
    a.p(f"Este trabajo recorrió el ciclo completo de un proyecto de aprendizaje automático sobre el inventario de una red "
        f"GPON real. El análisis exploratorio mostró que el límite del servicio está en los equipos de los clientes "
        f"({c(O2['total']['Wi-Fi 4']['pct'], 1)} % con Wi-Fi 4) y que el *firmware* fuera de estándar "
        f"({c(O3['pct_fuera_estandar'], 1)} %) se concentra en algunas localidades. Para estimarlo por puerto, *Ridge* "
        f"alcanzó un R² de {c(P2[M2]['R2'])} y un error medio de {c(P2[M2]['MAE'] * 100, 1)} puntos en prueba, sin "
        f"sobreajuste; para anticipar clientes con la señal en riesgo, la regresión logística logró un ROC-AUC de "
        f"{c(P3[M3]['ROC_AUC'])} y un PR-AUC de {c(P3[M3]['PR_AUC'])}. Las metas se cumplieron, pero el hallazgo más útil "
        f"es otro: una regla basada en la señal de los vecinos del puerto rinde lo mismo, lo que indica que el problema "
        f"está en la fibra compartida y no en el módem. Además, el proyecto es reproducible de punta a punta: un solo "
        f"comando regenera datos, modelos, aplicación y artículo, y cada cifra proviene del mismo archivo de métricas.")
    a.p("En lo práctico, la aplicación desplegada convierte esos modelos en dos decisiones concretas, qué puertos "
        "actualizar primero y a qué puerto conectar a un cliente nuevo, con lenguaje simple, márgenes de error y avisos "
        "ante casos fuera de lo conocido. Sirve para ordenar prioridades, no para reemplazar la medición. Como trabajo "
        "futuro proponemos incorporar lecturas periódicas de la OLT y el historial de reclamos para estudiar la evolución "
        "de la señal y anticipar fallas, validar con la empresa la definición de *firmware* estándar, medir el desempeño "
        "de la herramienta en las altas reales y evaluar su equidad entre localidades.")

    # ============================================================== Referencias
    a._agregar(escribir(vaciar(copy.deepcopy(a.modelo["h_ref"])), "Referencias"))   # mismo formato que la plantilla
    sin_citar = set(REFERENCIAS) - set(ORDEN_CITAS)
    assert not (LARGO and sin_citar), f"referencias sin citar: {sin_citar}"
    for clave, k in sorted(ORDEN_CITAS.items(), key=lambda x: x[1]):
        a.referencia(k, REFERENCIAS[clave])
    return a, palabras


REFERENCIAS = {
    "zibar": "D. Zibar, M. Piels, R. Jones y C. G. Schäffer, \"Machine learning techniques in optical communication\", "
    "*J. Lightw. Technol.*, vol. 34, no. 6, pp. 1442–1452, mar. 2016.",
    "khan": "F. N. Khan, Q. Fan, C. Lu y A. P. T. Lau, \"An optical communication's perspective on machine learning and its "
    "applications\", *J. Lightw. Technol.*, vol. 37, no. 2, pp. 493–516, ene. 2019.",
    "he": "H. He y E. A. Garcia, \"Learning from imbalanced data\", *IEEE Trans. Knowl. Data Eng.*, vol. 21, no. 9, "
    "pp. 1263–1284, sep. 2009.",
    "breck": "E. Breck, S. Cai, E. Nielsen, M. Salib y D. Sculley, \"The ML test score: A rubric for ML production readiness and "
    "technical debt reduction\", en *Proc. IEEE Int. Conf. Big Data*, 2017, pp. 1123–1132.",
    "g984": "ITU-T, *Gigabit-capable passive optical networks (G-PON): Physical media dependent (PMD) layer specification*, "
    "Rec. G.984.2, Amd. 1. Ginebra, Suiza: Unión Internacional de Telecomunicaciones, 2006.",
    "musumeci": "F. Musumeci *et al.*, \"An overview on application of machine learning techniques in optical networks\", *IEEE "
    "Commun. Surveys Tuts.*, vol. 21, no. 2, pp. 1383–1408, 2019.",
    "mata": "J. Mata *et al.*, \"Artificial intelligence (AI) methods in optical networks: A comprehensive survey\", *Opt. Switch. "
    "Netw.*, vol. 28, pp. 43–57, abr. 2018.",
    "rafique": "D. Rafique y L. Velasco, \"Machine learning for network automation: Overview, architecture, and applications\", "
    "*J. Opt. Commun. Netw.*, vol. 10, no. 10, pp. D126–D143, oct. 2018.",
    "hoerl": "A. E. Hoerl y R. W. Kennard, \"Ridge regression: Biased estimation for nonorthogonal problems\", *Technometrics*, "
    "vol. 12, no. 1, pp. 55–67, feb. 1970.",
    "hastie": "T. Hastie, R. Tibshirani y J. Friedman, *The Elements of Statistical Learning*, 2.ª ed. Nueva York, EE. UU.: "
    "Springer, 2009.",
    "breiman": "L. Breiman, \"Random forests\", *Mach. Learn.*, vol. 45, no. 1, pp. 5–32, oct. 2001.",
    "friedman": "J. H. Friedman, \"Greedy function approximation: A gradient boosting machine\", *Ann. Statist.*, vol. 29, no. 5, "
    "pp. 1189–1232, oct. 2001.",
    "saito": "T. Saito y M. Rehmsmeier, \"The precision-recall plot is more informative than the ROC plot when evaluating binary "
    "classifiers on imbalanced datasets\", *PLoS ONE*, vol. 10, no. 3, art. e0118432, mar. 2015.",
    "kaufman": "S. Kaufman, S. Rosset, C. Perlich y O. Stitelman, \"Leakage in data mining: Formulation, detection, and avoidance\", "
    "*ACM Trans. Knowl. Discov. Data*, vol. 6, no. 4, art. 15, dic. 2012.",
    "roberts": "D. R. Roberts *et al.*, \"Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic "
    "structure\", *Ecography*, vol. 40, no. 8, pp. 913–929, ago. 2017.",
    "sculley": "D. Sculley *et al.*, \"Hidden technical debt in machine learning systems\", en *Proc. Adv. Neural Inf. Process. Syst.*, "
    "vol. 28, 2015, pp. 2503–2511.",
    "pedregosa": "F. Pedregosa *et al.*, \"Scikit-learn: Machine learning in Python\", *J. Mach. Learn. Res.*, vol. 12, pp. 2825–2830, "
    "2011.",
    "rousseeuw": "P. J. Rousseeuw, \"Silhouettes: A graphical aid to the interpretation and validation of cluster analysis\", *J. Comput. "
    "Appl. Math.*, vol. 20, pp. 53–65, nov. 1987.",
    "streamlit": "Streamlit Inc. (2026). *Streamlit documentation* [En línea]. Disponible: https://docs.streamlit.io",
    "gama": "J. Gama, I. Žliobaitė, A. Bifet, M. Pechenizkiy y A. Bouchachia, \"A survey on concept drift adaptation\", *ACM "
    "Comput. Surv.*, vol. 46, no. 4, art. 44, abr. 2014.",
    "mitchell": "M. Mitchell *et al.*, \"Model cards for model reporting\", en *Proc. Conf. Fairness, Accountability, and Transparency "
    "(FAT ∗)*, 2019, pp. 220–229.",
}


def exportar_pdf(docx, pdf):
    """Exporta con Microsoft Word (COM) para que el PDF salga idéntico a la plantilla."""
    script = (f"$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0; "
              f"try {{ $d = $w.Documents.Open('{docx}', $false, $true); $d.ExportAsFixedFormat('{pdf}', 17); $d.Close(0) }} "
              f"finally {{ $w.Quit() }}")
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True)


def main():
    m = json.loads(METRICS.read_text(encoding="utf-8"))
    articulo, palabras = armar(m)
    destino = DESTINO if LARGO else DESTINO_CORTO
    articulo.guardar(destino)
    print(f"{destino.relative_to(RAIZ)}: {articulo.nfig} figuras, {articulo.ntab} tablas, {len(ORDEN_CITAS)} referencias, "
          f"resumen de {palabras} palabras")
    if "--pdf" in sys.argv:
        pdf = destino.with_suffix(".pdf")
        exportar_pdf(destino, pdf)
        print(pdf.relative_to(RAIZ))


if __name__ == "__main__":
    main()
