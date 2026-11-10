"""Presentaciones orales del TP2 y del TP3 (.pptx), con el estilo de la presentación del TP1:
fondo oscuro, una idea por diapositiva, cifras grandes repartidas, gráficos poco comunes pero fáciles de leer,
notas del orador con guion (IDEA CENTRAL, PASE, SI PREGUNTAN) y respaldo para preguntas al final.
Todo es nativo de PowerPoint (formas, gráficos y tablas editables). Las cifras salen de results/metrics.json."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_MARKER_STYLE, XL_TICK_LABEL_POSITION
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import METRICS, RAIZ  # noqa: E402

SALIDA = RAIZ / "informes y presentaciones"
AUTORES = ["Juan Ignacio Forzani", "Alejo Racca", "Agustín Cesano"]
FECHA = "Noviembre de 2026"
TITULAR, CUERPO = "Century Gothic", "Calibri"   # fuentes que vienen con Office (Poppins/Inter no están instaladas)

PALETAS = {   # sin azul ni rojo, y distintas del naranja y lima del TP1
    "TP2": dict(fondo="15131B", tarjeta="221F2B", linea="34303F", texto="F2EFE8", gris="A7A4B0", gris2="77737F",
                a1="F4B942", a2="B9A3FF", a1_suave="5A4A22", a2_suave="3F3760"),
    "TP3": dict(fondo="0F1614", tarjeta="1B2421", linea="2C3833", texto="F0F2EE", gris="A2ABA6", gris2="6F7A75",
                a1="3DDC97", a2="E879C9", a1_suave="1F4D3A", a2_suave="57294C"),
}


def c(x, d=2):
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def miles(n):
    return f"{int(n):,}".replace(",", ".")


def rgb(h):
    return RGBColor.from_string(h)


class Deck:
    """Ayudantes de diseño: fondo, etiqueta tipo píldora, título, textos con estilo, formas, gráficos y notas."""

    def __init__(self, tp):
        self.p = PALETAS[tp]
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(13.333), Inches(7.5)
        self.n = 0

    # -------------------------------------------------------------- estructura
    def nueva(self, fondo=None, numero=True):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = rgb(fondo or self.p["fondo"])
        self.n += 1
        if numero:
            self.texto(s, 12.2, 6.95, 0.6, 0.3, [[(str(self.n), dict(s=11, c=self.p["gris2"]))]], align=PP_ALIGN.RIGHT)
        return s

    def notas(self, s, texto):
        s.notes_slide.notes_text_frame.text = texto

    def pildora(self, s, texto, color=None):
        color = color or self.p["a1"]
        ancho = 0.5 + len(texto) * 0.118
        f = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.75), Inches(0.45), Inches(ancho), Inches(0.42))
        f.adjustments[0] = 0.5
        f.fill.background()
        f.line.color.rgb, f.line.width = rgb(color), Pt(1.5)
        tf = f.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = texto
        self._fuente(r, dict(s=12, b=True, c=color, sp=150))
        f.name = "Etiqueta de sección"

    def titulo(self, s, texto, acento=None, size=40, y=1.0, ancho=11.8):
        partes = [[(texto, dict(f=TITULAR, s=size, b=True, c=self.p["texto"]))]]
        if acento:
            partes.append([(acento, dict(f=TITULAR, s=size, b=True, c=self.p["a1"]))])
        self.texto(s, 0.75, y, ancho, 1.5 if not acento else 2.4, partes, interlineado=1.0, nombre="Título")

    # -------------------------------------------------------------- texto
    def _fuente(self, r, o):
        f = r.font
        f.name = o.get("f", CUERPO)
        f.size = Pt(o.get("s", 16))
        f.bold = o.get("b", False)
        f.italic = o.get("i", False)
        f.color.rgb = rgb(o.get("c", self.p["gris"]))
        if o.get("sp"):
            r._r.get_or_add_rPr().set("spc", str(o["sp"]))

    def texto(self, s, x, y, w, h, parrafos, align=PP_ALIGN.LEFT, interlineado=1.1, espacio=6, anclaje=MSO_ANCHOR.TOP, nombre=None):
        """parrafos: lista de párrafos; cada párrafo es una lista de (texto, estilo)."""
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = anclaje
        for i, par in enumerate(parrafos):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment, p.line_spacing = align, interlineado
            p.space_after = Pt(espacio)
            for t, o in par:
                r = p.add_run()
                r.text = t
                self._fuente(r, o)
        if nombre:
            tb.name = nombre
        return tb

    def b(self, t, **o):   # atajo: texto blanco en negrita
        return (t, dict(b=True, c=self.p["texto"], **o))

    def g(self, t, **o):   # atajo: texto gris
        return (t, dict(c=self.p["gris"], **o))

    def a(self, t, n=1, **o):   # atajo: texto con color de acento
        return (t, dict(b=True, c=self.p["a1" if n == 1 else "a2"], **o))

    # -------------------------------------------------------------- formas
    def forma(self, s, tipo, x, y, w, h, relleno=None, borde=None, grosor=1.0, nombre=None, redondez=None):
        f = s.shapes.add_shape(tipo, Inches(x), Inches(y), Inches(w), Inches(h))
        if relleno:
            f.fill.solid()
            f.fill.fore_color.rgb = rgb(relleno)
        else:
            f.fill.background()
        if borde:
            f.line.color.rgb, f.line.width = rgb(borde), Pt(grosor)
        else:
            f.line.fill.background()
        if redondez is not None:
            f.adjustments[0] = redondez
        f.shadow.inherit = False
        if nombre:
            f.name = nombre
        return f

    def caja(self, s, x, y, w, h, relleno=None, **k):
        return self.forma(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, relleno or self.p["tarjeta"], redondez=0.08, **k)

    def circulo(self, s, cx, cy, d, relleno, borde=None, grosor=1.0):
        return self.forma(s, MSO_SHAPE.OVAL, cx - d / 2, cy - d / 2, d, d, relleno, borde, grosor)

    def linea(self, s, x1, y1, x2, y2, color, grosor=1.5, guiones=False):
        ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
        ln.line.color.rgb, ln.line.width = rgb(color), Pt(grosor)
        if guiones:
            ln.line.dash_style = MSO_LINE.DASH
        return ln

    def letra_en_circulo(self, s, cx, cy, letra, d=0.42, relleno=None, color=None):
        f = self.circulo(s, cx, cy, d, relleno or self.p["a1"])
        tf = f.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = letra
        self._fuente(r, dict(s=14, b=True, c=color or self.p["fondo"]))

    def smart(self, s, x, y, items, paso=0.78, ancho=5.2):
        for i, (letra, etiqueta, txt) in enumerate(items):
            yy = y + i * paso
            self.letra_en_circulo(s, x + 0.21, yy + 0.21, letra)
            self.texto(s, x + 0.6, yy + 0.02, ancho, paso, [[self.b(f"{etiqueta}: ", s=15), self.g(txt, s=15)]])

    # -------------------------------------------------------------- gráficos nativos
    def estilo_grafico(self, ch, tam=12):
        ch.font.name, ch.font.size = CUERPO, Pt(tam)
        ch.font.color.rgb = rgb(self.p["gris"])
        ch.has_legend = False
        cs = ch._chartSpace   # fondo transparente: el del gráfico y el del área de trazado
        sp = etree.SubElement(cs, qn("c:spPr"))
        cs.remove(sp)
        cs.find(qn("c:chart")).addnext(sp)
        sp.append(etree.fromstring('<a:noFill xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>'))
        sp.append(etree.fromstring('<a:ln xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:noFill/></a:ln>'))
        pa = cs.find(qn("c:chart")).find(qn("c:plotArea"))
        sp2 = etree.SubElement(pa, qn("c:spPr"))
        sp2.append(etree.fromstring('<a:noFill xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>'))

    def eje(self, ax, minimo=None, maximo=None, unidad=None, formato=None, grilla=True, visible=True):
        if minimo is not None:
            ax.minimum_scale = minimo
        if maximo is not None:
            ax.maximum_scale = maximo
        if unidad is not None:
            ax.major_unit = unidad
        ax.visible = visible
        ax.format.line.color.rgb = rgb(self.p["linea"])
        ax.tick_labels.font.size = Pt(12)
        ax.tick_labels.font.color.rgb = rgb(self.p["gris"])
        if formato:
            ax.tick_labels.number_format, ax.tick_labels.number_format_is_linked = formato, False
        ax.has_major_gridlines = grilla
        if grilla:
            ax.major_gridlines.format.line.color.rgb = rgb(self.p["linea"])
            ax.major_gridlines.format.line.width = Pt(0.75)

    # -------------------------------------------------------------- piezas repetidas
    def portada(self, titulo1, titulo2, subtitulo):
        s = self.nueva(numero=False)
        self.texto(s, 0.75, 0.75, 10, 0.4, [[("UNIVERSIDAD NACIONAL DE RAFAELA", dict(s=14, b=True, c=self.p["a1"], sp=300))]])
        self.texto(s, 0.75, 1.2, 10, 0.4, [[self.g("Aprendizaje Automático y Grandes Datos", s=18)]])
        self.texto(s, 0.75, 2.45, 11.5, 2.0, [[(titulo1, dict(f=TITULAR, s=46, b=True, c=self.p["texto"]))],
                                              [(titulo2, dict(f=TITULAR, s=46, b=True, c=self.p["texto"]))]], interlineado=0.95)
        self.texto(s, 0.75, 4.45, 11, 0.4, [[(subtitulo, dict(s=20, b=True, c=self.p["a2"]))]])
        self.forma(s, MSO_SHAPE.RECTANGLE, 0.75, 5.0, 1.3, 0.06, self.p["a1"])
        self.texto(s, 0.75, 5.35, 6, 0.3, [[("Integrantes", dict(s=13, b=True, c=self.p["a1"], sp=100))]])
        self.texto(s, 0.75, 5.7, 11.5, 0.5, [[(" · ".join(AUTORES), dict(f=TITULAR, s=20, b=True, c=self.p["texto"]))]])
        self.texto(s, 0.75, 6.6, 6, 0.3, [[self.g(FECHA, s=14)]])
        return s

    def separador(self):
        s = self.nueva(fondo=self.p["a1"], numero=False)
        self.texto(s, 0.75, 3.0, 11.5, 1.2, [[("Respaldo para preguntas", dict(f=TITULAR, s=54, b=True, c=self.p["fondo"]))]])
        self.texto(s, 0.75, 4.25, 11.5, 0.5, [[("No se proyecta en la exposición: solo si alguien pregunta.", dict(s=18, c=self.p["fondo"]))]])
        return s

    def cierre(self, puntos, notas):
        s = self.nueva()
        self.pildora(s, "CIERRE", self.p["a2"])
        self.titulo(s, "Conclusión")
        for i, (fuerte, resto) in enumerate(puntos):
            y = 2.25 + i * 1.15
            self.texto(s, 0.75, y, 1.0, 0.6, [[(f"0{i + 1}", dict(f=TITULAR, s=30, b=True, c=self.p["a1"]))]])
            self.texto(s, 1.9, y + 0.05, 10.6, 1.0, [[self.b(fuerte + " ", s=20), self.g(resto, s=20)]])
        self.forma(s, MSO_SHAPE.RECTANGLE, 0.75, 5.75, 11.8, 0.02, self.p["linea"])
        self.texto(s, 0.75, 6.0, 8, 0.9, [[("¿Preguntas?", dict(f=TITULAR, s=44, b=True, c=self.p["a1"]))]])
        self.notas(s, notas)
        return s

    def tabla(self, s, filas, x, y, anchos, resaltar=None, alto=0.42):
        sh = s.shapes.add_table(len(filas), len(filas[0]), Inches(x), Inches(y), Inches(sum(anchos)), Inches(alto * len(filas)))
        t = sh.table
        tblPr = t._tbl.tblPr   # sin el estilo azul por defecto ni bandas
        tblPr.set("firstRow", "0"); tblPr.set("bandRow", "0")
        for j, w in enumerate(anchos):
            t.columns[j].width = Inches(w)
        for i, fila in enumerate(filas):
            t.rows[i].height = Inches(alto)
            for j, val in enumerate(fila):
                cel = t.cell(i, j)
                cel.fill.solid()
                cel.fill.fore_color.rgb = rgb(self.p["a1_suave"] if (resaltar and i in resaltar) else
                                              (self.p["linea"] if i == 0 else self.p["tarjeta"]))
                cel.margin_left = cel.margin_right = Inches(0.08)
                cel.vertical_anchor = MSO_ANCHOR.MIDDLE
                tf = cel.text_frame
                tf.paragraphs[0].alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
                r = tf.paragraphs[0].add_run()
                r.text = str(val)
                self._fuente(r, dict(s=13, b=(i == 0 or (resaltar and i in resaltar)),
                                     c=self.p["texto"] if (i == 0 or (resaltar and i in resaltar)) else self.p["gris"]))
        return t

    def pesas(self, s, filas, x0, y0, ancho, paso, vmin, vmax, ticks, etiqueta_izq=3.0, resaltar=None):
        """Gráfico de pesas: un punto en entrenamiento (lila) y otro con datos nuevos (acento), unidos por una barra.
        filas = [(nombre, valor_entrenamiento, valor_nuevo)]. La distancia entre los puntos es lo que el modelo memorizó."""
        xa = x0 + etiqueta_izq
        esc = lambda v: xa + (v - vmin) / (vmax - vmin) * ancho
        y_fin = y0 + paso * (len(filas) - 0.4)
        for t in ticks:
            self.linea(s, esc(t), y0 - 0.25, esc(t), y_fin, self.p["linea"], 0.75)
            self.texto(s, esc(t) - 0.4, y_fin + 0.08, 0.8, 0.3, [[self.g(c(t, 1), s=12)]], align=PP_ALIGN.CENTER)
        for i, (nombre, ent, nuevo) in enumerate(filas):
            y = y0 + i * paso
            fuerte = resaltar is not None and nombre == resaltar
            self.texto(s, x0, y - 0.18, etiqueta_izq - 0.25, 0.4,
                       [[(nombre, dict(s=15, b=fuerte, c=self.p["texto"] if fuerte else self.p["gris"]))]], align=PP_ALIGN.RIGHT)
            self.forma(s, MSO_SHAPE.RECTANGLE, min(esc(ent), esc(nuevo)), y - 0.035, abs(esc(ent) - esc(nuevo)), 0.07, self.p["gris2"])
            self.circulo(s, esc(ent), y, 0.26, self.p["a2"])
            self.circulo(s, esc(nuevo), y, 0.26, self.p["a1"])
            self.texto(s, esc(vmax) + 0.3, y - 0.17, 1.2, 0.35, [[(f"−{c(ent - nuevo)}", dict(s=15, b=True, c=self.p["texto"] if (ent - nuevo) > 0.15 else self.p["gris"]))]])
        return esc

    def bala(self, s, x, y, ancho, valor, meta, vmin, vmax, etiqueta, txt_valor, txt_meta, extra=None, alto=0.38):
        """Barra contra la meta: pista gris, barra hasta el valor obtenido y una marca vertical en la meta."""
        esc = lambda v: x + (v - vmin) / (vmax - vmin) * ancho
        self.texto(s, x, y - 0.55, ancho, 0.4, [[self.b(etiqueta, s=16)]])
        self.forma(s, MSO_SHAPE.RECTANGLE, x, y, ancho, alto, self.p["tarjeta"])
        self.forma(s, MSO_SHAPE.RECTANGLE, x, y, esc(valor) - x, alto, self.p["a1"])
        self.forma(s, MSO_SHAPE.RECTANGLE, esc(meta) - 0.025, y - 0.12, 0.05, alto + 0.24, self.p["a2"])
        self.texto(s, esc(meta) - 1.0, y + alto + 0.12, 2.0, 0.3, [[(txt_meta, dict(s=12, b=True, c=self.p["a2"]))]], align=PP_ALIGN.CENTER)
        self.texto(s, esc(valor) + 0.12 if esc(valor) < x + ancho - 1.2 else esc(valor) - 1.3, y - 0.02, 1.2, alto + 0.05,
                   [[(txt_valor, dict(f=TITULAR, s=18, b=True, c=self.p["texto"]))]], anclaje=MSO_ANCHOR.MIDDLE)
        if extra:
            ve, te = extra
            self.forma(s, MSO_SHAPE.RECTANGLE, esc(ve) - 0.015, y - 0.12, 0.03, alto + 0.24, self.p["gris2"])
            self.texto(s, esc(ve) - 1.0, y + alto + 0.12, 2.0, 0.3, [[(te, dict(s=12, c=self.p["gris"]))]], align=PP_ALIGN.CENTER)

    def guardar(self, nombre):
        SALIDA.mkdir(parents=True, exist_ok=True)
        ruta = SALIDA / nombre
        self.prs.save(ruta)
        return ruta


# ====================================================================== TP2
def presentacion_tp2(m):
    t, o3 = m["obj09_tp2"], m["obj03"]
    mejor = t["mejor_modelo"]
    pr, cv, en, d, s_ = t["prueba"], t["cv_media"], t["entrenamiento"], t["datos"], t["criterio_smart"]
    olt = t["prueba_olt"]["resultados"]
    imp = t["importancia_permutacion"]
    adv = o3["advertencia_fuera_vs_desactualizado"]
    D = Deck("TP2")
    P = D.p

    # 1. Portada
    s = D.portada("Firmware fuera de estándar", "por puerto PON", "TP2 · Regresión")
    D.notas(s, "Presentación (≈ 15 s). Nombres del grupo y una frase: \"En el TP1 vimos qué equipos tiene la red. En este TP2 nos "
               "preguntamos algo más práctico: ¿por dónde conviene empezar a actualizar el firmware?\"")

    # 2. Apertura: la idea central, con el esquema de un puerto PON
    s = D.nueva()
    D.pildora(s, "APERTURA")
    D.titulo(s, "Actualizar de a un módem no escala:", "hay que elegir puertos", size=46, y=1.05)
    D.caja(s, 0.75, 4.35, 1.5, 1.2, nombre="OLT")
    D.texto(s, 0.75, 4.35, 1.5, 1.2, [[D.b("OLT", s=20)], [D.g("central", s=13)]], align=PP_ALIGN.CENTER, anclaje=MSO_ANCHOR.MIDDLE)
    D.linea(s, 2.25, 4.95, 4.1, 4.95, P["gris2"], 2.5)
    D.texto(s, 2.3, 4.55, 1.8, 0.3, [[D.g("1 fibra = 1 puerto PON", s=12)]], align=PP_ALIGN.CENTER)
    D.circulo(s, 4.3, 4.95, 0.42, P["linea"], P["gris"], 1.5)
    n_fuera = round(o3["pct_fuera_estandar"] / 100 * 16)
    for i in range(16):
        y = 3.4 + i * 0.205
        D.linea(s, 4.5, 4.95, 6.1, y, P["linea"], 0.75)
        D.circulo(s, 6.25, y, 0.16, P["a1"] if i in (1, 4, 8, 11, 14)[:n_fuera] else P["gris2"])
    D.texto(s, 6.6, 3.3, 6.2, 0.9, [[(f"{c(o3['pct_fuera_estandar'], 1)} %", dict(f=TITULAR, s=44, b=True, c=P["a1"]))]])
    D.texto(s, 6.6, 4.15, 6.0, 1.0, [[D.g("de los equipos de la red no tiene la versión de firmware más usada de su modelo", s=17)]])
    D.texto(s, 6.6, 5.35, 6.0, 1.2, [[D.b("Una ventana de mantenimiento actualiza un puerto entero. ", s=17),
                                      D.g("La pregunta es: ¿cuáles puertos tienen más equipos para actualizar?", s=17)]])
    D.notas(s, f"IDEA CENTRAL: el firmware se actualiza de a un puerto entero, así que lo útil es saber qué puertos tienen más "
               f"equipos fuera de estándar. (≈ 45 s)\n\n"
               f"\"Cada módem tiene un 'sistema operativo', el firmware. En esta red, casi 3 de cada 10 equipos "
               f"({c(o3['pct_fuera_estandar'], 1)} %) no tienen la versión que usan la mayoría de los equipos de su mismo modelo.\n\n"
               f"Actualizar casa por casa es lento. Lo práctico es esto [señalar el esquema]: desde la central sale una fibra, se "
               f"divide y llega a varias casas. Eso es un puerto PON. En una ventana de mantenimiento se puede actualizar el puerto "
               f"entero de una vez.\n\nEntonces la pregunta del TP es: mirando cómo es cada puerto, ¿podemos estimar qué porcentaje "
               f"de sus equipos está fuera de estándar? Así la empresa sabe por dónde empezar.\"\n\n"
               f"PASE: \"Primero veamos cuánto varía ese porcentaje de un puerto a otro.\"\n\n"
               f"SI PREGUNTAN \"¿qué es el estándar?\": la versión más común de cada modelo en el inventario. Es una definición "
               f"nuestra; la empresa todavía no nos confirmó cuál es la correcta.")

    # 3. Contexto: cada punto es un puerto
    s = D.nueva()
    D.pildora(s, "01 · CONTEXTO")
    D.titulo(s, "Cada puerto tiene su porcentaje")
    pons = pd.read_csv(RAIZ / "data" / "processed" / "pons.csv")
    rng = np.random.default_rng(42)
    datos = XyChartData()
    ser = datos.add_series("PON")
    for v in pons["pct_fw_fuera"]:
        ser.add_data_point(float(v * 100), float(rng.uniform(0.15, 0.85)))
    gf = s.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, Inches(0.75), Inches(2.6), Inches(8.0), Inches(3.4), datos)
    ch = gf.chart
    D.estilo_grafico(ch)
    sr = ch.plots[0].series[0]
    sr.format.line.fill.background()
    sr.marker.style, sr.marker.size = XL_MARKER_STYLE.CIRCLE, 9
    sr.marker.format.fill.solid(); sr.marker.format.fill.fore_color.rgb = rgb(P["a2"])
    sr.marker.format.line.fill.background()
    D.eje(ch.category_axis, 0, 100, 20, '0"%"', grilla=False)
    D.eje(ch.value_axis, 0, 1, visible=False, grilla=False)
    med = d["objetivo_mediana"] * 100
    D.texto(s, 0.75, 6.15, 8.0, 0.3, [[D.g("% de equipos del puerto con firmware distinto del más usado de su modelo", s=12)]], align=PP_ALIGN.CENTER)
    D.texto(s, 9.3, 2.6, 3.5, 3.6, [[D.b(f"{d['pon']} puertos PON", s=18)], [D.g("Cada punto es un puerto.", s=16)],
                                     [D.b(f"La mitad tiene menos de {c(med, 0)} %. ", s=16), D.g("Pero hay de todo:", s=16)],
                                     [D.a(f"{d['pon_con_0_pct']} puertos ", s=16), D.g("al 0 % y ", s=16), D.a(f"{d['pon_con_100_pct']} ", s=16),
                                      D.g("al 100 %.", s=16)]], espacio=12)
    D.notas(s, f"IDEA CENTRAL: el porcentaje cambia mucho de un puerto a otro; por eso tiene sentido predecirlo. (≈ 35 s)\n\n"
               f"\"Este gráfico es simple: cada punto es un puerto PON, y está más a la derecha cuanto más equipos fuera de estándar "
               f"tiene. Son {d['pon']} puertos.\n\nLa mitad tiene menos de {c(med, 0)} % de equipos para actualizar. Pero miren los "
               f"extremos: {d['pon_con_0_pct']} puertos están perfectos, al 0 %, y {d['pon_con_100_pct']} tienen todos sus equipos "
               f"fuera de estándar. Si supiéramos de antemano dónde está cada puerto, sabríamos por dónde empezar.\"\n\n"
               f"PASE: \"Para eso nos pusimos una meta concreta.\"\n\n"
               f"SI PREGUNTAN \"¿por qué los puntos están a distintas alturas?\": la altura no significa nada, es para que no se "
               f"pisen. Lo único que importa es la posición de izquierda a derecha.")

    # 4. Objetivo
    s = D.nueva()
    D.pildora(s, "02 · OBJETIVO")
    D.titulo(s, "Meta e indicador")
    D.texto(s, 0.75, 2.3, 6.2, 0.35, [[("Indicador", dict(s=15, b=True, c=P["a1"], sp=100))]])
    D.texto(s, 0.75, 2.7, 6.2, 0.9, [[D.b("% de equipos de cada puerto con firmware fuera de estándar", s=17)],
                                     [D.g("Lo predice el modelo a partir de cómo está compuesto el puerto", s=15)]])
    metas = [(f"R² ≥ {c(s_['metas']['R2_prueba'])}", "explicar casi la mitad de las diferencias entre puertos"),
             (f"R² ajustado ≥ {c(s_['metas']['R2_ajustado_prueba'])}", "sin inflar el resultado con variables de más"),
             ("MAE < adivinar", "equivocarse menos que decir siempre el promedio")]
    for i, (num, txt) in enumerate(metas):
        y = 3.85 + i * 1.0
        D.caja(s, 0.75, y, 6.2, 0.85)
        D.texto(s, 0.95, y, 2.6, 0.85, [[(num, dict(f=TITULAR, s=20, b=True, c=P["a1"]))]], anclaje=MSO_ANCHOR.MIDDLE)
        D.texto(s, 3.6, y, 3.2, 0.85, [[D.g(txt, s=14)]], anclaje=MSO_ANCHOR.MIDDLE)
    D.texto(s, 7.6, 2.3, 5, 0.35, [[("Objetivo SMART", dict(s=15, b=True, c=P["a1"], sp=100))]])
    D.smart(s, 7.6, 2.8, [("S", "Específico", f"los {d['pon']} puertos PON de la red"),
                          ("M", "Medible", "R², R² ajustado y error medio (MAE) en prueba"),
                          ("A", "Alcanzable", "con datos que ya están en el inventario"),
                          ("R", "Relevante", "elegir qué puertos actualizar primero"),
                          ("T", "Temporal", "modelo e informe para la entrega del TP2")], ancho=4.7)
    D.notas(s, f"IDEA CENTRAL: le pedimos al modelo tres cosas medibles, y las fijamos antes de ver los resultados. (≈ 40 s)\n\n"
               f"\"¿Qué le exigimos al modelo? Tres cosas. Primero, un R² de al menos {c(s_['metas']['R2_prueba'])}: que explique casi "
               f"la mitad de las diferencias entre puertos. Segundo, un R² ajustado de al menos {c(s_['metas']['R2_ajustado_prueba'])}, "
               f"que es lo mismo pero castiga si agregamos variables de relleno. Y tercero, que se equivoque menos que alguien que "
               f"adivina siempre el promedio.\n\nTodo con un objetivo SMART: específico, medible, alcanzable con los datos que ya "
               f"tenemos, relevante para la empresa y con fecha.\"\n\n"
               f"PASE: \"¿Y cómo lo probamos sin hacernos trampa?\"\n\n"
               f"SI PREGUNTAN \"¿por qué no usaron MAPE?\": porque {d['pon_con_0_pct']} puertos tienen 0 % y el MAPE divide por el "
               f"valor real. Dividir por cero da infinito.")

    # 5. Método: barra de partición
    s = D.nueva()
    D.pildora(s, "03 · MÉTODO")
    D.titulo(s, "Cómo lo probamos")
    total = d["entrenamiento"] + d["prueba"]
    x0, ancho = 0.75, 11.8
    w_tr = ancho * d["entrenamiento"] / total
    for k in range(5):
        D.forma(s, MSO_SHAPE.RECTANGLE, x0 + k * w_tr / 5, 2.55, w_tr / 5 - 0.04, 0.9, P["a2"] if k % 2 == 0 else P["a2_suave"])
        D.texto(s, x0 + k * w_tr / 5, 2.55, w_tr / 5, 0.9, [[(f"{k + 1}", dict(s=16, b=True, c=P["fondo"] if k % 2 == 0 else P["texto"]))]],
                align=PP_ALIGN.CENTER, anclaje=MSO_ANCHOR.MIDDLE)
    D.forma(s, MSO_SHAPE.RECTANGLE, x0 + w_tr + 0.08, 2.55, ancho - w_tr - 0.08, 0.9, P["a1"])
    D.texto(s, x0, 3.55, w_tr, 0.8, [[D.b(f"{d['entrenamiento']} puertos para aprender", s=16)],
                                     [D.g("divididos en 5 partes: el modelo aprende con 4 y se evalúa con la otra, 5 veces", s=14)]])
    D.texto(s, x0 + w_tr + 0.08, 3.55, ancho - w_tr, 0.8, [[D.a(f"{d['prueba']} de prueba", s=16)],
                                                          [D.g("se miran una sola vez, al final", s=14)]])
    modelos = [("Adivinar el promedio", P["gris2"]), ("Regresión lineal (base)", P["a2"]), ("Ridge", P["a2"]),
               ("Random Forest", P["a2"]), ("Gradient Boosting", P["a2"])]
    D.texto(s, 0.75, 4.75, 6, 0.35, [[("Modelos comparados", dict(s=15, b=True, c=P["a1"], sp=100))]])
    xx = 0.75
    for nombre, col in modelos:
        w = 0.45 + len(nombre) * 0.11
        f = D.forma(s, MSO_SHAPE.ROUNDED_RECTANGLE, xx, 5.2, w, 0.5, None, col, 1.25, redondez=0.5)
        D.texto(s, xx, 5.2, w, 0.5, [[(nombre, dict(s=14, c=P["texto"]))]], align=PP_ALIGN.CENTER, anclaje=MSO_ANCHOR.MIDDLE)
        xx += w + 0.2
    D.texto(s, 0.75, 6.05, 11.8, 0.6, [[D.a("Prohibido: ", n=2, s=15), D.g("cualquier dato que salga de la versión de firmware. "
                                                                             "Sería darle la respuesta al modelo.", s=15)]])
    D.notas(s, f"IDEA CENTRAL: separamos los puertos para que el modelo nunca vea la prueba mientras aprende. (≈ 40 s)\n\n"
               f"\"Separamos los puertos en dos grupos. Con {d['entrenamiento']} puertos el modelo aprende. Y esos los dividimos en "
               f"5 partes: aprende con 4 y lo evaluamos con la quinta, cinco veces. Eso se llama validación cruzada.\n\nLos otros "
               f"{d['prueba']} puertos los guardamos bajo llave y los miramos una sola vez, al final.\n\nProbamos cuatro modelos, de "
               f"menos a más complejos, contra alguien que adivina siempre el promedio. Y una regla de oro: nada que salga de la "
               f"versión del firmware entra al modelo, porque eso sería pasarle la respuesta.\"\n\n"
               f"PASE: \"Y acá apareció el primer hallazgo.\"\n\n"
               f"SI PREGUNTAN \"¿qué variables usa?\": localidad, tarjeta, cantidad de equipos del puerto, % con TV, % de equipos "
               f"modernos, cantidad de modelos y la proporción de los 5 modelos más comunes.")

    # 6. Hallazgo: memorizar no es aprender (gráfico de pesas)
    s = D.nueva()
    D.pildora(s, "04 · HALLAZGO")
    D.titulo(s, "Memorizar no es aprender")
    filas = [("Regresión lineal", en["Regresión Lineal"]["R2"], cv["Regresión Lineal"]["R2"]), ("Ridge", en["Ridge"]["R2"], cv["Ridge"]["R2"]),
             ("Random Forest", en["Random Forest"]["R2"], cv["Random Forest"]["R2"]),
             ("Gradient Boosting", en["Gradient Boosting"]["R2"], cv["Gradient Boosting"]["R2"])]
    D.texto(s, 3.75, 2.2, 6.0, 0.35, [[("●", dict(s=16, c=P["a2"])), D.g("  con puertos que ya vio      ", s=14),
                                       ("●", dict(s=16, c=P["a1"])), D.g("  con puertos nuevos", s=14)]])
    D.pesas(s, filas, 0.75, 3.05, 5.4, 0.85, 0.3, 0.8, [0.3, 0.4, 0.5, 0.6, 0.7, 0.8], resaltar=mejor)
    D.texto(s, 0.75, 6.65, 9.4, 0.3, [[D.g("R²: qué parte de las diferencias entre puertos explica el modelo (1 = todas)", s=12)]], align=PP_ALIGN.CENTER)
    rf = filas[2]
    D.texto(s, 10.6, 2.6, 2.3, 3.4, [[(f"−{c(rf[1] - rf[2])}", dict(f=TITULAR, s=40, b=True, c=P["a1"]))],
                                      [D.g(f"Random Forest pasa de {c(rf[1])} a {c(rf[2])}: aprendió de memoria los puertos que vio.", s=15)],
                                      [D.b("Los modelos simples casi no pierden.", s=15)]], espacio=10)
    D.notas(s, f"IDEA CENTRAL: los modelos complejos se aprenden de memoria los puertos; los simples aprenden la idea. (≈ 50 s)\n\n"
               f"\"Este gráfico compara, para cada modelo, dos cosas. El punto lila es cuánto acierta con los puertos que ya vio. "
               f"El punto ámbar, con puertos nuevos. La barrita entre los dos es lo que se aprendió de memoria.\n\nMiren el Random "
               f"Forest [señalar]: con lo que ya vio explica {c(rf[1])}, pero con puertos nuevos baja a {c(rf[2])}. Es como el alumno "
               f"que se aprende las respuestas del práctico de memoria: en el examen le va peor.\n\nLa regresión lineal y Ridge casi no "
               f"pierden: aprendieron la idea general.\"\n\n"
               f"PASE: \"Entonces, ¿quién ganó?\"\n\n"
               f"SI PREGUNTAN \"¿por qué memorizan?\": porque con {d['entrenamiento']} puertos hay pocos datos para tantas reglas. "
               f"Eso se llama varianza alta (sobreajuste).")

    # 7. Resultado: barras contra la meta
    s = D.nueva()
    D.pildora(s, "05 · RESULTADO")
    D.titulo(s, f"{mejor} cumple las tres metas")
    D.bala(s, 0.75, 2.85, 7.3, pr[mejor]["R2"], s_["metas"]["R2_prueba"], 0, 1, "R² en prueba", c(pr[mejor]["R2"]),
           f"meta {c(s_['metas']['R2_prueba'])}")
    D.bala(s, 0.75, 4.25, 7.3, pr[mejor]["R2_ajustado"], s_["metas"]["R2_ajustado_prueba"], 0, 1, "R² ajustado en prueba",
           c(pr[mejor]["R2_ajustado"]), f"meta {c(s_['metas']['R2_ajustado_prueba'])}")
    mae_d = s_["metas"]["MAE_dummy_prueba"]
    D.bala(s, 0.75, 5.65, 7.3, pr[mejor]["MAE"], mae_d, 0, 0.2, "Error medio (MAE): menor es mejor", c(pr[mejor]["MAE"], 3),
           f"adivinar {c(mae_d, 3)}")
    pts = round(pr[mejor]["MAE"] * 100)
    D.texto(s, 9.0, 2.6, 3.8, 3.6, [[(f"≈ {pts} puntos", dict(f=TITULAR, s=34, b=True, c=P["a1"]))],
                                     [D.g(f"de error medio por puerto: si un puerto tiene 30 %, el modelo suele decir entre "
                                          f"{30 - pts} y {30 + pts} %.", s=15)],
                                     [D.b("Lo elegimos con la validación cruzada, ", s=15), D.g("no mirando la prueba.", s=15)]], espacio=12)
    D.notas(s, f"IDEA CENTRAL: {mejor}, un modelo lineal simple, cumple las tres metas. (≈ 45 s)\n\n"
               f"\"Ganó {mejor}, que es una regresión lineal con un freno para que no exagere. Las barras ámbar son lo que logró y "
               f"la marca lila, la meta.\n\nR² de {c(pr[mejor]['R2'])}, contra una meta de {c(s_['metas']['R2_prueba'])}. R² ajustado "
               f"de {c(pr[mejor]['R2_ajustado'])}, contra {c(s_['metas']['R2_ajustado_prueba'])}. Y un error medio de "
               f"{c(pr[mejor]['MAE'], 3)}, contra {c(mae_d, 3)} de adivinar el promedio.\n\nEn criollo: se equivoca en unos "
               f"{c(pr[mejor]['MAE'] * 100, 0)} puntos por puerto. Y lo importante: lo elegimos con la validación cruzada, sin mirar la "
               f"prueba.\"\n\n"
               f"PASE: \"¿Y qué es lo que mira el modelo para acertar?\"\n\n"
               f"SI PREGUNTAN \"¿por qué no el Random Forest, si en prueba sacó {c(pr['Random Forest']['R2'])}?\": porque la prueba "
               f"tiene solo {d['prueba']} puertos y salió fácil para todos. En validación cruzada, que es más estable, el Random Forest "
               f"es peor ({c(cv['Random Forest']['R2'])} contra {c(cv[mejor]['R2'])}) y además memoriza.")

    # 8. Comprensión: burbujas de importancia
    s = D.nueva()
    D.pildora(s, "06 · COMPRENSIÓN", P["a2"])
    D.titulo(s, "Qué mira el modelo")
    nombres = {"pct_catv": "% con TV", "Localidad": "Localidad", "share_EG8141A5": "Prop. EG8141A5", "share_EG8143A5": "Prop. EG8143A5",
               "onts": "Equipos del puerto"}
    top = sorted(((k, v) for k, v in imp.items() if k in nombres), key=lambda kv: -kv[1])
    vmax = top[0][1]
    xx = 0.75
    for (k, v), ancho in zip(top, [2.9, 1.6, 1.5, 1.45, 1.4]):   # un casillero fijo por burbuja: nada se pisa
        dmt = max(0.25, 2.6 * np.sqrt(max(v, 0) / vmax))
        cx = xx + ancho / 2
        D.circulo(s, cx, 3.85, dmt, P["a1"] if k == "pct_catv" else (P["a2"] if v > 0.05 else P["gris2"]))
        D.texto(s, xx, 5.25, ancho, 0.6, [[D.b(nombres[k], s=13)]], align=PP_ALIGN.CENTER, interlineado=0.95)
        D.texto(s, xx, 5.85, ancho, 0.35, [[D.g(c(v), s=14)]], align=PP_ALIGN.CENTER)
        xx += ancho
    D.texto(s, 0.75, 6.4, 8.5, 0.3, [[D.g("Tamaño = cuánto empeora el modelo si se le esconde esa variable", s=12)]])
    D.caja(s, 9.85, 2.4, 3.0, 3.75)
    D.texto(s, 10.05, 2.6, 2.65, 3.4, [[("Insight", dict(s=15, b=True, c=P["a2"]))],
                                      [D.g(f"El % con TV es casi lo mismo que la proporción de EG8143A5 (correlación "
                                           f"{c(t['correlacion_pct_catv_share_EG8143A5'])}).", s=13)],
                                      [D.g("En ese modelo la versión más repetida es una V3, pero la mayoría tiene alguna V5, más nueva.", s=13)],
                                      [D.b("Parte de lo que aprende es nuestra definición de estándar.", s=13)]], espacio=8)
    D.notas(s, f"IDEA CENTRAL: lo que más pesa es qué modelos de equipo tiene el puerto, y en qué localidad está. (≈ 45 s)\n\n"
               f"\"Para saber qué mira el modelo, le escondimos las variables de a una y medimos cuánto empeora. Cuanto más grande la "
               f"burbuja, más importante.\n\nLa más grande es el porcentaje de equipos con TV ({c(imp['pct_catv'])}). Después, la "
               f"localidad ({c(imp['Localidad'])}).\n\nY acá hay un detalle [señalar el recuadro]: el % con TV es casi lo mismo que la "
               f"proporción de un modelo, el EG8143A5. En ese modelo, la versión 'estándar' es la V3, pero la mayoría de esos equipos "
               f"tiene la V5, que es más nueva. O sea: parte de lo que aprende el modelo es cómo definimos el estándar. Por eso hay "
               f"que validarlo con la empresa.\"\n\n"
               f"PASE: \"Y entonces probamos una cosa más: ¿ayudan los datos técnicos de la red?\"")

    # 9. Prueba extra: gráfico de pendiente
    s = D.nueva()
    D.pildora(s, "07 · PRUEBA EXTRA", P["a2"])
    D.titulo(s, "Los datos de la red no ayudan")
    # gráfico de pendiente dibujado a mano: dos columnas (sin / con OLT) y una línea por métrica
    series = [("R² validación cruzada", olt["sin OLT"]["R2_cv"], olt["con OLT"]["R2_cv"], P["a2"]),
              ("R² prueba", olt["sin OLT"]["R2_prueba"], olt["con OLT"]["R2_prueba"], P["a1"]),
              ("R² ajustado prueba", olt["sin OLT"]["R2_ajustado_prueba"], olt["con OLT"]["R2_ajustado_prueba"], P["gris"])]
    xl, xr = 3.6, 6.9
    vals = [v for _, a_, b_, _ in series for v in (a_, b_)]
    lo, hi = min(vals) - 0.04, max(vals) + 0.04
    ypos = lambda v: 5.9 - (v - lo) / (hi - lo) * 3.3

    def sin_choques(ys, sep=0.36):
        """Separa etiquetas que caerían una sobre otra, manteniendo su orden vertical."""
        orden = sorted(range(len(ys)), key=lambda i: ys[i])
        out = list(ys)
        for a_, b_ in zip(orden, orden[1:]):
            out[b_] = max(out[b_], out[a_] + sep)
        return out

    for x_, txt in ((xl, "Sin datos de la OLT"), (xr, "Con datos de la OLT")):
        D.linea(s, x_, 2.45, x_, 6.1, P["linea"], 0.75)
        D.texto(s, x_ - 1.5, 6.2, 3.0, 0.4, [[D.b(txt, s=15)]], align=PP_ALIGN.CENTER)
    for nombre, a_, b_, col in series:
        D.linea(s, xl, ypos(a_), xr, ypos(b_), col, 3)
        D.circulo(s, xl, ypos(a_), 0.24, col)
        D.circulo(s, xr, ypos(b_), 0.24, col)
    y_izq = sin_choques([ypos(a_) for _, a_, _, _ in series])
    y_der = sin_choques([ypos(b_) for _, _, b_, _ in series])
    for (nombre, a_, b_, col), yi, yd in zip(series, y_izq, y_der):
        D.texto(s, 0.3, yi - 0.19, xl - 0.5, 0.38, [[(nombre + "  ", dict(s=13, b=True, c=col)), (c(a_), dict(s=16, b=True, c=col))]],
                align=PP_ALIGN.RIGHT, anclaje=MSO_ANCHOR.MIDDLE)
        D.texto(s, xr + 0.25, yd - 0.19, 1.0, 0.38, [[(c(b_), dict(s=16, b=True, c=col))]], anclaje=MSO_ANCHOR.MIDDLE)
    D.texto(s, 8.6, 2.6, 4.2, 3.6, [[D.b("Señal, distancia y equipos encendidos", s=17)],
                                     [D.g("no mejoran la predicción: las tres líneas bajan.", s=16)],
                                     [D.a("El firmware desactualizado es un tema administrativo, no técnico.", s=16)]], espacio=12)
    D.notas(s, f"IDEA CENTRAL: agregar datos técnicos de la red no mejora nada; el firmware depende de decisiones administrativas. "
               f"(≈ 40 s)\n\n\"La empresa nos pasó otro listado, de la central, con la señal, la distancia y si cada equipo estaba "
               f"encendido. Lo sumamos al modelo, a ver si mejoraba.\n\n¿Resultado? [señalar] Las tres líneas bajan. El R² de prueba "
               f"pasa de {c(olt['sin OLT']['R2_prueba'])} a {c(olt['con OLT']['R2_prueba'])}.\n\nLa conclusión es interesante: que un "
               f"equipo esté desactualizado no tiene nada que ver con la fibra ni con la señal. Depende de qué localidades y qué "
               f"modelos se actualizaron. Es un tema administrativo.\"\n\n"
               f"PASE: \"Cerramos.\"")

    # 10. Cierre
    D.cierre([("La composición del puerto predice su firmware.",
               f"{mejor} explica la mitad de las diferencias (R² {c(cv[mejor]['R2'])} en validación, {c(pr[mejor]['R2'])} en prueba) "
               f"con {c(pr[mejor]['MAE'] * 100, 0)} puntos de error medio."),
              ("Lo simple gana.", f"Los árboles memorizan: el Random Forest cae de {c(en['Random Forest']['R2'])} a "
                                  f"{c(cv['Random Forest']['R2'])} con puertos nuevos."),
              ("Antes de actualizar, validar el estándar.",
               f"{miles(adv['fuera_estandar_con_generacion_mayor'])} de {miles(o3['equipos_fuera_estandar'])} equipos 'fuera' tienen una "
               f"versión más nueva.")],
             f"IDEA CENTRAL: se puede estimar qué puertos actualizar, con un modelo simple, pero primero hay que validar qué versión es "
             f"la correcta. (≈ 40 s)\n\n\"Tres ideas para llevarse. Uno: mirando cómo está compuesto un puerto, podemos estimar cuánto "
             f"firmware fuera de estándar tiene, con unos {c(pr[mejor]['MAE'] * 100, 0)} puntos de error. Dos: el modelo simple le gana "
             f"al complejo, porque el complejo memoriza. Y tres, la advertencia: {miles(adv['fuera_estandar_con_generacion_mayor'])} "
             f"equipos que figuran 'fuera de estándar' en realidad tienen una versión más nueva. Antes de mandar a actualizar, la "
             f"empresa tiene que confirmar cuál es la versión correcta.\n\n¿Preguntas?\"")

    # ---------------------------------------------------------------- respaldo
    D.separador()
    s = D.nueva()
    D.pildora(s, "R1 · RESPALDO")
    D.titulo(s, "Métricas completas")
    mods = ["Dummy (promedio)", "Regresión Lineal", "Ridge", "Random Forest", "Gradient Boosting"]
    nom = {"Dummy (promedio)": "Adivinar el promedio", "Regresión Lineal": "Regresión lineal"}
    filas = [["Modelo", "R² entren.", "R² validación", "R² prueba", "R² ajust.", "RMSE prueba", "MAE prueba"]]
    for mo in mods:
        filas.append([nom.get(mo, mo), c(en[mo]["R2"]), c(cv[mo]["R2"]), c(pr[mo]["R2"]), c(pr[mo]["R2_ajustado"]), c(pr[mo]["RMSE"], 3),
                      c(pr[mo]["MAE"], 3)])
    D.tabla(s, filas, 0.75, 2.4, [3.1, 1.45, 1.6, 1.45, 1.45, 1.6, 1.45], resaltar=[mods.index(mejor) + 1], alto=0.55)
    D.texto(s, 0.75, 6.0, 11.8, 0.6, [[D.g(f"Validación cruzada de 5 partes sobre {d['entrenamiento']} puertos; prueba: {d['prueba']} "
                                           f"puertos. Errores en proporción (0,10 = 10 puntos).", s=13)]])
    D.notas(s, "Respaldo. Si preguntan por los números exactos: la fila resaltada es el modelo elegido. Mostrar que en validación "
               "cruzada gana, y que en prueba todos salen mejor que en validación porque la prueba resultó fácil.")

    s = D.nueva()
    D.pildora(s, "R2 · RESPALDO")
    D.titulo(s, "Residuos del modelo elegido")
    pred = pd.read_csv(RAIZ / "results" / "tp2_predicciones_prueba.csv")
    datos = XyChartData()
    ser = datos.add_series("Prueba")
    for p_, r_ in zip(pred["predicho"], pred["residuo"]):
        ser.add_data_point(float(p_ * 100), float(r_ * 100))
    gf = s.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, Inches(0.75), Inches(2.3), Inches(7.2), Inches(4.2), datos)
    ch = gf.chart
    D.estilo_grafico(ch)
    sr = ch.plots[0].series[0]
    sr.format.line.fill.background()
    sr.marker.style, sr.marker.size = XL_MARKER_STYLE.CIRCLE, 10
    sr.marker.format.fill.solid(); sr.marker.format.fill.fore_color.rgb = rgb(P["a1"])
    sr.marker.format.line.fill.background()
    D.eje(ch.category_axis, 0, 100, 20, '0"%"', grilla=False)
    D.eje(ch.value_axis, -50, 50, 25, '0" p.p.";"−"0" p.p."')
    ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW   # números abajo, no sobre la línea del cero
    res, pat = t["residuos"], t["residuos"]["patrones"]
    D.texto(s, 8.5, 2.4, 4.3, 4.0, [[D.g("Horizontal: % predicho. Vertical: error (real − predicho).", s=13)],
                                     [D.b("Centrados en cero, ", s=15), D.g("sin forma de embudo.", s=15)],
                                     [D.g(f"No son normales (Shapiro-Wilk p = {c(res['cv_entrenamiento']['shapiro_p'], 4)}).", s=15)],
                                     [D.b("Patrón: ", s=15), D.g(f"en puertos con 5 equipos o menos el error es {c(pat['MAE_pon_5_onts_o_menos'], 3)}, "
                                                                 f"contra {c(pat['MAE_pon_mas_de_5_onts'], 3)} en el resto.", s=15)]], espacio=10)
    D.notas(s, "Respaldo (cuestionario, pregunta 3). Los residuos están centrados en cero, pero los puertos chicos tienen más error: un "
               "puerto con 2 equipos solo puede valer 0, 50 o 100 %. Mejora posible: ponderar cada puerto por su cantidad de equipos.")

    s = D.nueva()
    D.pildora(s, "R3 · RESPALDO")
    D.titulo(s, "Curva de aprendizaje")
    cr = pd.read_csv(RAIZ / "reports" / "TP2" / f"curva_aprendizaje_{mejor.lower()}.csv")
    cf = pd.read_csv(RAIZ / "reports" / "TP2" / "curva_aprendizaje_random_forest.csv")
    cd = CategoryChartData()
    cd.categories = [str(int(n)) for n in cr["n_entrenamiento"]]
    lineas = [(f"{mejor}: validación", cr["RMSE_validacion"], P["a1"], False), (f"{mejor}: entrenamiento", cr["RMSE_entrenamiento"], P["a1"], True),
              ("Random Forest: validación", cf["RMSE_validacion"], P["a2"], False), ("Random Forest: entrenamiento", cf["RMSE_entrenamiento"], P["a2"], True)]
    for nombre, v, _, _ in lineas:
        cd.add_series(nombre, [round(x * 100, 1) for x in v])
    gf = s.shapes.add_chart(XL_CHART_TYPE.LINE, Inches(0.75), Inches(2.3), Inches(8.0), Inches(4.2), cd)
    ch = gf.chart
    D.estilo_grafico(ch)
    for sr, (_, _, col, punteada) in zip(ch.plots[0].series, lineas):
        sr.format.line.color.rgb, sr.format.line.width = rgb(col), Pt(3)
        sr.smooth = False
        if punteada:
            sr.format.line.dash_style = MSO_LINE.DASH
    D.eje(ch.value_axis, 8, 18, 2, '0" p.p."')
    D.eje(ch.category_axis, grilla=False)
    cu = t["curva_aprendizaje"]
    D.texto(s, 9.2, 2.4, 3.6, 4.0, [[D.g("RMSE según cuántos puertos se usan para entrenar. Continua: validación; punteada: entrenamiento.", s=13)],
                                     [D.a(f"{mejor}: ", s=15), D.g(f"las líneas casi se tocan ({c(cu[mejor + ' (mejor)']['brecha_final_pp'], 1)} "
                                                                   f"puntos). Su límite es el sesgo: faltan variables.", s=15)],
                                     [D.a("Random Forest: ", n=2, s=15), D.g(f"quedan separadas ({c(cu['Random Forest']['brecha_final_pp'], 1)} "
                                                                             f"puntos): memoriza.", s=15)]], espacio=10)
    D.notas(s, "Respaldo (cuestionario, pregunta 2: sesgo y varianza). Si las curvas se juntan en un error alto, el límite es el sesgo; "
               "si quedan separadas, es varianza. Más puertos ayudarían poco a Ridge: harían falta variables nuevas.")

    s = D.nueva()
    D.pildora(s, "R4 · RESPALDO")
    D.titulo(s, "Decisiones del diseño")
    sh = t["comparacion_5_vs_22_modelos"]
    k5, k22 = list(sh)
    gs = t["gridsearch_mejora"]
    tarjetas = [("5 modelos, no 22", c(sh[k5]["R2_ajustado_prueba"]), f"R² ajustado con 5 proporciones de modelo; con las 22 cae a "
                                                                       f"{c(sh[k22]['R2_ajustado_prueba'])} ({sh[k22]['predictores']} variables para "
                                                                       f"{d['entrenamiento']} puertos)."),
                ("Búsqueda de hiperparámetros", f"−{c(gs['Gradient Boosting']['mejora_pct'], 0)} %", f"de error en Gradient Boosting "
                                                                                                     f"(Random Forest: −{c(gs['Random Forest']['mejora_pct'], 0)} %). "
                                                                                                     "Igual siguen memorizando."),
                ("Sin MAPE", str(d["pon_con_0_pct"]), "puertos tienen 0 %: el MAPE divide por el valor real y daría infinito.")]
    for i, (tit, num, txt) in enumerate(tarjetas):
        x = 0.75 + i * 4.05
        D.caja(s, x, 2.4, 3.75, 3.9)
        D.texto(s, x + 0.25, 2.6, 3.3, 0.5, [[D.b(tit, s=16)]])
        D.texto(s, x + 0.25, 3.2, 3.3, 1.0, [[(num, dict(f=TITULAR, s=40, b=True, c=P["a1"]))]])
        D.texto(s, x + 0.25, 4.3, 3.3, 1.9, [[D.g(txt, s=14)]])
    D.notas(s, "Respaldo. Por qué se usaron solo 5 proporciones de modelo, cuánto mejoró la búsqueda de hiperparámetros y por qué no "
               "se informa MAPE.")

    s = D.nueva()
    D.pildora(s, "R5 · RESPALDO")
    D.titulo(s, "Fuera de estándar ≠ desactualizado")
    fuera, nuevos = o3["equipos_fuera_estandar"], adv["fuera_estandar_con_generacion_mayor"]
    D.forma(s, MSO_SHAPE.RECTANGLE, 0.75, 3.0, 11.8 * nuevos / fuera, 1.1, P["a2"])
    D.forma(s, MSO_SHAPE.RECTANGLE, 0.75 + 11.8 * nuevos / fuera + 0.06, 3.0, 11.8 * (1 - nuevos / fuera) - 0.06, 1.1, P["a1"])
    D.texto(s, 0.95, 3.0, 4.5, 1.1, [[(miles(nuevos), dict(f=TITULAR, s=30, b=True, c=P["fondo"]))]], anclaje=MSO_ANCHOR.MIDDLE)
    D.texto(s, 0.75 + 11.8 * nuevos / fuera + 0.25, 3.0, 4.5, 1.1, [[(miles(fuera - nuevos), dict(f=TITULAR, s=30, b=True, c=P["fondo"]))]],
            anclaje=MSO_ANCHOR.MIDDLE)
    D.texto(s, 0.75, 4.3, 11.8 * nuevos / fuera, 0.8, [[D.b("con una versión MÁS NUEVA que la más común", s=15)],
                                                       [D.g(f"casi todos EG8143A5 (estándar V3, tienen V5)", s=14)]])
    D.texto(s, 0.75 + 11.8 * nuevos / fuera + 0.06, 4.3, 6, 0.8, [[D.b("con una versión distinta y no más nueva", s=15)]])
    D.texto(s, 0.75, 5.6, 11.8, 0.8, [[D.g(f"De los {miles(fuera)} equipos 'fuera de estándar'. Definimos el estándar como la versión más "
                                           f"común de cada modelo; la empresa tiene que confirmar cuál es la correcta.", s=15)]])
    D.notas(s, "Respaldo. Si preguntan por qué Larrechea aparece tan desactualizada: la mayoría de sus EG8143A5 tiene V5, más nueva "
               "que el 'estándar' V3. La definición se mantuvo (es la del CLAUDE.md), pero se informa la advertencia.")
    return D.guardar("TP2_presentacion.pptx")


# ====================================================================== TP3
def presentacion_tp3(m):
    t = m["obj14_tp3"]
    mejor = t["mejor_modelo"]
    pr, cv, en, d, s_ = t["prueba"], t["cv_media"], t["entrenamiento"], t["datos"], t["criterio_smart"]
    vec = pr["Regla de los vecinos"]
    (tn, fp), (fn, tp) = t["matrices_confusion_prueba"][mejor]
    imp = t["importancia_permutacion"]
    cl = t["clustering"]
    pe = cl["perfil_extra"]
    D = Deck("TP3")
    P = D.p
    rlog = mejor.lower()

    # 1. Portada
    s = D.portada("Clientes con la señal", "de la fibra en riesgo", "TP3 · Clasificación")
    D.notas(s, "Presentación (≈ 15 s). \"En el TP3 cambiamos de pregunta: ya no miramos los equipos, sino la señal que le llega a "
               "cada cliente.\"")

    # 2. Apertura: regla de la señal en dBm
    s = D.nueva()
    D.pildora(s, "APERTURA")
    D.titulo(s, "Para anticipar quién queda al límite,", "mirá a sus vecinos", size=46, y=1.05)
    x0, ancho, vmin, vmax = 0.75, 11.8, -15, -30
    esc = lambda v: x0 + (v - vmin) / (vmax - vmin) * ancho
    D.forma(s, MSO_SHAPE.RECTANGLE, esc(-15), 4.35, esc(-25) - esc(-15), 0.55, P["tarjeta"])
    D.forma(s, MSO_SHAPE.RECTANGLE, esc(-25), 4.35, esc(-27) - esc(-25), 0.55, P["a2_suave"])
    D.forma(s, MSO_SHAPE.RECTANGLE, esc(-27), 4.35, esc(-30) - esc(-27), 0.55, P["a2"])
    for v in range(-15, -31, -5):
        D.texto(s, esc(v) - 0.5, 5.0, 1.0, 0.3, [[D.g(f"−{abs(v)} dBm", s=12)]], align=PP_ALIGN.CENTER)
    D.texto(s, esc(-15) + 0.15, 4.35, 4, 0.55, [[D.g("señal normal", s=14)]], anclaje=MSO_ANCHOR.MIDDLE)
    D.texto(s, esc(-25), 3.55, 2.6, 0.75, [[D.a("−25: en riesgo", n=2, s=15)], [D.g("nuestro umbral", s=13)]])
    D.texto(s, esc(-27), 5.45, 3.0, 0.75, [[D.a("−27: el mínimo", n=2, s=15)], [D.g("que tolera el equipo", s=13)]])
    D.texto(s, 0.75, 5.75, 6.4, 1.0, [[D.g("Potencia que le llega al módem por la fibra. Más a la derecha, más débil: "
                                           "por debajo de −27 el cliente se queda sin servicio.", s=15)]])
    D.notas(s, "IDEA CENTRAL: para saber si un cliente nuevo va a quedar con la señal al límite, alcanza con mirar la señal de sus "
               "vecinos de fibra. (≈ 45 s)\n\n\"A cada casa le llega una cantidad de 'luz' por la fibra, que se mide en dBm. Esta barra va "
               "de una señal fuerte, a la izquierda, a una débil, a la derecha.\n\nEl equipo deja de funcionar por debajo de −27. Nosotros "
               "llamamos 'en riesgo' a todo lo que está por debajo de −25: el cliente tiene internet, pero está al borde, y cualquier "
               "problemita lo deja sin servicio.\n\nLa pregunta del TP es: ¿podemos saber quién va a quedar al límite ANTES de medir su "
               "señal? Spoiler, y es la idea de toda la presentación: sí, y la clave está en los vecinos.\"\n\n"
               "PASE: \"Primero, ¿cuántos clientes están en esa zona?\"\n\n"
               "SI PREGUNTAN \"¿por qué −25 y no −27?\": porque −27 es el límite del equipo (clase B+); −25 deja 2 dB de margen para "
               "avisar antes de que se corte.")

    # 3. Contexto: casitas
    s = D.nueva()
    D.pildora(s, "01 · CONTEXTO")
    D.titulo(s, "1 de cada 9 clientes está en riesgo")
    uno_cada = round(1 / d["pct_en_riesgo"])
    for i in range(uno_cada):
        x = 0.9 + i * 0.9
        col = P["a2"] if i == uno_cada - 1 else P["gris2"]
        D.forma(s, MSO_SHAPE.ISOSCELES_TRIANGLE, x, 3.0, 0.7, 0.42, col)
        D.forma(s, MSO_SHAPE.RECTANGLE, x + 0.1, 3.42, 0.5, 0.48, col)
    D.texto(s, 0.75, 4.2, 8.2, 0.4, [[D.g("Cada casita representa a 1 de cada 9 clientes online", s=13)]])
    D.texto(s, 0.75, 4.9, 4.0, 1.5, [[(miles(d["equipos"]), dict(f=TITULAR, s=40, b=True, c=P["texto"]))],
                                      [D.g("clientes online con lectura válida", s=15)]])
    D.texto(s, 4.75, 4.9, 4.2, 1.5, [[(miles(d["en_riesgo"]), dict(f=TITULAR, s=40, b=True, c=P["a2"]))],
                                      [D.g(f"en riesgo ({c(d['pct_en_riesgo'] * 100, 1)} %)", s=15)]])
    D.texto(s, 9.5, 2.9, 3.3, 3.4, [[D.b(f"{d['pon']} puertos PON", s=16)], [D.g("Datos: listado de la central (OLT) del 29/10/2026, "
                                                                               "cruzado con el inventario del TP1.", s=15)],
                                     [D.g("Es una foto de una tarde.", s=15)]], espacio=10)
    D.notas(s, f"IDEA CENTRAL: hay pocos clientes en riesgo, y eso hace el problema más difícil. (≈ 35 s)\n\n\"Tenemos "
               f"{miles(d['equipos'])} clientes con internet y con una lectura de señal válida. De esos, {miles(d['en_riesgo'])} están en "
               f"riesgo: más o menos 1 de cada 9 [señalar la casita de color].\n\nQue sean pocos parece bueno para la empresa, pero para "
               f"un modelo es un desafío: es muy fácil 'acertar' diciendo que nadie está en riesgo. Ya vamos a ver por qué eso es una "
               f"trampa.\"\n\nPASE: \"Antes, la meta que nos pusimos.\"")

    # 4. Objetivo
    s = D.nueva()
    D.pildora(s, "02 · OBJETIVO")
    D.titulo(s, "Meta e indicador")
    D.texto(s, 0.75, 2.3, 6.2, 0.35, [[("Indicador", dict(s=15, b=True, c=P["a1"], sp=100))]])
    D.texto(s, 0.75, 2.7, 6.3, 0.9, [[D.b("¿El cliente tiene la señal en riesgo? Sí o no", s=17)],
                                     [D.g("sin mirar su propia señal: solo lo que se sabe antes de medirla", s=15)]])
    metas = [(f"ROC-AUC ≥ {c(s_['metas']['ROC_AUC_prueba'])}", "de 100 pares (uno en riesgo y uno sano), ordenar bien al menos 68"),
             (f"PR-AUC ≥ {c(s_['metas']['PR_AUC_prueba'])}", f"el doble que el azar ({c(pr['Dummy (prior)']['PR_AUC'])}) al buscar a los clientes en riesgo")]
    for i, (num, txt) in enumerate(metas):
        y = 3.95 + i * 1.15
        D.caja(s, 0.75, y, 6.3, 0.95)
        D.texto(s, 0.95, y, 2.6, 0.95, [[(num, dict(f=TITULAR, s=20, b=True, c=P["a1"]))]], anclaje=MSO_ANCHOR.MIDDLE)
        D.texto(s, 3.65, y, 3.25, 0.95, [[D.g(txt, s=14)]], anclaje=MSO_ANCHOR.MIDDLE)
    D.texto(s, 7.6, 2.3, 5, 0.35, [[("Objetivo SMART", dict(s=15, b=True, c=P["a1"], sp=100))]])
    D.smart(s, 7.6, 2.8, [("S", "Específico", f"{miles(d['equipos'])} clientes online"),
                          ("M", "Medible", "ROC-AUC y PR-AUC en prueba"),
                          ("A", "Alcanzable", "con datos de la red y del inventario"),
                          ("R", "Relevante", "elegir el puerto de cada alta nueva"),
                          ("T", "Temporal", "modelo e informe para la entrega del TP3")], ancho=4.7)
    D.notas(s, f"IDEA CENTRAL: no medimos 'cuánto acierta' sino si sabe ordenar a los clientes por riesgo. (≈ 40 s)\n\n\"Con tan pocos "
               f"clientes en riesgo, el porcentaje de aciertos no sirve. Por eso usamos dos medidas que miran si el modelo sabe ORDENAR a "
               f"los clientes.\n\nLa primera: si tomamos un cliente en riesgo y uno sano, ¿cuál marca como más riesgoso? Queremos que acierte "
               f"en al menos 68 de cada 100 pares. La segunda mide qué tan bien encuentra a los pocos en riesgo: tiene que ser al menos "
               f"el doble que tirar una moneda.\"\n\nPASE: \"¿Y cómo nos aseguramos de no hacer trampa?\"")

    # 5. Método: grilla de puertos
    s = D.nueva()
    D.pildora(s, "03 · MÉTODO")
    D.titulo(s, "Un puerto entero va a un solo lado")
    import tp3_clasificacion as t3
    dd = t3.cargar_datos()
    _, te = t3.particion(dd)
    pons_prueba = set(te["pon_key"])
    todos = sorted(dd["pon_key"].unique())
    cols, lado = 25, 0.27
    for i, pk in enumerate(todos):
        f_, c_ = divmod(i, cols)
        D.forma(s, MSO_SHAPE.RECTANGLE, 0.75 + c_ * (lado + 0.05), 2.45 + f_ * (lado + 0.05), lado, lado,
                P["a1"] if pk in pons_prueba else P["linea"])
    D.texto(s, 0.75, 6.4, 8.0, 0.35, [[D.g("Cada cuadrado es un puerto PON con todos sus clientes. ", s=13),
                                       ("■ ", dict(s=13, c=P["a1"])), D.g("prueba", s=13)]])
    D.texto(s, 9.3, 2.45, 3.5, 4.0, [[D.b(f"{miles(d['entrenamiento'])} clientes", s=18)], [D.g(f"de {d['pon_entrenamiento']} puertos para aprender", s=15)],
                                      [D.a(f"{miles(d['prueba'])} clientes", s=18)], [D.g(f"de {d['pon_prueba']} puertos de prueba", s=15)],
                                      [D.a("Prohibido: ", n=2, s=15), D.g("la señal, el estado y el nivel del propio cliente.", s=15)]], espacio=8)
    D.notas(s, f"IDEA CENTRAL: los clientes de un mismo puerto comparten la fibra, así que nunca los repartimos entre aprender y "
               f"probar. (≈ 45 s)\n\n\"Cada cuadradito es un puerto con todos sus clientes. Los de color son la prueba: "
               f"{d['pon_prueba']} puertos, {miles(d['prueba'])} clientes.\n\n¿Por qué separar puertos enteros y no clientes sueltos? "
               f"Porque los vecinos comparten la misma fibra. Si un vecino está en el grupo de aprender y el otro en la prueba, el modelo "
               f"ya 'vio' esa fibra: sería hacer trampa.\n\nY obviamente, la señal del propio cliente no entra: es justo lo que queremos "
               f"adivinar.\"\n\nPASE: \"Primer hallazgo: cuidado con los aciertos.\"\n\n"
               f"SI PREGUNTAN \"¿qué variables usa?\": localidad, modelo de equipo, Wi-Fi, puertos LAN, posición en el puerto, cantidad "
               f"de vecinos, firmware, distancia y la señal media de los vecinos.")

    # 6. Hallazgo: la exactitud engaña (108 puntos)
    s = D.nueva()
    D.pildora(s, "04 · HALLAZGO")
    D.titulo(s, "Acertar mucho no es detectar")
    en_riesgo = tp + fn
    for k, (nombre, acc, detect) in enumerate([("Decir siempre \"sin riesgo\"", pr["Dummy (prior)"]["accuracy"], 0),
                                               (f"Regresión logística", pr[mejor]["accuracy"], tp)]):
        x = 0.75 + k * 6.2
        D.texto(s, x, 2.3, 5.8, 0.4, [[D.b(nombre, s=17)]])
        D.texto(s, x, 2.8, 2.9, 0.9, [[(f"{c(acc * 100, 0)} %", dict(f=TITULAR, s=32, b=True, c=P["gris"]))], [D.g("de aciertos", s=13)]])
        D.texto(s, x + 2.9, 2.8, 2.9, 0.9, [[(f"{detect} de {en_riesgo}", dict(f=TITULAR, s=32, b=True, c=P["a1"] if detect else P["a2"]))],
                                            [D.g("clientes en riesgo detectados", s=13)]])
        for i in range(en_riesgo):
            f_, c_ = divmod(i, 18)
            D.circulo(s, x + 0.12 + c_ * 0.31, 4.35 + f_ * 0.31, 0.22, P["a1"] if i < detect else P["linea"])
    D.texto(s, 0.75, 6.4, 11.8, 0.35, [[D.g(f"Cada punto es uno de los {en_riesgo} clientes en riesgo de la prueba. ", s=13),
                                        ("● ", dict(s=13, c=P["a1"])), D.g("detectado", s=13)]])
    D.notas(s, f"IDEA CENTRAL: el porcentaje de aciertos engaña; lo que importa es cuántos clientes en riesgo encuentra. (≈ 45 s)\n\n"
               f"\"Les presento al peor modelo del mundo [señalar la izquierda]: dice siempre 'sin riesgo'. ¿Cuánto acierta? "
               f"{c(pr['Dummy (prior)']['accuracy'] * 100, 0)} %. Impresionante, ¿no? Pero miren los puntos: de los {en_riesgo} clientes "
               f"en riesgo, no encuentra a ninguno.\n\nNuestro modelo [señalar la derecha] acierta menos en total, "
               f"{c(pr[mejor]['accuracy'] * 100, 0)} %, pero encuentra a {tp} de los {en_riesgo}. Por eso no elegimos modelos por "
               f"porcentaje de aciertos.\"\n\nPASE: \"Entonces, ¿cumplimos la meta?\"")

    # 7. Resultado
    s = D.nueva()
    D.pildora(s, "05 · RESULTADO")
    D.titulo(s, "La regresión logística cumple")
    D.bala(s, 0.75, 3.0, 7.3, pr[mejor]["ROC_AUC"], s_["metas"]["ROC_AUC_prueba"], 0.4, 1.0, "ROC-AUC en prueba: ordenar por riesgo",
           c(pr[mejor]["ROC_AUC"]), f"meta {c(s_['metas']['ROC_AUC_prueba'])}", extra=(0.5, "azar 0,50"))
    D.bala(s, 0.75, 4.75, 7.3, pr[mejor]["PR_AUC"], s_["metas"]["PR_AUC_prueba"], 0, 0.6, "PR-AUC en prueba: encontrar a los pocos",
           c(pr[mejor]["PR_AUC"]), f"meta {c(s_['metas']['PR_AUC_prueba'])}", extra=(pr["Dummy (prior)"]["PR_AUC"], f"azar {c(pr['Dummy (prior)']['PR_AUC'])}"))
    D.texto(s, 9.0, 2.5, 3.8, 3.9, [[(f"{tp} detectados", dict(f=TITULAR, s=28, b=True, c=P["a1"]))],
                                     [(f"{fp} falsas alarmas", dict(f=TITULAR, s=28, b=True, c=P["gris"]))],
                                     [D.g(f"De cada 4 clientes que marca, 1 está realmente en riesgo. La ROC-AUC quedó justa: "
                                          f"{c(pr[mejor]['ROC_AUC'], 3)} contra {c(s_['metas']['ROC_AUC_prueba'])}.", s=15)]], espacio=10)
    D.notas(s, f"IDEA CENTRAL: la regresión logística, el modelo más simple, cumple las dos metas. (≈ 45 s)\n\n\"La barra verde es lo "
               f"que logró y la marca rosa, la meta. Ordena bien a {c(pr[mejor]['ROC_AUC'] * 100, 0)} de cada 100 pares de clientes, "
               f"contra una meta de 68. Y para encontrar a los pocos en riesgo, saca {c(pr[mejor]['PR_AUC'])}, casi cuatro veces el azar.\n\n"
               f"En la práctica: encuentra a {tp} clientes en riesgo y da {fp} falsas alarmas. O sea, de cada 4 que marca, uno está "
               f"realmente en riesgo. Y lo decimos de frente: la ROC-AUC quedó justa, apenas arriba de la meta.\"\n\n"
               f"PASE: \"¿Y qué es lo que mira para acertar? Esto es lo más interesante.\"\n\n"
               f"SI PREGUNTAN \"¿por qué la regresión logística?\": tiene la mejor PR-AUC en validación cruzada entre los cuatro "
               f"clasificadores individuales, y no memoriza.")

    # 8. Comprensión: duelo modelo contra regla de los vecinos
    s = D.nueva()
    D.pildora(s, "06 · COMPRENSIÓN", P["a2"])
    D.titulo(s, "Una regla sin ML rinde igual")
    duelos = [("ROC-AUC", pr[mejor]["ROC_AUC"], vec["ROC_AUC"], 1.0), ("PR-AUC", pr[mejor]["PR_AUC"], vec["PR_AUC"], 0.6)]
    D.texto(s, 0.75, 2.25, 8.0, 0.4, [[("■ ", dict(s=15, c=P["a1"])), D.g("Modelo (13 variables)      ", s=15),
                                       ("■ ", dict(s=15, c=P["a2"])), D.g("Regla: mirar la señal de los vecinos", s=15)]])
    for k, (nombre, vm, vr, tope) in enumerate(duelos):
        y = 3.05 + k * 1.75
        D.texto(s, 0.75, y, 1.6, 1.0, [[D.b(nombre, s=16)]], anclaje=MSO_ANCHOR.MIDDLE)
        for j, (v, col) in enumerate([(vm, P["a1"]), (vr, P["a2"])]):
            w = 5.6 * v / tope
            D.forma(s, MSO_SHAPE.RECTANGLE, 2.45, y + j * 0.52, w, 0.42, col)
            D.texto(s, 2.45 + w + 0.12, y + j * 0.52, 1.0, 0.42, [[(c(v), dict(f=TITULAR, s=16, b=True, c=col))]], anclaje=MSO_ANCHOR.MIDDLE)
    D.caja(s, 9.4, 2.4, 3.45, 3.9)
    D.texto(s, 9.65, 2.6, 3.0, 3.6, [[("Insight", dict(s=15, b=True, c=P["a2"]))],
                                      [D.g("Si al modelo le escondemos la señal de los vecinos, pierde ", s=14),
                                       D.b(c(imp["vec_rxp"], 3), s=14), D.g(" de PR-AUC. Cualquier otra variable: casi 0.", s=14)],
                                      [D.b("El riesgo está en la fibra que comparten, no en el módem.", s=14)]], espacio=8)
    D.notas(s, f"IDEA CENTRAL: la señal de los vecinos lo explica casi todo; el modelo de módem y el firmware no importan. (≈ 50 s)\n\n"
               f"\"Hicimos una prueba muy simple, sin inteligencia artificial: ordenar a los clientes según qué tan débil les llega la "
               f"señal a sus vecinos de puerto. [señalar barras rosas] Rinde igual que el modelo: {c(vec['ROC_AUC'])} contra "
               f"{c(pr[mejor]['ROC_AUC'])}.\n\nY si al modelo le escondemos esa información, pierde casi todo. Si le escondemos el modelo de "
               f"módem, el firmware o la distancia, no pasa nada.\n\n¿Por qué? Porque la señal depende de la fibra, los empalmes y el "
               f"divisor que comparten todos los vecinos. Si a ellos les llega débil, a vos también. Para la empresa: antes de conectar "
               f"a un cliente nuevo, miren cómo les llega la señal a los vecinos de ese puerto.\"\n\n"
               f"PASE: \"Ahora, el plus: ¿modelos más potentes ayudan?\"\n\n"
               f"SI PREGUNTAN \"si una regla rinde igual, ¿para qué el modelo?\": el modelo sirvió para DEMOSTRAR que nada más agrega "
               f"información. Ese es el hallazgo.")

    # 9. Plus ensamble: pesas
    s = D.nueva()
    D.pildora(s, "07 · PLUS: ENSAMBLE", P["a2"])
    D.titulo(s, "Más complejo no es mejor")
    orden = ["Regresión Logística", "Naive Bayes", "Árbol de Decisión", "Gradient Boosting", "Random Forest", "KNN"]
    nomb = {"Regresión Logística": "Regresión logística", "Árbol de Decisión": "Árbol de decisión"}
    filas = [(nomb.get(n, n), en[n]["ROC_AUC"], cv[n]["ROC_AUC"]) for n in orden]
    D.texto(s, 3.75, 2.15, 6.5, 0.35, [[("●", dict(s=16, c=P["a2"])), D.g("  con clientes que ya vio      ", s=14),
                                        ("●", dict(s=16, c=P["a1"])), D.g("  con puertos nuevos", s=14)]])
    D.pesas(s, filas, 0.75, 2.85, 5.4, 0.62, 0.6, 1.0, [0.6, 0.7, 0.8, 0.9, 1.0], resaltar="Regresión logística")
    D.texto(s, 0.75, 6.8, 9.4, 0.3, [[D.g("ROC-AUC: de 100 pares (uno en riesgo y uno sano), cuántos ordena bien", s=12)]], align=PP_ALIGN.CENTER)
    seg = t["segundos_busqueda"]
    D.texto(s, 10.6, 2.5, 2.3, 4.0, [[(f"{c(seg['Random Forest'], 0)} s", dict(f=TITULAR, s=34, b=True, c=P["a1"]))],
                                      [D.g(f"tarda el Random Forest en ajustarse; la regresión logística, {c(seg[mejor], 0)} s.", s=14)],
                                      [D.b("Los ensambles memorizan y no superan al modelo simple.", s=14)]], espacio=10)
    D.notas(s, f"IDEA CENTRAL: juntar cientos de árboles no mejora y encima memoriza. (≈ 45 s)\n\n\"Como plus probamos dos ensambles: "
               f"Random Forest, que son 300 árboles votando, y Gradient Boosting. Es el mismo tipo de gráfico que en el TP2: punto rosa, "
               f"clientes que ya vio; punto verde, puertos nuevos.\n\nEl caso extremo es KNN, que con lo que ya vio acierta {c(en['KNN']['ROC_AUC'])}: se "
               f"reconoce a sí mismo. El Random Forest pasa de {c(en['Random Forest']['ROC_AUC'])} a {c(cv['Random Forest']['ROC_AUC'])}. "
               f"La regresión logística casi no cae.\n\nY encima los ensambles tardan mucho más. No valen la pena.\"\n\n"
               f"PASE: \"El último plus: dejar que la computadora arme grupos sola.\"\n\n"
               f"SI PREGUNTAN \"¿el Random Forest no tenía mejor PR-AUC?\": en validación cruzada sí, por 0,02, pero varía ± 0,15 entre "
               f"particiones (es ruido), memoriza, y en prueba no llega a la meta de ROC-AUC ({c(pr['Random Forest']['ROC_AUC'], 3)}).")

    # 10. Plus clustering: burbujas
    s = D.nueva()
    D.pildora(s, "08 · PLUS: CLUSTERING", P["a2"])
    D.titulo(s, "Un grupo lejano con el triple de riesgo")
    # un círculo por grupo, de más cerca a más lejos de la central; el área es la cantidad de clientes
    grupos = sorted(pe.items(), key=lambda kv: kv[1]["distancia_mediana_m"])
    top_g = max(pe, key=lambda k: pe[k]["pct_en_riesgo"])
    n_max = max(v["equipos"] for _, v in grupos)
    for i, (g, v) in enumerate(grupos):
        cx = 0.75 + 2.0 * i + 1.0
        fuerte = g == top_g
        col = P["a2"] if fuerte else P["gris2"]
        D.circulo(s, cx, 3.55, 2.0 * np.sqrt(v["equipos"] / n_max), col)
        D.texto(s, cx - 1.0, 4.75, 2.0, 0.6, [[(f"{c(v['pct_en_riesgo'] * 100, 1)} %", dict(f=TITULAR, s=28, b=True,
                                                                                          c=P["a2"] if fuerte else P["texto"]))]],
                align=PP_ALIGN.CENTER)
        D.texto(s, cx - 1.0, 5.35, 2.0, 0.3, [[D.g("en riesgo", s=13)]], align=PP_ALIGN.CENTER)
        D.texto(s, cx - 1.0, 5.75, 2.0, 0.6, [[(f"{miles(v['equipos'])} clientes", dict(s=13, b=fuerte, c=P["texto"] if fuerte else P["gris"]))],
                                               [D.g(f"a {c(v['distancia_mediana_m'] / 1000, 1)} km", s=13)]], align=PP_ALIGN.CENTER, espacio=0)
    D.linea(s, 0.9, 6.55, 8.6, 6.55, P["linea"], 1)
    D.texto(s, 0.75, 6.6, 8.0, 0.3, [[D.g("más cerca de la central  →  más lejos", s=12)]], align=PP_ALIGN.CENTER)
    gt = pe[top_g]
    otros = [pe[k]["pct_en_riesgo"] for k in pe if k != top_g]
    D.texto(s, 9.3, 2.5, 3.55, 4.0, [[D.g("K-Means armó 4 grupos sin saber quién está en riesgo.", s=15)],
                                      [D.b(f"{miles(gt['equipos'])} clientes lejanos ", s=15),
                                       D.g(f"({c(gt['distancia_mediana_m'] / 1000, 1)} km): {c(gt['pct_en_riesgo'] * 100, 1)} % en riesgo, "
                                           f"contra {c(min(otros) * 100, 1)} a {c(max(otros) * 100, 1)} % en los demás.", s=15)],
                                      [D.a(f"La mitad está en {gt['localidad_principal']}.", n=2, s=15)]], espacio=10)
    D.notas(s, f"IDEA CENTRAL: sin darle la respuesta, la computadora encontró un grupo de clientes lejanos con el triple de riesgo. "
               f"(≈ 45 s)\n\n\"Le pedimos al algoritmo que arme grupos de clientes parecidos, sin decirle quién está en riesgo. Cada círculo "
               f"es un grupo, ordenados de más cerca a más lejos de la central; el tamaño es cuántos clientes tiene y abajo está qué "
               f"porcentaje queda en riesgo.\n\nUno se despega [señalar el rosa]: {miles(gt['equipos'])} clientes a {c(gt['distancia_mediana_m'] / 1000, 1)} km de "
               f"mediana, con {c(gt['pct_en_riesgo'] * 100, 1)} % en riesgo. Casi el triple que los demás. La mitad está en "
               f"{gt['localidad_principal']}.\n\nPara la empresa, eso dice dónde empezar el mantenimiento preventivo.\"\n\n"
               f"PASE: \"Cerramos.\"\n\n"
               f"SI PREGUNTAN \"¿los grupos coinciden con 'en riesgo / sin riesgo'?\": no. El mejor número de grupos es "
               f"{cl['k_mejor']} y casi no coincide con la clase (índice {c(cl['ARI'][str(cl['k_mejor'])])} de 0 a 1). Lo valioso es el "
               f"grupo de tendidos largos que aparece con 4.")

    # 11. Cierre
    D.cierre([("Se puede anticipar.", f"Sin medir su señal, la regresión logística ordena por riesgo (ROC-AUC {c(pr[mejor]['ROC_AUC'])}, "
                                      f"PR-AUC {c(pr[mejor]['PR_AUC'])}) y cumple la meta."),
              ("La clave son los vecinos.", f"Una regla sin ML que mira su señal rinde igual ({c(vec['ROC_AUC'])}): el problema está en la "
                                            f"fibra, no en el módem."),
              ("Dónde actuar.", f"Altas nuevas: mirar la señal del puerto. Mantenimiento: empezar por los {miles(gt['equipos'])} clientes "
                                f"de tendidos largos.")],
             f"IDEA CENTRAL: se puede anticipar quién queda al límite, y lo que manda es la fibra compartida. (≈ 40 s)\n\n\"Tres ideas. "
             f"Uno: sin medir la señal de un cliente, podemos saber si va a quedar al límite, y cumplimos la meta. Dos: la clave son los "
             f"vecinos; una regla simple que mira su señal rinde igual que el modelo. El problema está en la fibra, no en el módem. Y "
             f"tres: para la empresa, antes de conectar a un cliente nuevo, conviene mirar la señal de ese puerto, y el mantenimiento "
             f"preventivo puede empezar por los tendidos largos.\n\n¿Preguntas?\"")

    # ---------------------------------------------------------------- respaldo
    D.separador()
    s = D.nueva()
    D.pildora(s, "R1 · RESPALDO")
    D.titulo(s, "Métricas en prueba")
    mods = ["Regresión Logística", "Árbol de Decisión", "KNN", "Naive Bayes", "Random Forest", "Gradient Boosting", "Dummy (prior)"]
    nom = {"Regresión Logística": "Regresión logística", "Árbol de Decisión": "Árbol de decisión", "Dummy (prior)": "Decir siempre 'sin riesgo'"}
    filas = [["Modelo", "Exactitud", "Recall", "Precisión", "F1", "Kappa", "ROC-AUC", "PR-AUC"]]
    for n in mods:
        x = pr[n]
        filas.append([nom.get(n, n), c(x["accuracy"]), c(x["recall"]), c(x["precision"]), c(x["F1"]), c(x["kappa"]), c(x["ROC_AUC"]), c(x["PR_AUC"])])
    filas.append(["Regla de los vecinos", "—", "—", "—", "—", "—", c(vec["ROC_AUC"]), c(vec["PR_AUC"])])
    D.tabla(s, filas, 0.75, 2.25, [3.3, 1.2, 1.1, 1.2, 1.0, 1.0, 1.5, 1.4], resaltar=[1], alto=0.45)
    D.notas(s, "Respaldo. La fila resaltada es el modelo elegido. KNN, Naive Bayes y Gradient Boosting usan un umbral elegido en "
               "validación cruzada; el resto, 0,5.")

    s = D.nueva()
    D.pildora(s, "R2 · RESPALDO")
    D.titulo(s, "Matrices de confusión")
    for k, n in enumerate(["Regresión Logística", "Árbol de Decisión", "KNN", "Naive Bayes"]):
        (a_, b_), (c_, d_) = t["matrices_confusion_prueba"][n]
        x = 0.75 + k * 3.1
        D.texto(s, x, 2.3, 2.9, 0.4, [[D.b(nom.get(n, n), s=15)]], align=PP_ALIGN.CENTER)
        celdas = [(a_, "sin riesgo,\nbien", P["tarjeta"], P["gris"]), (b_, "falsas\nalarmas", P["tarjeta"], P["gris"]),
                  (c_, "en riesgo\nperdidos", P["a2_suave"], P["texto"]), (d_, "en riesgo\ndetectados", P["a1_suave"], P["texto"])]
        for idx, (val, lab, fondo, col) in enumerate(celdas):
            f_, cc = divmod(idx, 2)
            xx, yy = x + cc * 1.45, 2.85 + f_ * 1.45
            D.caja(s, xx, yy, 1.4, 1.4, relleno=fondo)
            D.texto(s, xx, yy + 0.15, 1.4, 0.6, [[(str(val), dict(f=TITULAR, s=24, b=True, c=col))]], align=PP_ALIGN.CENTER)
            D.texto(s, xx, yy + 0.75, 1.4, 0.6, [[D.g(lab, s=11)]], align=PP_ALIGN.CENTER)
    D.texto(s, 0.75, 6.0, 11.8, 0.6, [[D.g(f"Prueba: {miles(d['prueba'])} clientes. Fila de arriba: realmente sin riesgo; fila de abajo: "
                                           f"realmente en riesgo.", s=14)]])
    D.notas(s, "Respaldo (consigna: matriz de confusión de cada modelo). Los que más detectan son los que más falsas alarmas dan.")

    s = D.nueva()
    D.pildora(s, "R3 · RESPALDO")
    D.titulo(s, "Detectar más cuesta alarmas")
    u = t["umbral_decision"]["comparacion_prueba"]
    mc = t["umbral_decision"]["matrices_confusion_prueba"]
    k_bajo = next(k for k in u if k.startswith("recall"))
    escenarios = [("Umbral habitual (0,5)", u["0,5 (por defecto)"], mc["0,5 (por defecto)"]),
                  ("Umbral bajo (elegido para detectar el 80 % en validación)", u[k_bajo], mc[k_bajo])]
    for k, (nombre, e, mat) in enumerate(escenarios):
        y = 2.7 + k * 1.75
        reales, falsas = mat[1][1], mat[0][1]   # de la matriz de confusión de prueba: detectados y falsas alarmas
        esc_ = 11.8 / d["prueba"]
        D.texto(s, 0.75, y - 0.45, 11, 0.4, [[D.b(nombre + ": ", s=16), D.g(f"marca {e['marcados']} de {miles(d['prueba'])} clientes", s=16)]])
        D.forma(s, MSO_SHAPE.RECTANGLE, 0.75, y, reales * esc_, 0.6, P["a1"])
        D.forma(s, MSO_SHAPE.RECTANGLE, 0.75 + reales * esc_, y, falsas * esc_, 0.6, P["gris2"])
        D.texto(s, 0.85, y + 0.65, 9, 0.4, [[D.a(f"{reales} de {en_riesgo} en riesgo detectados", s=14),
                                             D.g(f"   ·   {falsas} falsas alarmas", s=14)]])
    D.notas(s, "Respaldo (cuestionario, pregunta 1: recall contra precisión). Bajar el umbral para detectar a 8 de cada 10 (en prueba fueron "
               f"{mc[k_bajo][1][1]} de {en_riesgo}) obliga a revisar más de la mitad de los clientes de la prueba. Es una decisión de negocio: cuánto cuesta un reclamo contra una visita técnica.")

    s = D.nueva()
    D.pildora(s, "R4 · RESPALDO")
    D.titulo(s, "Sin fuga de información")
    tarjetas = [("Entra", "Ubicación, modelo, Wi-Fi, puertos LAN, firmware, distancia y la señal media de los vecinos (sin el propio cliente)."),
                ("No entra", "La señal recibida y transmitida, el estado y el nivel de señal del propio cliente: son la respuesta."),
                ("0 puertos", "compartidos entre aprender y probar: los vecinos de fibra siempre quedan del mismo lado.")]
    for i, (tit, txt) in enumerate(tarjetas):
        x = 0.75 + i * 4.05
        D.caja(s, x, 2.4, 3.75, 3.6)
        D.texto(s, x + 0.25, 2.6, 3.3, 0.8, [[(tit, dict(f=TITULAR, s=30, b=True, c=P["a1"] if i != 1 else P["a2"]))]])
        D.texto(s, x + 0.25, 3.5, 3.3, 2.4, [[D.g(txt, s=15)]])
    D.notas(s, "Respaldo. La pregunta del TP3 nació de la fuga de datos del TP1 (respaldo R3 de esa presentación): acá se evita a "
               "propósito. La señal de los vecinos sí vale porque ya está medida cuando se instala un cliente nuevo.")
    return D.guardar("TP3_presentacion.pptx")


def main():
    m = json.loads(METRICS.read_text(encoding="utf-8"))
    for f in (presentacion_tp2(m), presentacion_tp3(m)):
        print("PPTX:", f.relative_to(RAIZ))


if __name__ == "__main__":
    main()
