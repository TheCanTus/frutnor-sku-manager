import subprocess
import sys
import tempfile
from pathlib import Path

import requests

from version import VERSION

# URL del archivo latest_version.json en el repositorio público de GitHub
# Reemplazar TU_USUARIO con el usuario real de GitHub una vez creado el repo
UPDATE_CHECK_URL = (
    "https://raw.githubusercontent.com/TU_USUARIO/frutnor-sku-manager/master/latest_version.json"
)


def _es_mas_nuevo(remoto: str, actual: str) -> bool:
    def partes(v):
        return [int(x) for x in v.strip().split(".")]
    try:
        return partes(remoto) > partes(actual)
    except Exception:
        return False


def verificar_actualizacion(timeout: int = 5):
    """
    Consulta el servidor para ver si hay una versión más nueva.
    Retorna (version, url, notas) si hay actualización disponible, o None si no hay.
    """
    try:
        r = requests.get(UPDATE_CHECK_URL, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        version_remota = data.get("version", "0.0.0")
        if _es_mas_nuevo(version_remota, VERSION):
            return version_remota, data.get("url", ""), data.get("notes", "")
    except Exception:
        pass
    return None


def descargar_e_instalar(download_url: str, progreso_callback=None) -> bool:
    """
    Descarga el nuevo .exe y prepara el reemplazo automático al cerrar la app.
    Solo funciona cuando la app corre como .exe empaquetado (PyInstaller).
    Retorna True si el proceso fue exitoso.
    """
    if not getattr(sys, "frozen", False):
        return False

    exe_actual = Path(sys.executable)
    exe_nuevo = exe_actual.parent / (exe_actual.stem + "_update.exe")

    # Descargar nuevo ejecutable
    try:
        r = requests.get(download_url, stream=True, timeout=120)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        descargado = 0
        with open(exe_nuevo, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
                descargado += len(chunk)
                if progreso_callback and total:
                    progreso_callback(int(descargado * 100 / total))
    except Exception as e:
        if exe_nuevo.exists():
            exe_nuevo.unlink()
        raise RuntimeError(f"Error descargando actualización: {e}") from e

    # Script .bat que espera a que el proceso actual cierre, reemplaza el exe y lo relanza
    bat = f"""@echo off
timeout /t 3 /nobreak > nul
move /y "{exe_nuevo}" "{exe_actual}"
start "" "{exe_actual}"
del "%~f0"
"""
    bat_path = Path(tempfile.mktemp(suffix=".bat"))
    bat_path.write_text(bat, encoding="utf-8")
    subprocess.Popen(
        ["cmd", "/c", str(bat_path)],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return True
