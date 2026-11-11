"""Informes del TP2 y del TP3 en PDF, con formato de artículo IEEE en una columna.
Todas las cifras salen de results/metrics.json; las figuras, de src/informes_figuras.py.

Para poner los nombres del grupo, editar AUTORES y volver a correr:  python src/informes_pdf.py"""
import json
import re
import sys
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import METRICS, RAIZ  # noqa: E402

AUTORES = ["Juan Ignacio Forzani", "Alejo Racca", "Agustín Cesano"]   # completar con los integrantes del grupo
AFILIACION = "Ingeniería en Computación, Universidad Nacional de Rafaela (UNRaf), Rafaela, Santa Fe, Argentina"
MATERIA = "Aprendizaje Automático y Grandes Datos · UNRaf · 2026"
SALIDA = RAIZ / "informes y presentaciones"

# ------------------------------------------------------------------ tipografía y estilos (IEEE: Times, una columna)
FUENTES = Path("C:/Windows/Fonts")
for nombre, archivo in [("TNR", "times.ttf"), ("TNR-B", "timesbd.ttf"), ("TNR-I", "timesi.ttf"), ("TNR-BI", "timesbi.ttf")]:
    pdfmetrics.registerFont(TTFont(nombre, str(FUENTES / archivo)))
pdfmetrics.registerFontFamily("TNR", normal="TNR", bold="TNR-B", italic="TNR-I", boldItalic="TNR-BI")

TINTA, GRIS, AZUL, RESALTE = colors.HexColor("#111111"), colors.HexColor("#6b6a66"), colors.HexColor("#1f5fa8"), colors.HexColor("#eaf1fa")
E = {
    "titulo": ParagraphStyle("titulo", fontName="TNR", fontSize=20, leading=24, alignment=TA_CENTER, textColor=TINTA, spaceAfter=10),
    "autores": ParagraphStyle("autores", fontName="TNR", fontSize=11, leading=14, alignment=TA_CENTER),
    "afil": ParagraphStyle("afil", fontName="TNR-I", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=GRIS, spaceAfter=14),
    "resumen": ParagraphStyle("resumen", fontName="TNR-B", fontSize=9, leading=11.2, alignment=TA_JUSTIFY, spaceAfter=5),
    "cuerpo": ParagraphStyle("cuerpo", fontName="TNR", fontSize=10.5, leading=13.4, alignment=TA_JUSTIFY, firstLineIndent=14, spaceAfter=3),
    "h1": ParagraphStyle("h1", fontName="TNR", fontSize=10.5, leading=13, alignment=TA_CENTER, spaceBefore=9, spaceAfter=5, textColor=TINTA),
    "h2": ParagraphStyle("h2", fontName="TNR-I", fontSize=10.5, leading=13, alignment=TA_LEFT, spaceBefore=5, spaceAfter=2),
    "pie_fig": ParagraphStyle("pie_fig", fontName="TNR", fontSize=8.5, leading=10.4, alignment=TA_JUSTIFY, spaceBefore=2, spaceAfter=8),
    "tab_num": ParagraphStyle("tab_num", fontName="TNR", fontSize=8.5, leading=10, alignment=TA_CENTER, spaceBefore=6),
    "tab_tit": ParagraphStyle("tab_tit", fontName="TNR", fontSize=8.5, leading=10.4, alignment=TA_CENTER, spaceAfter=3),
    "celda": ParagraphStyle("celda", fontName="TNR", fontSize=8.5, leading=10, alignment=TA_CENTER),
    "celda_izq": ParagraphStyle("celda_izq", fontName="TNR", fontSize=8.5, leading=10, alignment=TA_LEFT),
    "nota_tab": ParagraphStyle("nota_tab", fontName="TNR", fontSize=7.8, leading=9.4, alignment=TA_LEFT, spaceBefore=2, spaceAfter=8, textColor=GRIS),
    "ecuacion": ParagraphStyle("ecuacion", fontName="TNR", fontSize=10.5, leading=14, alignment=TA_CENTER),
    "ref": ParagraphStyle("ref", fontName="TNR", fontSize=8.5, leading=10.4, alignment=TA_LEFT, leftIndent=20, firstLineIndent=-20, spaceAfter=2),
}
ROMANOS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def versalitas(texto, tam=10.5):
    """Imita las versalitas de IEEE: inicial a tamaño normal, resto en mayúsculas más chicas."""
    chico = tam * 0.8
    return " ".join(f"{w[0].upper()}<font size={chico}>{w[1:].upper()}</font>" if w else w for w in texto.split(" "))


def c(x, d=2):
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def hiper(texto):
    """"{'max_depth': 8, 'learning_rate': 0.05}" -> "max_depth = 8, learning_rate = 0,05" (coma decimal)."""
    t = texto.strip("{}").replace(chr(39), "").replace(":", " =")
    return re.sub(r"(\d)\.(\d)", r"\1,\2", t)


def pct(x, d=1):
    return f"{x * 100:.{d}f}".replace(".", ",")


