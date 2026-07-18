import re
import unicodedata
import pandas as pd
from database.models import Categoria, Producto
from services.product_service import crear_producto, agregar_presentacion_global

# Mapeo de categorías Pedix → código de categoría interna
PEDIX_MAP = {
    "FRUTOS SECOS Y DISECADOS": "FRU",
    "FRUTOS SECOS y DISECADOS": "FRU",
    "CHOCOLATERIA": "CHO",
    "CHOCOLATERÍA": "CHO",
    "FRUTOS SECOS BANADOS EN CHOCO": "CHO",
    "FRUTOS SECOS BAÑADOS EN CHOCO": "CHO",
    "CONGELADOS": "CGD",
    "FRUTAS CONGELADAS ALIF AGRO": "CGD",
    "AVENA, SEMILLAS Y LEGUMBRES": "AVN",
    "AVENA, SEMILLAS y LEGUMBRES": "AVN",
    "CEREALES": "CER",
    "GRANOLAS": "GRN",
    "HARINAS": "HAR",
    "ACEITES DE OLIVA": "ACE",
    "ACEITES COCO y OLIVA": "ACE",
    "MIX": "MIX",
    "REPOSTERIA Y OTROS": "REP",
    "REPOSTERIA, TE y ENDULZANTES": "REP",
    "HIERBAS Y ESPECIAS NATURALES": "REP",
    "CONDIMENTOS": "CON",
    "ALMACEN": "ALM",
    "ACEITUNAS": "ALM",
    "SNACKS SALADOS": "SAB",
    "SABORIZADOS FRUTOS SECOS": "SAB",
    "SABORIZADOS": "SAB",
    "ALFAJORES": "SAB",
    "HOGAR-HERMETICOS": "HOG",
    "HOGAR / BAZAR": "HOG",
    "GRANGER": "GRA",
    "VENTA MAYORISTA": "MAY",
    "YOGURT NATURAL y GRIEGO": "YOG",
    "YOGURT NATURAL Y GRIEGO": "YOG",
    "YERBAS Y TE": "YER",
    "YERBAS": "YER",
    "HIERBAS Y YERBAS": "YER",
    "Dulces Regionales": "MIE",
    "MIEL, PASTAS, MERMELADAS y DdL": "MIE",
    "ENTRENUTS y MIEL": "MIE",
    "SUPLEMENTOS": "SUP",
    "SUPLEMENTOS NATURALES": "SUP",
    "LINEA SIN TACC": "SGL",
    "Bonafide": "CHO",
    "FRIZADITAS": "CER",
    "KUIBI- SIN GLUTEN": "SGL",
}

SKIP_CATS = {
    "OFERTAS DE LA SEMANA",
    "¡NUEZ COSECHA 2026!",
    "¿CÓMO USO LA PAGINA?",
    "COMO USO LA PAGINA",
    "DIA del PADRE",
    "CANASTAS NAVIDEÑAS",
}


def _norm(s):
    if not s or pd.isna(s):
        return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _mapear_categoria(pedix_cat):
    if not pedix_cat:
        return None
    cat_clean = re.sub(r"[^\x20-\x7E\xC0-\xFF]", "", str(pedix_cat)).strip()
    for key, val in PEDIX_MAP.items():
        if _norm(key) in _norm(cat_clean) or _norm(cat_clean).startswith(_norm(key)):
            return val
    return None


def _debe_omitir(pedix_cat):
    if not pedix_cat:
        return True
    cat_n = _norm(str(pedix_cat))
    return any(_norm(s) in cat_n for s in SKIP_CATS)


