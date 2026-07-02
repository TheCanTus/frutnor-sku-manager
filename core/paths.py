import sys
from pathlib import Path


def get_app_dir() -> Path:
    """
    Directorio donde se guardan datos del usuario (productos.db, config.json).
    - En desarrollo: carpeta raíz del proyecto (junto a main.py)
    - Como .exe PyInstaller: carpeta donde está el .exe
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent
