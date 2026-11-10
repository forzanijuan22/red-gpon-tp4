"""Abre el dashboard único de los tres trabajos (TP1, TP2 y TP3) en http://localhost:8501.

    python dashboards/lanzar.py

Los apartados se eligen en el panel de la izquierda. Se pueden sumar opciones de Streamlit, por ejemplo
--server.headless true para que no abra el navegador.
"""
import logging
import socket
import subprocess
import sys
from pathlib import Path

logging.disable(logging.WARNING)   # importar comun fuera de Streamlit avisa "No runtime found": es inofensivo
from comun import PALETAS  # noqa: E402
logging.disable(logging.NOTSET)

AQUI = Path(__file__).resolve().parent
PUERTO = 8501


def ocupado(puerto):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", puerto)) == 0


if __name__ == "__main__":
    opciones = [a for a in sys.argv[1:] if a.lower() not in ("tp1", "tp2", "tp3")]   # el resto va directo a Streamlit
    if len(opciones) < len(sys.argv) - 1:
        print("Ahora los tres trabajos están en un solo dashboard: elegí el apartado en el panel de la izquierda.")
    if ocupado(PUERTO):
        sys.exit(f"El puerto {PUERTO} ya está en uso: el dashboard probablemente ya está abierto en http://localhost:{PUERTO}. "
                 f"Si no, cerrá la otra terminal que lo esté usando (Ctrl + C) y probá de nuevo.")
    p = PALETAS["GEN"]   # cada apartado cambia sus colores con su propio estilo; esto es la base
    tema = {"base": "dark", "primaryColor": p["a1"], "backgroundColor": p["fondo"], "secondaryBackgroundColor": p["tarjeta"],
            "textColor": p["texto"]}
    comando = [sys.executable, "-m", "streamlit", "run", str(AQUI / "app.py"), "--server.port", str(PUERTO),
               "--browser.gatherUsageStats", "false", "--client.toolbarMode", "minimal"] + \
              [f"--theme.{k}={v}" for k, v in tema.items()] + opciones
    subprocess.run(comando)