class Informe:
    """Arma el flujo del artículo: numera secciones, figuras, tablas y ecuaciones al estilo IEEE."""

    def __init__(self, tp, titulo):
        self.tp, self.titulo, self.flujo = tp, titulo, []
        self.n_sec = self.n_sub = self.n_fig = self.n_tab = self.n_eq = 0
        self.titulos_pendientes = []   # títulos que tienen que quedar en la misma página que lo que sigue

    @staticmethod
    def _plano(f):
        """Contenido de un grupo (KeepTogether) como lista: reportlab mide mal los grupos anidados."""
        return list(f._content) if isinstance(f, KeepTogether) else [f]

    def _agregar(self, f):
        if self.titulos_pendientes:
            f = KeepTogether(self.titulos_pendientes + self._plano(f))
            self.titulos_pendientes = []
        self.flujo.append(f)

    def encabezado(self, resumen, palabras):
        self.flujo += [Paragraph(self.titulo, E["titulo"]), Paragraph(", ".join(AUTORES), E["autores"]),
                       Paragraph(AFILIACION, E["afil"]),
                       Paragraph(f"<i>Resumen</i>—{resumen}", E["resumen"]),
                       Paragraph(f"<i>Palabras clave</i>—{palabras}", E["resumen"]), Spacer(1, 4)]

    def seccion(self, titulo):
        self.n_sub = 0
        rom = ROMANOS[self.n_sec]
        self.n_sec += 1
        self.titulos_pendientes.append(Paragraph(f"{rom}. {versalitas(titulo)}", E["h1"]))

    def subseccion(self, titulo):
        letra = "ABCDEFGH"[self.n_sub]
        self.n_sub += 1
        self.titulos_pendientes.append(Paragraph(f"{letra}. {titulo}", E["h2"]))

    def p(self, texto):
        self._agregar(Paragraph(texto, E["cuerpo"]))

    def ecuacion(self, formula):
        self.n_eq += 1
        t = Table([[Paragraph(formula, E["ecuacion"]), Paragraph(f"({self.n_eq})", E["ecuacion"])]], colWidths=[14.8 * cm, 1.8 * cm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        previo = self.flujo.pop()   # la ecuación no se separa de la frase que la presenta
        self.flujo.append(KeepTogether(self._plano(previo) + [t]))
        return self.n_eq

    def figura(self, ruta, pie, ancho=16.4 * cm):
        self.n_fig += 1
        w, h = PILImage.open(ruta).size
        img = Image(str(ruta), width=ancho, height=ancho * h / w)
        self._agregar(KeepTogether([Spacer(1, 4), img, Paragraph(f"Fig. {self.n_fig}. {pie}", E["pie_fig"])]))
        return self.n_fig

    def tabla(self, titulo, filas, anchos, resaltar=None, nota=None, izq=(0,)):
        """filas[0] = encabezado. Formato IEEE: filetes arriba, bajo el encabezado y abajo; sin rejilla."""
        self.n_tab += 1
        datos = [[Paragraph(f"<b>{x}</b>" if i == 0 else str(x), E["celda_izq"] if j in izq else E["celda"])
                  for j, x in enumerate(fila)] for i, fila in enumerate(filas)]
        t = Table(datos, colWidths=anchos, repeatRows=1)
        estilo = [("LINEABOVE", (0, 0), (-1, 0), 0.9, TINTA), ("LINEBELOW", (0, 0), (-1, 0), 0.5, TINTA),
                  ("LINEBELOW", (0, -1), (-1, -1), 0.9, TINTA), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                  ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]
        for r in (resaltar or []):
            estilo.append(("BACKGROUND", (0, r), (-1, r), RESALTE))
        t.setStyle(TableStyle(estilo))
        bloque = [Paragraph(f"TABLA {ROMANOS[self.n_tab - 1]}", E["tab_num"]), Paragraph(versalitas(titulo, 8.5), E["tab_tit"]), t]
        if nota:
            bloque.append(Paragraph(nota, E["nota_tab"]))
        else:
            bloque.append(Spacer(1, 6))
        self._agregar(KeepTogether(bloque))
        return ROMANOS[self.n_tab - 1]

    def referencias(self, refs):
        self.titulos_pendientes.append(Paragraph(versalitas("Referencias"), E["h1"]))
        for i, r in enumerate(refs, 1):
            self._agregar(Paragraph(f"[{i}]&nbsp;&nbsp;{r}", E["ref"]))

    def construir(self, archivo):
        SALIDA.mkdir(parents=True, exist_ok=True)
        doc = BaseDocTemplate(str(archivo), pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm, topMargin=2.2 * cm,
                              bottomMargin=2.0 * cm, title=self.titulo.replace("<br/>", " "), author=", ".join(AUTORES),
                              subject=f"{self.tp} — {MATERIA}")
        marco = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="texto", leftPadding=0, rightPadding=0)
        tp, materia = self.tp, MATERIA

        def decorar(canv, d):
            canv.saveState()
            canv.setFont("TNR", 8)
            canv.setFillColor(GRIS)
            if d.page > 1:
                canv.drawString(d.leftMargin, A4[1] - 1.35 * cm, tp)
                canv.drawRightString(A4[0] - d.rightMargin, A4[1] - 1.35 * cm, materia)
                canv.setStrokeColor(colors.HexColor("#c9c7c0")); canv.setLineWidth(0.4)
                canv.line(d.leftMargin, A4[1] - 1.5 * cm, A4[0] - d.rightMargin, A4[1] - 1.5 * cm)
            canv.setFillColor(TINTA)
            canv.drawCentredString(A4[0] / 2, 1.1 * cm, str(d.page))
            canv.restoreState()
        doc.addPageTemplates([PageTemplate(id="pagina", frames=[marco], onPage=decorar)])
        doc.build(self.flujo)
        return archivo


REFS_COMUNES = {
    "itu": "ITU-T, <i>Gigabit-capable passive optical networks (GPON): Physical media dependent (PMD) layer specification</i>, Rec. ITU-T G.984.2, Ginebra, Suiza, 2003 (Enmienda 1, 2006).",
    "sklearn": "F. Pedregosa <i>et al.</i>, “Scikit-learn: Machine learning in Python,” <i>J. Mach. Learn. Res.</i>, vol. 12, pp. 2825–2830, 2011.",
    "esl": "T. Hastie, R. Tibshirani y J. Friedman, <i>The Elements of Statistical Learning</i>, 2.ª ed. Nueva York, NY, EE. UU.: Springer, 2009.",
    "rf": "L. Breiman, “Random forests,” <i>Mach. Learn.</i>, vol. 45, n.º 1, pp. 5–32, 2001.",
    "gb": "J. H. Friedman, “Greedy function approximation: A gradient boosting machine,” <i>Ann. Statist.</i>, vol. 29, n.º 5, pp. 1189–1232, 2001.",
}


# ================================================================== TP2
def informe_tp2(m):
    t, o3 = m["obj09_tp2"], m["obj03"]
    mejor = t["mejor_modelo"]
    d, v, pr, cv, cvd, en = t["datos"], t["variables"], t["prueba"], t["cv_media"], t["cv_desvio"], t["entrenamiento"]
    s = t["criterio_smart"]
    olt = t["prueba_olt"]["resultados"]
    res, pat = t["residuos"], t["residuos"]["patrones"]
    gs = t["gridsearch_mejora"]
    sh = t["comparacion_5_vs_22_modelos"]
    k5, k22 = list(sh)
    cu = t["curva_aprendizaje"]
    n_onts = int(m["fase1_chequeos"]["detalle"]["Filas"]["obtenido"])
    hp = t["hiperparametros_elegidos"]
    shares = ", ".join(x.replace("share_", "") for x in v["shares_top5"])
    R = {k: i + 1 for i, k in enumerate(["itu", "sklearn", "ridge", "rf", "gb", "shapiro", "koenker", "esl"])}

    inf = Informe("TP2 — Regresión", "Predicción del porcentaje de ONTs con firmware<br/>fuera de estándar por puerto PON")
    inf.encabezado(
        f"Se estima, para cada uno de los {d['pon']} puertos PON de una red GPON de nueve localidades, la proporción de terminales "
        f"ópticos (ONT) cuyo firmware difiere de la versión más frecuente de su modelo. Se comparan una regresión lineal (línea base), "
        f"Ridge, Random Forest y Gradient Boosting contra un predictor constante, con una partición 80/20 y validación cruzada de cinco "
        f"particiones. {mejor} obtuvo el menor RMSE de validación cruzada ({c(cv[mejor]['RMSE'], 3)}) y, en prueba, R² = {c(pr[mejor]['R2'])}, "
        f"R² ajustado = {c(pr[mejor]['R2_ajustado'])} y MAE = {c(pr[mejor]['MAE'], 3)}, frente a {c(s['metas']['MAE_dummy_prueba'], 3)} del "
        f"predictor constante, con lo que cumple los tres criterios fijados. Los ensambles de árboles sobreajustan, el error es mayor en los "
        f"puertos con pocos equipos y agregar variables físicas de la OLT no mejora la predicción: el firmware fuera de estándar responde a "
        f"factores administrativos y de composición del parque, no al estado de la red.",
        "GPON, ONT, firmware, regresión, Ridge, validación cruzada, sesgo y varianza.")

    inf.seccion("Introducción")
    inf.p(f"Las redes de acceso GPON conectan a cada cliente mediante un terminal óptico (ONT) que depende de un puerto PON de la "
          f"terminal de línea (OLT) [{R['itu']}]. El firmware de las ONT condiciona su seguridad y sus funciones; en el inventario analizado, "
          f"el {c(o3['pct_fuera_estandar'], 1)} % de los {n_onts} equipos no tiene la versión más frecuente de su modelo. Actualizar equipo "
          f"por equipo es costoso, mientras que actualizar un puerto completo en una ventana de mantenimiento aprovecha mejor cada intervención.")
    inf.p("En el TP1 se observó que el modelo de ONT instalado depende fuertemente de la localidad. De ese hallazgo surge la pregunta de "
          "este trabajo: estimar, a partir de la composición de cada puerto, qué proporción de sus equipos está fuera del estándar, para "
          "priorizar los puertos donde una ventana de mantenimiento rinde más. Se comparan cuatro algoritmos de regresión bajo un marco "
          f"experimental controlado y se analiza su ajuste en términos de sesgo y varianza [{R['esl']}].")

    inf.seccion("Marco experimental")
    inf.subseccion("Datos y variable objetivo")
    inf.p(f"El inventario contiene {n_onts} ONT agregadas en {d['pon']} puertos PON. La variable objetivo es la proporción de equipos del "
          "puerto cuya versión de firmware difiere de la versión modal de su modelo. Esta definición de estándar es una regla de negocio "
          f"fija, calculada sobre todo el inventario. La variable tiene media {c(d['objetivo_media'])} y desvío {c(d['objetivo_desvio'])}; "
          f"{d['pon_con_0_pct']} puertos valen 0 y {d['pon_con_100_pct']} valen 1.")
    inf.subseccion("Variables predictoras")
    inf.p("Se usan la localidad y la tarjeta (codificación <i>one-hot</i>), la cantidad de equipos del puerto, los porcentajes de equipos "
          "con salida de TV y de equipos modernos, la cantidad de modelos distintos y la proporción de los cinco modelos más frecuentes "
          f"en el conjunto de entrenamiento ({shares}). Se excluyen todas las variables derivadas de la versión de firmware (proporción "
          "de versiones V3 y cantidad de versiones), porque contienen la respuesta, además de los identificadores y de los indicadores de "
          f"huecos de ID, no validados con la empresa. Con las {m['obj01']['modelos_canonicos']} proporciones de modelo, "
          f"la regresión lineal tiene {sh[k22]['predictores']} predictores para {d['entrenamiento']} puertos y su R² ajustado de prueba cae a "
          f"{c(sh[k22]['R2_ajustado_prueba'])}, frente a {c(sh[k5]['R2_ajustado_prueba'])} con cinco.")
    inf.subseccion("Partición y validación")
    inf.p(f"Se reserva el 20 % de los puertos ({d['prueba']}) como conjunto de prueba (semilla 42), que se usa una única vez al final. Con "
          f"el 80 % restante ({d['entrenamiento']} puertos) se aplica validación cruzada <i>k-fold</i> de cinco particiones, con mezcla y "
          "semilla 42, para elegir hiperparámetros y modelo. No hace falta agrupar porque cada fila ya es un puerto.")
    inf.subseccion("Métricas")
    inf.p("Se informan MSE, RMSE, MAE, R² y R² ajustado en entrenamiento, validación cruzada (media ± desvío) y prueba. El R² ajustado se "
          "calcula como")
    eq = inf.ecuacion("R<super>2</super><sub>aj</sub> = 1 − (1 − R<super>2</super>) · (<i>n</i> − 1) / (<i>n</i> − <i>p</i> − 1)")
    inf.p(f"donde <i>p</i> = {v['predictores_efectivos']} es la cantidad de predictores efectivos (columnas <i>one-hot</i> menos una por "
          f"variable categórica). No se usa MAPE porque {d['pon_con_0_pct']} puertos tienen valor real nulo y la métrica divide por él.")

    inf.seccion("Métodos")
    inf.p(f"Todo el preprocesamiento (codificación <i>one-hot</i> que ignora categorías nuevas, imputación por mediana y estandarización) "
          f"se encapsula en un <i>Pipeline</i> de scikit-learn [{R['sklearn']}], de modo que nada se ajusta con datos de validación o de "
          "prueba. La línea base es una regresión lineal por mínimos cuadrados; se la compara con Ridge "
          f"[{R['ridge']}], Random Forest [{R['rf']}] y Gradient Boosting [{R['gb']}], y con un predictor que devuelve siempre la media de "
          "entrenamiento. Los hiperparámetros se buscaron con <i>GridSearchCV</i> minimizando el RMSE de validación cruzada. En Ridge "
          f"se probó α en {{0,1; 1; 10}} y se eligió {hiper(hp['Ridge']).replace('alpha', 'α')}. En Random Forest (300 árboles), "
          "<i>min_samples_leaf</i> en {1, 3, 5} y <i>max_depth</i> en {sin límite, 8}; se eligieron "
          f"{hiper(hp['Random Forest'])}, que mejoran el RMSE de validación {c(gs['Random Forest']['mejora_pct'], 1)} % respecto de "
          "los valores por defecto. En Gradient Boosting (200 árboles), <i>learning_rate</i> en {0,05; 0,1} y <i>max_depth</i> en "
          f"{{2, 3}}; se eligieron {hiper(hp['Gradient Boosting'])} (mejora de {c(gs['Gradient Boosting']['mejora_pct'], 1)} %).")
    inf.p("El modelo final se eligió por el menor RMSE medio de validación cruzada, sin mirar la prueba. Sobre él se calcularon la "
          f"importancia por permutación, el análisis de residuos con las pruebas de Shapiro-Wilk [{R['shapiro']}] y de Breusch-Pagan en la "
          f"versión de Koenker [{R['koenker']}], y la curva de aprendizaje. Como prueba adicional, el mejor modelo se repitió con tres "
          "variables por puerto del listado de la OLT del 29/10/2026: porcentaje de equipos en línea, distancia mediana y potencia "
          "recibida mediana.")

    inf.seccion("Resultados")
    modelos = ["Dummy (promedio)", "Regresión Lineal", "Ridge", "Random Forest", "Gradient Boosting"]
    nombres = {"Dummy (promedio)": "Constante (media)", "Regresión Lineal": "Regresión lineal"}
    filas = [["Modelo", "R² entr.", "R² VC (media ± desvío)", "R² prueba", "R² aj. prueba", "RMSE prueba", "MAE prueba"]]
    for mo in modelos:
        filas.append([nombres.get(mo, mo), c(en[mo]["R2"]), f"{c(cv[mo]['R2'])} ± {c(cvd[mo]['R2'])}", c(pr[mo]["R2"]),
                      c(pr[mo]["R2_ajustado"]), c(pr[mo]["RMSE"], 3), c(pr[mo]["MAE"], 3)])
    tab = inf.tabla("Métricas de regresión por modelo", filas, [3.4 * cm, 1.7 * cm, 3.3 * cm, 1.8 * cm, 2.1 * cm, 2.0 * cm, 1.9 * cm],
                    resaltar=[modelos.index(mejor) + 1],
                    nota=f"VC: validación cruzada de cinco particiones sobre {d['entrenamiento']} puertos; prueba: {d['prueba']} puertos. "
                         "Errores en proporción (0,10 = 10 puntos porcentuales). Sombreado: modelo elegido.")
    inf.p(f"La Tabla {tab} resume las métricas. Todos los modelos superan con amplitud al predictor constante, cuyo R² de prueba es "
          f"{c(pr['Dummy (promedio)']['R2'])}. {mejor} y la regresión lineal son prácticamente equivalentes: su diferencia de RMSE en "
          f"validación cruzada ({c(cv[mejor]['RMSE'], 4)} contra {c(cv['Regresión Lineal']['RMSE'], 4)}) es muy inferior al desvío entre "
          f"particiones (± {c(cvd[mejor]['RMSE'], 3)}). {mejor} cumple los tres criterios SMART: R² = {c(pr[mejor]['R2'])} ≥ "
          f"{c(s['metas']['R2_prueba'])}, R² ajustado = {c(pr[mejor]['R2_ajustado'])} ≥ {c(s['metas']['R2_ajustado_prueba'])} y MAE = "
          f"{c(pr[mejor]['MAE'], 3)} &lt; {c(s['metas']['MAE_dummy_prueba'], 3)}.")
    f1 = inf.figura(RAIZ / "reports" / "TP2" / "ieee_fig1_comparacion.png",
                    "R² (a) y RMSE (b) de cada modelo en entrenamiento, validación cruzada y prueba. Los ensambles muestran la mayor "
                    "brecha entre entrenamiento y validación cruzada.")
    inf.p(f"La Fig. {f1} muestra el sobreajuste de los ensambles: Random Forest pasa de R² = {c(en['Random Forest']['R2'])} en "
          f"entrenamiento a {c(cv['Random Forest']['R2'])} en validación cruzada, y Gradient Boosting de {c(en['Gradient Boosting']['R2'])} "
          f"a {c(cv['Gradient Boosting']['R2'])}. Todos los modelos logran mejor R² en prueba que en validación cruzada, lo que indica que "
          f"la partición de prueba ({d['prueba']} puertos) resultó más sencilla que el promedio; por eso la selección se basa en la "
          "validación cruzada.")
    f2 = inf.figura(RAIZ / "reports" / "TP2" / "ieee_fig2_residuos.png",
                    f"Diagnóstico de {mejor}: (a) valores predichos contra reales, con la diagonal de predicción perfecta; (b) residuos "
                    "contra predichos; (c) distribución de los residuos. Gris: predicciones fuera de muestra en entrenamiento; azul: prueba.")
    inf.p(f"Los residuos (Fig. {f2}) están centrados en cero (media {c(res['cv_entrenamiento']['media'] * 100, 2)} puntos porcentuales) "
          f"pero no son normales (Shapiro-Wilk, <i>p</i> = {c(res['cv_entrenamiento']['shapiro_p'], 4)}) y muestran heterocedasticidad "
          f"leve (Breusch-Pagan, <i>p</i> = {c(res['cv_entrenamiento']['breusch_pagan_p'], 3)}). El error absoluto decrece con el tamaño del "
          f"puerto (Spearman, ρ = {c(pat['spearman_abs_residuo_vs_onts'])}): en los {pat['n_pon_5_onts_o_menos']} puertos con cinco "
          f"equipos o menos el MAE es {c(pat['MAE_pon_5_onts_o_menos'], 3)}, frente a {c(pat['MAE_pon_mas_de_5_onts'], 3)} en el resto.")
    f3 = inf.figura(RAIZ / "reports" / "TP2" / "ieee_fig3_importancia.png",
                    f"(a) Importancia por permutación de {mejor} en prueba (caída del R² al permutar cada variable). (b) Curvas de "
                    f"aprendizaje de {mejor} y de Random Forest (RMSE de entrenamiento en trazo discontinuo y de validación en trazo continuo).")
    j = t["importancia_pct_catv_y_share_EG8143A5_juntas"]
    inf.p(f"La variable más influyente es el porcentaje de equipos con TV (caída del R² de {c(t['importancia_permutacion']['pct_catv'])}), "
          f"casi idéntica a la proporción de EG8143A5 (correlación {c(t['correlacion_pct_catv_share_EG8143A5'])}); permutadas juntas, el R² "
          f"cae {c(j['media'])}. Le sigue la localidad ({c(t['importancia_permutacion']['Localidad'])}). En la Fig. {f3}b, la curva de "
          f"{mejor} converge con una brecha final de {c(cu[mejor + ' (mejor)']['brecha_final_pp'], 1)} puntos porcentuales, mientras que "
          f"Random Forest mantiene {c(cu['Random Forest']['brecha_final_pp'], 1)}. Por último, al incorporar las variables de la OLT el R² "
          f"de validación cruzada baja de {c(olt['sin OLT']['R2_cv'])} a {c(olt['con OLT']['R2_cv'])} y el R² ajustado de prueba, de "
          f"{c(olt['sin OLT']['R2_ajustado_prueba'])} a {c(olt['con OLT']['R2_ajustado_prueba'])}.")

    inf.seccion("Discusión")
    inf.subseccion("¿Cuál es el modelo más adecuado y depende de la métrica?")
    inf.p(f"{mejor} es el más adecuado: tiene el menor RMSE y el mayor R² en validación cruzada, y la regresión lineal queda a una "
          "distancia despreciable. En prueba, Random Forest obtiene el mejor R² y RMSE y Gradient Boosting el mejor MAE, pero esa ventaja "
          "no se sostiene en validación cruzada; elegir por la prueba equivaldría a ajustar el modelo mirando el conjunto de evaluación. "
          "El MAE favorece a los árboles, que aciertan los puertos típicos, mientras que el RMSE penaliza los errores grandes en los "
          "puertos extremos, donde los modelos lineales son más estables. Como para la empresa importa no errar por mucho en un puerto, "
          "el RMSE es la métrica de selección más adecuada.")
    inf.subseccion("¿Hubo sobreajuste o subajuste?")
    inf.p(f"Random Forest y Gradient Boosting sobreajustan (brechas de R² entre entrenamiento y validación cruzada de "
          f"{c(t['diagnostico']['Random Forest']['brecha_entrenamiento_cv'])} y {c(t['diagnostico']['Gradient Boosting']['brecha_entrenamiento_cv'])}): "
          f"con {d['entrenamiento']} puertos, los árboles aprenden particularidades que no se repiten, lo que corresponde a varianza alta. "
          f"Los modelos lineales no sobreajustan (brecha de {c(t['diagnostico'][mejor]['brecha_entrenamiento_cv'])}), pero tienen sesgo "
          f"moderado: su R² de entrenamiento ({c(en[mejor]['R2'])}) es el techo de un modelo aditivo con estas variables, y su curva de "
          "aprendizaje casi converge, por lo que más datos aportarían poco. La búsqueda de hiperparámetros ya redujo la varianza de los "
          "árboles, y limitar las proporciones de modelo a cinco fue la principal medida contra ella; para reducir el sesgo harían falta "
          "variables nuevas, como la fecha de la última campaña de actualización.")
    inf.subseccion("¿Qué factores del dominio explican el desempeño?")
    adv = o3["advertencia_fuera_vs_desactualizado"]
    inf.p(f"Con {d['pon']} puertos y {v['predictores_efectivos']} predictores, los modelos flexibles no tienen datos suficientes para "
          "que sus interacciones compensen, y la relación es casi aditiva: composición del parque más localidad. Parte de lo que se "
          "predice es la propia definición del estándar: en el EG8143A5 la versión modal es la V3 y la mayoría de los equipos tiene la V5, "
          f"más nueva. En total, {adv['fuera_estandar_con_generacion_mayor']} de los {o3['equipos_fuera_estandar']} equipos fuera de "
          "estándar tienen una generación más nueva que la modal, lo que debe validarse con la empresa. Que las variables físicas de la "
          "OLT no aporten confirma que estar fuera de estándar es una cuestión administrativa. Los residuos sí conservan un patrón: los "
          "puertos chicos tienen proporciones muy variables (con dos equipos, solo 0, 0,5 o 1), lo que sugiere ponderar cada puerto por su "
          "cantidad de equipos o modelar la proporción con una regresión binomial.")

    inf.seccion("Conclusiones")
    inf.p(f"{mejor} estima el porcentaje de firmware fuera de estándar de cada puerto con un error medio de "
          f"{c(pr[mejor]['MAE'] * 100, 1)} puntos porcentuales en prueba y explica alrededor de la mitad de la variabilidad entre puertos "
          f"(R² de {c(cv[mejor]['R2'])} en validación cruzada y {c(pr[mejor]['R2'])} en prueba), cumpliendo los criterios fijados. Con el "
          "volumen disponible, los ensambles de árboles no se justifican. Antes de usar el modelo para planificar actualizaciones, la "
          "empresa debe confirmar cuál es la versión de firmware correcta para cada modelo.")

    inf.referencias([REFS_COMUNES["itu"], REFS_COMUNES["sklearn"],
                     "A. E. Hoerl y R. W. Kennard, “Ridge regression: Biased estimation for nonorthogonal problems,” <i>Technometrics</i>, vol. 12, n.º 1, pp. 55–67, 1970.",
                     REFS_COMUNES["rf"], REFS_COMUNES["gb"],
                     "S. S. Shapiro y M. B. Wilk, “An analysis of variance test for normality (complete samples),” <i>Biometrika</i>, vol. 52, n.º 3/4, pp. 591–611, 1965.",
                     "R. Koenker, “A note on studentizing a test for heteroscedasticity,” <i>J. Econometrics</i>, vol. 17, n.º 1, pp. 107–112, 1981.",
                     REFS_COMUNES["esl"]])
    return inf.construir(SALIDA / "TP2_informe_regresion_Forzani_Racca_Cesano.pdf")


# ================================================================== TP3
def informe_tp3(m):
    t = m["obj14_tp3"]
    mejor = t["mejor_modelo"]
    d, pr, cv, cvd, en = t["datos"], t["prueba"], t["cv_media"], t["cv_desvio"], t["entrenamiento"]
    s = t["criterio_smart"]
    vec = pr["Regla de los vecinos"]
    (tn, fp), (fn, tp) = t["matrices_confusion_prueba"][mejor]
    u = t["umbral_decision"]
    r80 = u["comparacion_prueba"][next(k for k in u["comparacion_prueba"] if k.startswith("recall"))]
    cl = t["clustering"]
    kb = str(cl["k_mejor"])
    pe = cl["perfil_extra"]
    g = max(pe, key=lambda k: pe[k]["pct_en_riesgo"])
    otros = [pe[k]["pct_en_riesgo"] for k in pe if k != g]
    hp = t["hiperparametros_elegidos"]
    gs = t["gridsearch_mejora"]
    seg = t["segundos_busqueda"]
    r05 = t["recall_prueba_con_umbral_05"]
    imp = t["importancia_permutacion"]
    diag = t["diagnostico"]
    R = {k: i + 1 for i, k in enumerate(["itu", "sklearn", "cox", "cart", "knn", "esl", "rf", "gb", "desb", "cohen", "pr", "lloyd",
                                         "silueta", "db", "ari"])}
    hpf = lambda n: hiper(hp[n])

    inf = Informe("TP3 — Clasificación", "¿Tiene el cliente la señal de la fibra en riesgo?<br/>Clasificación de ONTs en una red GPON")
    inf.encabezado(
        f"Se clasifica si la potencia óptica que recibe cada ONT en línea está en riesgo (por debajo de −25 dBm) usando solo información "
        f"disponible antes de medirla: ubicación, equipo y la señal media de los vecinos del mismo puerto. Sobre {d['equipos']} ONT "
        f"({pct(d['pct_en_riesgo'])} % en riesgo), con una partición estratificada y agrupada por puerto, se comparan regresión logística, "
        f"árbol de decisión, KNN y Naive Bayes, más dos ensambles y K-Means. La regresión logística obtuvo la mejor PR-AUC en validación "
        f"cruzada y, en prueba, ROC-AUC = {c(pr[mejor]['ROC_AUC'])} y PR-AUC = {c(pr[mejor]['PR_AUC'])} (tasa base {c(pr['Dummy (prior)']['PR_AUC'])}), "
        f"con lo que cumple los criterios fijados. Una regla sin aprendizaje basada solo en la señal de los vecinos alcanza un desempeño "
        f"equivalente (ROC-AUC = {c(vec['ROC_AUC'])}): el riesgo depende de la fibra compartida del puerto y no del equipo. Los ensambles "
        f"sobreajustan sin mejorar la prueba, y el clustering revela un grupo de tendidos largos con {pct(pe[g]['pct_en_riesgo'])} % de "
        f"clientes en riesgo.",
        "GPON, potencia óptica, clasificación desbalanceada, regresión logística, validación agrupada, K-Means.")

    inf.seccion("Introducción")
    inf.p(f"En una red GPON, la potencia óptica que recibe cada ONT debe superar la sensibilidad mínima del receptor, que para la clase "
          f"B+ es de −27 dBm [{R['itu']}]. Un cliente con señal cercana a ese límite tiene servicio, pero cualquier degradación adicional "
          "lo deja sin conexión. Este trabajo define como <i>en riesgo</i> a los equipos que reciben menos de −25 dBm (2 dB de margen) y "
          "busca anticiparlos sin medir su propia señal, lo que permite elegir el puerto de cada alta nueva, adelantarse a los reclamos y "
          "distinguir si el problema está en la fibra o en el módem.")
    inf.p("La pregunta surge de una fuga de información detectada en el TP1: un modelo que usa la señal del propio equipo para predecir su "
          "estado acierta sin aprender nada. Los datos son el inventario del TP1 cruzado con el listado de la OLT que entregó la empresa el "
          "29/10/2026, uso confirmado por la cátedra.")

    inf.seccion("Marco experimental")
    inf.subseccion("Problema y distribución de clases")
    inf.p(f"Es una clasificación binaria sobre los {d['equipos']} equipos en línea que cruzan con el inventario y tienen lectura válida. "
          f"La clase <i>en riesgo</i> tiene {d['en_riesgo']} equipos ({pct(d['pct_en_riesgo'])} %), un desbalance de uno a ocho: un "
          f"clasificador que siempre predice <i>sin riesgo</i> logra exactitud {c(pr['Dummy (prior)']['accuracy'])} sin detectar a nadie. "
          "Por eso se priorizan métricas sensibles a la clase minoritaria.")
    inf.subseccion("Variables")
    inf.p("Entran la localidad, el modelo de ONT, los puertos LAN y la tecnología Wi-Fi (<i>one-hot</i>); y el slot, el puerto, el ID, la "
          "posición relativa en el puerto, los equipos del puerto, la generación de firmware, el indicador de firmware fuera de estándar, "
          "la distancia a la OLT y la señal media de los <i>otros</i> equipos en línea del mismo puerto:")
    inf.ecuacion("<i>v</i><sub><i>i</i></sub> = (1 / (<i>n</i><sub>PON</sub> − 1)) · Σ<sub><i>j</i> ≠ <i>i</i></sub> RXP<sub><i>j</i></sub>")
    inf.p("donde la suma recorre los equipos en línea del mismo puerto que el equipo <i>i</i> y <i>n</i><sub>PON</sub> es su cantidad. "
          "Se excluyen la potencia recibida y transmitida, el estado y el nivel de señal del propio equipo, porque son la respuesta. La "
          "señal de los vecinos sí es legítima: cuando se instala un cliente, la de sus vecinos ya está medida y la suya todavía no existe.")
    inf.subseccion("Partición y validación")
    inf.p(f"Los equipos de un puerto comparten la fibra, de modo que repartirlos entre entrenamiento y prueba filtraría información. Se "
          "usa <i>StratifiedGroupKFold</i> de cinco particiones (mezcla, semilla 42) con el puerto como grupo; la prueba es una de esas "
          f"particiones ({d['prueba']} equipos de {d['pon_prueba']} puertos, {pct(d['pct_en_riesgo_prueba'])} % en riesgo) y no comparte "
          f"ningún puerto con el entrenamiento ({d['entrenamiento']} equipos, {pct(d['pct_en_riesgo_entrenamiento'])} % en riesgo). La "
          "validación cruzada aplica la misma estrategia sobre el entrenamiento.")
    inf.subseccion("Métricas")
    inf.p(f"Se informan exactitud y exactitud balanceada; precisión, <i>recall</i> y F1 de la clase en riesgo y ponderados; Kappa de Cohen "
          f"[{R['cohen']}]; ROC-AUC y PR-AUC, más informativa con clases desbalanceadas [{R['pr']}]. Todas se calculan en entrenamiento, "
          "validación cruzada y prueba. La referencia es un clasificador que predice la proporción de clases, al que se suma una regla "
          "sin aprendizaje que ordena a los clientes por la señal de sus vecinos.")

    inf.seccion("Métodos")
    inf.p(f"El preprocesamiento (<i>one-hot</i>, imputación por mediana y estandarización) va dentro de un <i>Pipeline</i> [{R['sklearn']}]. "
          f"La línea base es la regresión logística [{R['cox']}] (<i>C</i> en {{0,01; 0,1; 1; 10}}; se eligió {hpf('Regresión Logística')}). "
          f"Se la compara con un árbol de decisión [{R['cart']}] ({hpf('Árbol de Decisión')}), KNN [{R['knn']}] ({hpf('KNN')}) y Naive "
          f"Bayes gaussiano [{R['esl']}] ({hpf('Naive Bayes')}). Contra el desbalance [{R['desb']}] se usa <i>class_weight</i> balanceado "
          "en la regresión logística, el árbol y Random Forest. En KNN, Naive Bayes y Gradient Boosting el umbral de decisión se elige "
          "en validación cruzada (F1 máximo sobre probabilidades fuera de muestra) y, para medirlos en validación cruzada, se vuelve a "
          "elegir dentro de cada partición.")
    inf.p("Los hiperparámetros se buscaron con <i>GridSearchCV</i> y la misma validación agrupada, maximizando la PR-AUC. El clasificador "
          "se eligió entre los cuatro individuales por la PR-AUC media de validación cruzada. Se agregan la importancia por permutación, "
          "el análisis del umbral de decisión y la curva de aprendizaje.")

    inf.seccion("Resultados")
    mods = ["Regresión Logística", "Árbol de Decisión", "KNN", "Naive Bayes", "Random Forest", "Gradient Boosting", "Dummy (prior)"]
    nom = {"Regresión Logística": "Reg. logística", "Árbol de Decisión": "Árbol de decisión", "Dummy (prior)": "Constante (prior)",
           "Regla de los vecinos": "Regla de vecinos"}
    filas = [["Modelo", "Exact.", "Exact. bal.", "Precisión", "Recall", "F1", "κ", "ROC-AUC", "PR-AUC"]]
    for n in mods:
        x = pr[n]
        filas.append([nom.get(n, n), c(x["accuracy"]), c(x["accuracy_balanceada"]), c(x["precision"]), c(x["recall"]), c(x["F1"]),
                      c(x["kappa"]), c(x["ROC_AUC"]), c(x["PR_AUC"])])
    filas.append([nom["Regla de los vecinos"], "—", "—", "—", "—", "—", "—", c(vec["ROC_AUC"]), c(vec["PR_AUC"])])
    tab1 = inf.tabla("Métricas de clasificación en prueba (clase en riesgo)", filas,
                     [3.2 * cm, 1.45 * cm, 1.65 * cm, 1.65 * cm, 1.45 * cm, 1.3 * cm, 1.2 * cm, 2.0 * cm, 1.9 * cm], resaltar=[1],
                     nota=f"Prueba: {d['prueba']} equipos. Umbral 0,5, salvo KNN, Naive Bayes y Gradient Boosting, cuyo umbral se eligió "
                          "en validación cruzada. La regla de vecinos no es un clasificador: solo ordena por −<i>v</i><sub><i>i</i></sub>.")
    filas2 = [["Modelo", "ROC-AUC entr.", "ROC-AUC VC", "ROC-AUC prueba", "PR-AUC VC", "Diagnóstico"]]
    for n in mods[:-1]:
        filas2.append([nom.get(n, n), c(en[n]["ROC_AUC"]), f"{c(cv[n]['ROC_AUC'])} ± {c(cvd[n]['ROC_AUC'])}", c(pr[n]["ROC_AUC"]),
                       f"{c(cv[n]['PR_AUC'])} ± {c(cvd[n]['PR_AUC'])}", diag[n]["diagnostico"].split(":")[0]])
    inf.p(f"La Tabla {tab1} resume el desempeño en prueba. La {mejor.lower()} detecta {tp} de los {tp + fn} clientes en riesgo "
          f"(<i>recall</i> {c(pr[mejor]['recall'])}) a costa de {fp} falsas alarmas (precisión {c(pr[mejor]['precision'])}) y cumple los "
          f"criterios SMART: ROC-AUC = {c(pr[mejor]['ROC_AUC'])} ≥ {c(s['metas']['ROC_AUC_prueba'])} y PR-AUC = {c(pr[mejor]['PR_AUC'])} ≥ "
          f"{c(s['metas']['PR_AUC_prueba'])}. La regla de los vecinos obtiene ROC-AUC = {c(vec['ROC_AUC'])} y PR-AUC = {c(vec['PR_AUC'])}, "
          "a la par del mejor clasificador.")
    tab2 = inf.tabla("Ajuste de cada modelo en entrenamiento, validación cruzada y prueba", filas2,
                     [3.4 * cm, 2.2 * cm, 2.6 * cm, 2.4 * cm, 2.6 * cm, 3.4 * cm], resaltar=[1],
                     nota="Diagnóstico: sobreajuste si la ROC-AUC de entrenamiento supera a la de validación cruzada o a la de prueba en "
                          "más de 0,10; subajuste si la ROC-AUC de entrenamiento es menor que 0,68.")
    f1 = inf.figura(RAIZ / "reports" / "TP3" / "ieee_fig1_matrices.png",
                    "Matrices de confusión en prueba (filas: clase real; columnas: clase predicha). El color indica la proporción de "
                    "cada fila.")
    inf.p(f"Las matrices de la Fig. {f1} muestran el compromiso entre <i>recall</i> y precisión: los modelos que más clientes en riesgo "
          f"detectan son los que más falsas alarmas generan. La importancia por permutación confirma que casi toda la información está "
          f"en la señal de los vecinos (caída de PR-AUC de {c(imp['vec_rxp'], 3)}); el resto de las variables aporta cerca de cero. Si se "
          f"baja el umbral hasta detectar el {pct(u['recall_objetivo'], 0)} % de los casos en validación cruzada, en prueba el "
          f"<i>recall</i> sube a {c(r80['recall'])}, pero se marcan {r80['marcados']} de {d['prueba']} equipos y solo "
          f"{pct(r80['precision'], 0)} % de las alarmas son reales.")
    f2 = inf.figura(RAIZ / "reports" / "TP3" / "ieee_fig2_roc_pr.png",
                    "Curvas ROC (a) y precisión-recall (b) en prueba. La regla de los vecinos (trazo discontinuo) queda entre los "
                    "clasificadores; la línea gris indica el azar.")
    inf.p(f"En la Fig. {f2} todas las curvas quedan próximas entre sí y lejos de la esquina ideal: ningún modelo separa las clases "
          "mucho mejor que otro.")

    inf.seccion("Actividades complementarias")
    inf.subseccion("Ensamble")
    inf.p(f"Random Forest [{R['rf']}] (<i>bagging</i>, 300 árboles; {hpf('Random Forest')}) y Gradient Boosting [{R['gb']}] "
          f"(<i>boosting</i>, 200 árboles; {hpf('Gradient Boosting')}) se compararon con las mismas métricas (Tablas {tab1} y {tab2}). "
          f"Random Forest tiene la mayor PR-AUC de validación cruzada ({c(cv['Random Forest']['PR_AUC'])} contra "
          f"{c(cv[mejor]['PR_AUC'])}), pero la diferencia es muy inferior a su desvío (± {c(cvd['Random Forest']['PR_AUC'])}); además "
          f"sobreajusta (ROC-AUC de entrenamiento {c(en['Random Forest']['ROC_AUC'])}) y en prueba no alcanza la meta "
          f"(ROC-AUC = {c(pr['Random Forest']['ROC_AUC'], 3)}). Gradient Boosting es el peor en validación cruzada "
          f"({c(cv['Gradient Boosting']['PR_AUC'])}) y el mejor en prueba ({c(pr['Gradient Boosting']['PR_AUC'])}), señal de inestabilidad. "
          f"Su búsqueda de hiperparámetros tardó {c(seg['Random Forest'], 0)} s y {c(seg['Gradient Boosting'], 0)} s, contra "
          f"{c(seg[mejor], 1)} s de la regresión logística, y se pierde interpretabilidad: la ganancia no justifica la complejidad.")
    inf.subseccion("Clustering")
    f3 = inf.n_fig + 1   # el texto va antes que la figura para que no quede un hueco al final de la página
    inf.p(f"Se aplicó K-Means [{R['lloyd']}] con <i>k</i> de 2 a 8, elegido por el coeficiente de silueta [{R['silueta']}] junto con el "
          f"codo y el índice de Davies-Bouldin [{R['db']}]. El mejor valor es <i>k</i> = {kb}, con silueta {c(cl['silueta'][kb])} "
          f"(estructura débil), y los grupos casi no coinciden con la clase: índice de Rand ajustado [{R['ari']}] de {c(cl['ARI'][kb])} "
          f"(Fig. {f3}a-b). Con <i>k</i> = {cl['k_extra']} aparece, sin embargo, una subestructura (Fig. {f3}c): un grupo de "
          f"{pe[g]['equipos']} equipos con {pct(pe[g]['pct_en_riesgo'])} % en riesgo, frente a {pct(min(otros))} % a {pct(max(otros))} % "
          f"en los demás, formado por tendidos largos (distancia mediana {c(pe[g]['distancia_mediana_m'] / 1000, 1)} km) con señal de "
          f"vecinos débil ({c(pe[g]['vec_rxp_media'], 1)} dBm de media) y concentrado en {pe[g]['localidad_principal']}. El clustering "
          "aporta así un criterio para priorizar el mantenimiento que la clasificación supervisada no muestra.")
    inf.figura(RAIZ / "reports" / "TP3" / "ieee_fig3_clustering.png",
               f"K-Means con las mismas variables, sin la etiqueta: (a) proyección PCA coloreada por grupo (k = {kb}); (b) la misma "
               "proyección coloreada por clase real (rojo: en riesgo; gris: sin riesgo); (c) proporción de equipos en riesgo en cada "
               f"grupo con k = {cl['k_extra']} (la línea discontinua es la tasa global).")

    inf.seccion("Discusión")
    inf.subseccion("¿Cuál es el clasificador más adecuado y cambia al priorizar recall o precisión?")
    rec_max = max(mods[:-1], key=lambda n: pr[n]["recall"])
    prec_max = max(mods[:-1], key=lambda n: pr[n]["precision"])
    (_, fp_p), (fn_p, tp_p) = t["matrices_confusion_prueba"][prec_max]
    detecta = (f"y es la que más clientes en riesgo encuentra en prueba (<i>recall</i> {c(pr[mejor]['recall'])})" if rec_max == mejor else
               f"y encuentra el {pct(pr[mejor]['recall'], 0)} % de los clientes en riesgo en prueba (el máximo es de {rec_max}, "
               f"<i>recall</i> {c(pr[rec_max]['recall'])})")
    inf.p(f"La {mejor.lower()} es la más adecuada: tiene la mejor PR-AUC media de validación cruzada entre los individuales, no sobreajusta "
          f"{detecta}. Si se priorizara la "
          f"precisión, convendría {prec_max} (precisión {c(pr[prec_max]['precision'])}), que da solo {fp_p} falsas alarmas pero deja sin "
          f"detectar a {fn_p} de {fn_p + tp_p} clientes en riesgo. Como un cliente en riesgo no detectado termina en reclamo, se prioriza "
          f"el <i>recall</i>; el umbral que maximiza F2 ({c(u['umbral_f2'])}) coincide prácticamente con 0,5 porque el peso balanceado ya "
          "desplaza la decisión.")
    inf.subseccion("¿Hubo sobreajuste o subajuste? ¿Qué impacto tuvo el desbalance?")
    sobre = [n for n in mods[:-1] if diag[n]["diagnostico"].startswith("sobreajuste")]
    nombres_sobre = [n.lower() if n.startswith(("Árbol", "Regresión")) else n for n in sobre]
    lista_sobre = ", ".join(nombres_sobre[:-1]) + " y " + nombres_sobre[-1] if len(nombres_sobre) > 1 else nombres_sobre[0]
    inf.p(f"Sobreajustan {lista_sobre} (Tabla {tab2}); el caso "
          f"extremo es KNN, con ROC-AUC de entrenamiento {c(en['KNN']['ROC_AUC'])} porque con ponderación por distancia cada equipo se "
          f"reconoce a sí mismo. La regresión logística y Naive Bayes están equilibrados (brechas de "
          f"{c(diag[mejor]['brecha_entrenamiento_cv'])} y {c(diag['Naive Bayes']['brecha_entrenamiento_cv'])}) pero tienen sesgo alto: "
          f"su curva de aprendizaje queda plana (PR-AUC de validación {c(t['curva_aprendizaje'][mejor + ' (mejor)']['PR_AUC_validacion_inicio'])} "
          f"con {t['curva_aprendizaje'][mejor + ' (mejor)']['n_inicio']} equipos y "
          f"{c(t['curva_aprendizaje'][mejor + ' (mejor)']['PR_AUC_validacion_final'])} con {t['curva_aprendizaje'][mejor + ' (mejor)']['n_final']}), "
          "de modo que el límite es la información, no la cantidad de datos. El desbalance vuelve engañosa la exactitud y, sin "
          f"corrección, anula la detección: con el umbral 0,5 el <i>recall</i> en prueba sería {c(r05['KNN'])} en KNN, "
          f"{c(r05['Naive Bayes'])} en Naive Bayes y {c(r05['Gradient Boosting'])} en Gradient Boosting, frente a "
          f"{c(pr['KNN']['recall'])}, {c(pr['Naive Bayes']['recall'])} y {c(pr['Gradient Boosting']['recall'])} con el umbral elegido.")
    inf.subseccion("¿Qué factores del dominio explican el desempeño?")
    inf.p(f"La potencia recibida depende del divisor óptico, los empalmes y los conectores que el cliente comparte con su puerto, por lo "
          "que la señal de los vecinos concentra la información y el modelo de ONT o el firmware casi no influyen. Aunque hay "
          f"{d['equipos']} equipos, la información relevante vive en {d['pon']} puertos; al separar por puerto, los modelos flexibles "
          "aprenden ruido de cada uno. Las clases se separan poco (ninguna ROC-AUC de validación cruzada supera "
          f"{c(max(cv[n]['ROC_AUC'] for n in mods[:-1]))}). El clustering no reproduce las clases, pero identifica los tendidos largos como "
          "subgrupo de mayor riesgo, y el ensamble no justifica su complejidad.")

    inf.seccion("Conclusiones")
    inf.p(f"Sin medir la señal de un cliente, la {mejor.lower()} identifica a los clientes en riesgo mucho mejor que el azar "
          f"(PR-AUC {c(pr[mejor]['PR_AUC'])} contra {c(pr['Dummy (prior)']['PR_AUC'])}) y cumple los criterios fijados. Casi todo ese "
          "poder proviene de la señal de los vecinos del puerto, al punto de que una regla sin aprendizaje rinde igual: el riesgo está "
          "en la fibra compartida y no en el módem. Para elegir dónde conectar a un cliente nuevo alcanza con observar la señal de sus "
          "futuros vecinos, y los tendidos largos detectados por el clustering son el punto de partida para el mantenimiento preventivo.")

    inf.referencias([
        REFS_COMUNES["itu"], REFS_COMUNES["sklearn"],
        "D. R. Cox, “The regression analysis of binary sequences,” <i>J. Roy. Statist. Soc. B</i>, vol. 20, n.º 2, pp. 215–242, 1958.",
        "L. Breiman, J. H. Friedman, R. A. Olshen y C. J. Stone, <i>Classification and Regression Trees</i>. Belmont, CA, EE. UU.: Wadsworth, 1984.",
        "T. Cover y P. Hart, “Nearest neighbor pattern classification,” <i>IEEE Trans. Inf. Theory</i>, vol. 13, n.º 1, pp. 21–27, 1967.",
        REFS_COMUNES["esl"], REFS_COMUNES["rf"], REFS_COMUNES["gb"],
        "H. He y E. A. Garcia, “Learning from imbalanced data,” <i>IEEE Trans. Knowl. Data Eng.</i>, vol. 21, n.º 9, pp. 1263–1284, 2009.",
        "J. Cohen, “A coefficient of agreement for nominal scales,” <i>Educ. Psychol. Meas.</i>, vol. 20, n.º 1, pp. 37–46, 1960.",
        "T. Saito y M. Rehmsmeier, “The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets,” <i>PLoS ONE</i>, vol. 10, n.º 3, e0118432, 2015.",
        "S. Lloyd, “Least squares quantization in PCM,” <i>IEEE Trans. Inf. Theory</i>, vol. 28, n.º 2, pp. 129–137, 1982.",
        "P. J. Rousseeuw, “Silhouettes: A graphical aid to the interpretation and validation of cluster analysis,” <i>J. Comput. Appl. Math.</i>, vol. 20, pp. 53–65, 1987.",
        "D. L. Davies y D. W. Bouldin, “A cluster separation measure,” <i>IEEE Trans. Pattern Anal. Mach. Intell.</i>, vol. PAMI-1, n.º 2, pp. 224–227, 1979.",
        "L. Hubert y P. Arabie, “Comparing partitions,” <i>J. Classif.</i>, vol. 2, n.º 1, pp. 193–218, 1985."])
    return inf.construir(SALIDA / "TP3_informe_clasificacion_Forzani_Racca_Cesano.pdf")


def main():
    from informes_figuras import figuras_tp2, figuras_tp3
    m = json.loads(METRICS.read_text(encoding="utf-8"))
    figuras_tp2(m, RAIZ / "reports" / "TP2")
    figuras_tp3(m, RAIZ / "reports" / "TP3")
    for f in (informe_tp2(m), informe_tp3(m)):
        print("PDF:", f.relative_to(RAIZ))


if __name__ == "__main__":
    main()