def _extraer_pres_de_nombre(nombre):
    """Extrae el tamaño del nombre si está incluido (ej: 'Mix Premium X10kg')."""
    m = re.search(
        r"\s+[xX]?\s*(\d+(?:[.,]\d+)?)\s*(kg|kgs|kilos?|gr|grs|g|ml|cc|l|litros?)$",
        str(nombre), re.IGNORECASE
    )
    if m:
        clean = nombre[:m.start()].strip()
        return clean, m.group(1) + m.group(2)
    m2 = re.search(r"\s+[xX]\s*(kilo|kilos|kg)$", str(nombre), re.IGNORECASE)
    if m2:
        return nombre[:m2.start()].strip(), "1kg"
    return str(nombre), None


def _es_variante_nombre(texto):
    """
    True si el texto parece un sabor o nombre de variante, no una presentación estándar.
    Criterio: no contiene dígitos ni palabras clave de unidades de medida.
    Ej: "Chocolate", "Vainilla", "Frutilla roja" → True
        "500g", "1 kg", "granel"               → False
    """
    if not texto or pd.isna(texto):
        return False
    s = str(texto).strip()
    if re.search(r'\d', s):
        return False
    if re.search(r'\b(kg|g|gr|ml|cc|litro|litros|unidad|unidades|pack|granel)\b', s.lower()):
        return False
    return True


def _pres_code(p):
    if not p or pd.isna(p):
        return "1U"
    s = str(p).strip().rstrip(".,;:")   # strip trailing punctuation (e.g. "500 gr.")
    s = s.lower().strip()
    s = re.sub(r"^x\s*", "", s)         # strip leading "x " or "x"

    # Fractions: "1/2 kg" → 500G, "1/4 kg" → 250G
    m_frac = re.match(
        r"^(\d+)/(\d+)\s*(kg|kgs|kilos?|g|gr|grs|gramos?)$", s
    )
    if m_frac:
        n = int(m_frac.group(1)) / int(m_frac.group(2))
        u = m_frac.group(3).rstrip("s")
        if u in ["kg", "kilo"]:
            grams = round(n * 1000)
            return f"{grams // 1000}K" if grams >= 1000 and grams % 1000 == 0 else f"{grams}G"
        elif u in ["g", "gr", "gramo"]:
            return f"{int(n)}G"

    # Bare "kg" keyword, possibly followed by text: "kg", "kg pedrera"
    if re.match(r"^(kg|kgs|kilo|kilos?)(?:\s.*)?$", s):
        return "1K"

    # "N kilos" / "N kilos texto": "2 kilos", "3kilos organicos"
    m0 = re.match(r"^(\d+(?:[.,]\d+)?)\s*kilos?(?:\s.*)?$", s)
    if m0:
        n = float(m0.group(1).replace(",", "."))
        return "1K" if n == 1 else (f"{int(n)}K" if n == int(n) else f"{n}K")

    # Standard: "500g", "1 kg", "360cc", "2l" — with optional trailing text
    # Covers "1KG Organica" → 1K, "X12U VIRGEN 360cc" → 12U, then 360C via embedded
    m = re.match(
        r"^(\d+(?:[.,]\d+)?)\s*(kg|kgs|k|gr|grs|g|gramos|ml|cc|l|litros?|u|unidades?|paquetes?)(?:\s.*)?$",
        s,
    )
    if m:
        n = float(m.group(1).replace(",", "."))
        u = m.group(2).lower().rstrip("s")
        if u in ["kg", "kgs", "k"]:
            return "1K" if n == 1 else (f"{int(n)}K" if n == int(n) else f"{n}K")
        elif u in ["g", "gr", "grs", "gramo"]:
            return f"{int(n)}G"
        elif u == "ml":
            return f"{int(n)}ML"
        elif u == "cc":
            return f"{int(n)}C"
        elif u in ["l", "litro"]:
            return "1L" if n == 1 else f"{int(n)}L"
        else:
            return "1U" if n == 1 else f"{int(n)}U"

    # Embedded quantity anywhere: "DDL SIN FRUCTOSA 400gr", "Palta Hass en Trozos x 250gr"
    m_emb = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(kg|kgs|kilos?|gr|grs|g|gramos|ml|cc|l|litros?)(?:\b|$)",
        s,
    )
    if m_emb:
        n = float(m_emb.group(1).replace(",", "."))
        u = m_emb.group(2).lower().rstrip("s")
        if u in ["kg", "kilo"]:
            return "1K" if n == 1 else (f"{int(n)}K" if n == int(n) else f"{n}K")
        elif u in ["g", "gr", "grs", "gramo"]:
            return f"{int(n)}G"
        elif u == "ml":
            return f"{int(n)}ML"
        elif u == "cc":
            return f"{int(n)}C"
        elif u in ["l", "litro"]:
            return "1L" if n == 1 else f"{int(n)}L"

    if "granel" in s:
        return "GRL"
    return "1U"


