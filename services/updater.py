import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from version import VERSION

GITHUB_REPO = "TheCanTus/frutnor-sku-manager"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _ver_tuple(v: str):
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except Exception:
        return (0,)


def verificar_actualizacion(token: str = ""):
    """
    Consulta la última release en GitHub Releases.
    Retorna (version, url_descarga, notas) si hay versión nueva, o None si no la hay o falla.
    token: Personal Access Token para repos privados (puede ser vacío para repos públicos).
    """
    try:
        headers = {"User-Agent": "SKUManager-Updater", "Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(API_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        tag = data.get("tag_name", "").lstrip("v")
        notas = data.get("body", "")
        if _ver_tuple(tag) > _ver_tuple(VERSION):
            for asset in data.get("assets", []):
                if asset["name"].lower().endswith(".exe"):
                    return tag, asset["url"], notas
    except Exception:
        pass
    return None


def descargar_e_instalar(download_url: str, token: str = "", progreso_callback=None) -> bool:
    """
    Descarga el nuevo .exe y crea un .bat que lo reemplaza al cerrar la app.
    Solo funciona cuando la app corre como .exe empaquetado (PyInstaller).
    Retorna True si la descarga fue exitosa.
    """
    if not getattr(sys, "frozen", False):
        raise RuntimeError(
            "La actualización automática solo funciona en la versión empaquetada (.exe).\n"
            "En modo desarrollo, actualizá con git pull."
        )

    exe_actual = Path(sys.executable).resolve()
    exe_nuevo = exe_actual.parent / (exe_actual.stem + "_update.exe")

    headers = {
        "User-Agent": "SKUManager-Updater",
        "Accept": "application/octet-stream",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(download_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            descargado = 0
            with open(exe_nuevo, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    descargado += len(chunk)
                    if progreso_callback and total:
                        progreso_callback(min(99, int(descargado * 100 / total)))
    except Exception as e:
        if exe_nuevo.exists():
            exe_nuevo.unlink()
        raise RuntimeError(f"Error al descargar: {e}") from e

    if progreso_callback:
        progreso_callback(100)

    # Bat que espera a que el proceso cierre, reemplaza el exe y lo relanza
    bat_content = (
        "@echo off\r\n"
        "timeout /t 3 /nobreak > nul\r\n"
        f'move /y "{exe_nuevo}" "{exe_actual}"\r\n'
        f'start "" "{exe_actual}"\r\n'
        'del "%~f0"\r\n'
    )
    bat_path = Path(tempfile.mktemp(suffix=".bat"))
    bat_path.write_text(bat_content, encoding="utf-8")
    subprocess.Popen(
        ["cmd", "/c", str(bat_path)],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return True
