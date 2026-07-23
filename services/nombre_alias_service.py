"""
Gestión de aliases de nombres entre Pedix y la base de datos.

El archivo nombre_aliases.json mapea:
  "nombre tal como aparece en Pedix" -> "nombre canónico en la BD"

También maneja patrones de pack mayorista (x18u, x24u, etc.) que el importer
debe ignorar al buscar coincidencias.
"""

import re
import json
from difflib import SequenceMatcher
from core.paths import get_app_dir

ALIAS_PATH = get_app_dir() / "nombre_aliases.json"

# Patrón de descriptor de pack: "x18u", "x24u", "x6u", "x12u", etc.
_RE_PACK = re.compile(r'\s+x\d+u?\b', re.IGNORECASE)


def _strip_pack_desc(nombre):
    """
    Elimina descriptores de pack mayorista del nombre.
    "Chocman x18u Baño semiamargo" → "Chocman Baño semiamargo"
    "Donnuts x24u Blanca"          → "Donnuts Blanca"
    "Pasta de mani 12u"            → sin cambio (no tiene el prefijo x)
    """
    return _RE_PACK.sub('', nombre).strip()


def cargar_aliases():
    """Retorna dict {nombre_pedix: nombre_db}."""
    if ALIAS_PATH.exists():
        try:
            return json.loads(ALIAS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def guardar_aliases(aliases):
    ALIAS_PATH.write_text(
        json.dumps(aliases, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def resolver_nombre(nombre, aliases):
    """
    Dado un nombre de Pedix y el dict de aliases, retorna el nombre canónico en BD.
    Solo usa aliases confirmados explícitamente por el usuario.
    El stripping de pack (xNu) solo se usa para generar sugerencias, no para el import.
    """
    return aliases.get(nombre, nombre)


def top_matches(nombre_norm, nombres_db_norm, existentes_map, n=3):
    """
    Dado un nombre normalizado y la lista de claves normalizadas de la BD,
    retorna hasta n tuplas (score, nombre_original_db).
    existentes_map: {nombre_norm: nombre_original}
    """
    scores = [
        (SequenceMatcher(None, nombre_norm, db_n).ratio(), db_n)
        for db_n in nombres_db_norm
    ]
    scores.sort(reverse=True)
    result = []
    for score, db_n in scores[:n * 2]:  # take extra to allow dedup
        orig = existentes_map.get(db_n, db_n)
        if orig not in [r[1] for r in result]:
            result.append((score, orig))
        if len(result) == n:
            break
    return result