def previsualizar(archivo_path, tipo):
    """Retorna lista de dicts para mostrar en la tabla de preview."""
    df = _leer_archivo(archivo_path, tipo)
    rows = []
    seen_ids = set()
    for _, row in df.iterrows():
        if pd.isna(row.get("ID")):
            continue
        pid = str(row["ID"])
        if pid in seen_ids:
            continue
        seen_ids.add(pid)
        cat = row.get("Categoría") or row.get("Categoria", "")
        if _debe_omitir(cat):
            continue
        codigo = _mapear_categoria(cat)
        rows.append({
            "nombre": str(row.get("Nombre", "") or ""),
            "categoria_pedix": str(cat),
            "codigo_sku": codigo or "—",
        })
    return rows[:50]


def _procesar_variantes(session, nombre_base, variantes, pres_codigo,
                        categoria_id, grupo, existentes_bd, existentes_sesion):
    """
    Para cada variante de nombre (sabor), crea el producto "{nombre_base} {variante}"
    si no existe, o le agrega la presentación si ya existe.
    Retorna (importados, errores).
    """
    from services.product_service import editar_producto

    importados = 0
    errores = []

    for variante in variantes:
        nombre_v = f"{nombre_base} {variante}".strip()
        nombre_v_n = _norm(nombre_v)

        if nombre_v_n in existentes_bd or nombre_v_n in existentes_sesion:
            # El producto ya existe → agregarle la presentación si no la tiene
            prod = session.query(Producto).filter(
                Producto.nombre.ilike(nombre_v)
            ).first()
            if not prod:
                # Búsqueda por normalización
                todos = session.query(Producto).filter_by(categoria_id=categoria_id).all()
                prod = next((p for p in todos if _norm(p.nombre) == nombre_v_n), None)

            if prod:
                skus_actuales = {s.presentacion for s in prod.skus}
                if pres_codigo not in skus_actuales:
                    try:
                        editar_producto(session, prod.id, prod.nombre, prod.grupo,
                                        [pres_codigo], [])
                        importados += 1
                    except Exception as e:
                        errores.append({
                            "nombre": nombre_v,
                            "motivo": f"Error agregando presentación {pres_codigo}: {e}",
                            "puede_forzar": False,
                        })
            # Si no encontramos el producto en la BD, no podemos hacer nada
        else:
            # Crear producto nuevo
            try:
                crear_producto(session, nombre_v, categoria_id, [pres_codigo], grupo=grupo)
                existentes_sesion.add(nombre_v_n)
                existentes_bd.add(nombre_v_n)
                importados += 1
            except Exception as e:
                errores.append({
                    "nombre": nombre_v,
                    "motivo": str(e),
                    "puede_forzar": False,
                })

    return importados, errores


def escanear_categorias_sin_mapeo(archivo_path):
    """
    Lee el archivo y retorna lista de categorías Pedix que no tienen mapeo,
    sin duplicados, ordenadas alfabéticamente.
    """
    df = _leer_archivo(archivo_path, None)
    sin_mapeo = set()
    for _, row in df.iterrows():
        if pd.isna(row.get("ID")):
            continue
        cat = row.get("Categoría") or row.get("Categoria", "")
        if not cat or _debe_omitir(cat):
            continue
        if _mapear_categoria(cat) is None:
            sin_mapeo.add(str(cat).strip())
    return sorted(sin_mapeo)


def importar_desde_pedix(session, archivo_path, tipo, extra_map=None, forzar_nombres=None):
    """
    Importa productos desde un Excel de Pedix.

    extra_map: dict {categoria_pedix: codigo_sku} asignado por el usuario
               para categorías sin mapeo automático.
    forzar_nombres: set de nombres normalizados que deben importarse aunque
                    ya existan en la BD (el usuario eligió reimportar).

    Retorna (importados, omitidos_detalle, errores).
    omitidos_detalle es una lista de dicts: {"nombre", "motivo", "puede_forzar"}
    """
    extra_map = extra_map or {}
    forzar_nombres = forzar_nombres or set()

    df = _leer_archivo(archivo_path, tipo)

    pres_col = next(
        (c for c in df.columns if "resentaci" in _norm(c) and "nombre" in _norm(c)), None
    )
    sku_col = next(
        (c for c in df.columns if "digo" in _norm(c) and "sku" in _norm(c)), None
    )

    existentes_bd = {_norm(p.nombre) for p in session.query(Producto).all()}
    existentes_sesion = set()

    importados = 0
    omitidos = []
    errores = []
    filas = df.reset_index(drop=True)

    # ── Fase 0: recolectar todos los bloques del archivo ─────────────────
    blocks = []
    i = 0
    while i < len(filas):
        row = filas.iloc[i]
        if pd.isna(row.get("ID")):
            i += 1
            continue

        cat = str(row.get("Categoría") or row.get("Categoria", "") or "").strip()
        nombre_raw = str(row.get("Nombre", "") or "").strip()

        if _debe_omitir(cat) or not nombre_raw or "(Copia)" in nombre_raw:
            i += 1
            continue

        nombre, embedded_pres = _extraer_pres_de_nombre(nombre_raw)

        # Recolectar sub-filas (presentaciones + SKUs de Pedix)
        sub_textos = []
        sub_skus = []
        j = i
        while j < len(filas):
            sub = filas.iloc[j]
            if j > i and pd.notna(sub.get("ID")):
                break
            if pres_col:
                pres_val = sub.get(pres_col)
                if pd.notna(pres_val):
                    sub_textos.append(str(pres_val).strip())
                    sku_val = sub.get(sku_col) if sku_col else None
                    sub_skus.append(str(sku_val).strip() if pd.notna(sku_val) and sku_val else None)
            j += 1

        sku_base_pedix = None
        for s in sub_skus:
            if s and "-" in s:
                sku_base_pedix = s.split("-")[0].strip().upper()
                break

        blocks.append({
            "nombre": nombre,
            "nombre_n": _norm(nombre),
            "cat": cat,
            "embedded_pres": embedded_pres,
            "sub_textos": sub_textos,
            "sub_skus": sub_skus,
            "sku_base_pedix": sku_base_pedix,
        })
        i = j

    # ── Fase 1: procesar — primero los que tienen SKU en Pedix ───────────
    # Así el generador secuencial nunca ocupa un número ya reservado en Pedix.
    blocks_ordenados = (
        [b for b in blocks if b["sku_base_pedix"]] +
        [b for b in blocks if not b["sku_base_pedix"]]
    )

    for block in blocks_ordenados:
        nombre        = block["nombre"]
        nombre_n      = block["nombre_n"]
        cat           = block["cat"]
        embedded_pres = block["embedded_pres"]
        sub_textos    = list(block["sub_textos"])
        sub_skus      = list(block["sub_skus"])
        sku_base_pedix = block["sku_base_pedix"]

        # Duplicado en el archivo (mismo producto en otra categoría)
        if nombre_n in existentes_sesion:
            omitidos.append({
                "nombre": nombre,
                "motivo": f"Duplicado en el archivo (misma nombre en otra categoría: «{cat}»)",
                "puede_forzar": False,
            })
            continue

        # Ya existe en la BD — intentar agregar presentaciones nuevas
        if nombre_n in existentes_bd and nombre_n not in forzar_nombres:
            if sub_textos and not all(_es_variante_nombre(t) for t in sub_textos):
                from services.product_service import editar_producto
                prod = session.query(Producto).filter(
                    Producto.nombre.ilike(nombre)
                ).first()
                if prod:
                    skus_actuales = {s.presentacion for s in prod.skus}
                    nuevas = []
                    for p, s in zip(sub_textos, sub_skus):
                        pc = s.split("-", 1)[1].strip().upper() if s and "-" in s else _pres_code(p)
                        if pc not in skus_actuales and pc not in nuevas:
                            nuevas.append(pc)
                            agregar_presentacion_global(session, pc)
                    if nuevas:
                        try:
                            editar_producto(session, prod.id, prod.nombre, prod.grupo, nuevas, [])
                            importados += 1
                        except Exception as e:
                            errores.append({
                                "nombre": nombre,
                                "motivo": f"Error al agregar presentaciones nuevas: {e}",
                                "puede_forzar": False,
                            })
                    else:
                        omitidos.append({
                            "nombre": nombre,
                            "motivo": "Ya existe con las mismas presentaciones",
                            "puede_forzar": False,
                        })
                else:
                    omitidos.append({
                        "nombre": nombre,
                        "motivo": "Ya existe en la base de datos",
                        "puede_forzar": True,
                    })
            else:
                omitidos.append({
                    "nombre": nombre,
                    "motivo": "Ya existe en la base de datos",
                    "puede_forzar": True,
                })
            continue

        # Buscar código de categoría
        codigo_cat = _mapear_categoria(cat) or extra_map.get(cat)
        if not codigo_cat:
            omitidos.append({
                "nombre": nombre,
                "motivo": f"Categoría sin mapeo: «{cat}»",
                "puede_forzar": False,
            })
            continue

        categoria = session.query(Categoria).filter_by(codigo=codigo_cat).first()
        if not categoria:
            omitidos.append({
                "nombre": nombre,
                "motivo": f"Código de categoría no encontrado en la BD: {codigo_cat}",
                "puede_forzar": False,
            })
            continue

        grupo = cat
        modo_variantes = bool(sub_textos) and all(_es_variante_nombre(t) for t in sub_textos)

        if modo_variantes:
            pres_peso = _pres_code(embedded_pres) if embedded_pres else "1U"
            agregar_presentacion_global(session, pres_peso)
            n_imp, n_err = _procesar_variantes(
                session, nombre, sub_textos, pres_peso,
                categoria.id, grupo,
                existentes_bd, existentes_sesion,
            )
            importados += n_imp
            errores.extend(n_err)
            existentes_sesion.add(nombre_n)

        else:
            if not sub_textos:
                sub_textos = [embedded_pres] if embedded_pres else [None]
                sub_skus = [None]

            seen_p = set()
            codigos_pres = []
            for p, s in zip(sub_textos, sub_skus):
                pc = s.split("-", 1)[1].strip().upper() if s and "-" in s else _pres_code(p)
                if pc not in seen_p:
                    seen_p.add(pc)
                    codigos_pres.append(pc)
                    agregar_presentacion_global(session, pc)

            try:
                crear_producto(session, nombre, categoria.id, codigos_pres,
                               grupo=grupo, sku_base_override=sku_base_pedix)
                existentes_sesion.add(nombre_n)
                existentes_bd.add(nombre_n)
                importados += 1
            except Exception as e:
                errores.append({"nombre": nombre, "motivo": str(e), "puede_forzar": False})

    return importados, omitidos, errores


def _leer_archivo(archivo_path, tipo):
    xl = pd.ExcelFile(archivo_path)
    sheet = "Productos" if "Productos" in xl.sheet_names else xl.sheet_names[0]
    return pd.read_excel(archivo_path, sheet_name=sheet, header=0)
