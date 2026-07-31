import json
import re as _re
import xmlrpc.client

ATTR_PRESENTACION = "Presentación"


def conectar(url, db, user, password):
    """Autentica contra Odoo. Retorna uid o lanza excepción."""
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})
    if not uid:
        raise ValueError("Credenciales incorrectas o base de datos no encontrada.")
    return uid


def listar_skus_odoo(url, db, uid, password):
    """Retorna lista de default_code de todos los product.product (variantes) en Odoo."""
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    records = models.execute_kw(
        db, uid, password,
        "product.product", "search_read",
        [[["default_code", "!=", False]]],
        {"fields": ["default_code"]},
    )
    return [r["default_code"] for r in records if r.get("default_code")]


def listar_websites(url, db, uid, password):
    """Retorna lista de dicts {id, name, domain} con los sitios web de Odoo."""
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return models.execute_kw(
        db, uid, password, "website.website", "search_read",
        [[]],
        {"fields": ["id", "name", "domain"]},
    )


def _get_or_create_attribute(models, db, uid, password):
    """Obtiene o crea el atributo 'Presentación'."""
    ids = models.execute_kw(db, uid, password, "product.attribute", "search",
        [[["name", "=", ATTR_PRESENTACION]]])
    if ids:
        return ids[0]
    return models.execute_kw(db, uid, password, "product.attribute", "create", [{
        "name": ATTR_PRESENTACION,
        "create_variant": "always",
        "display_type": "select",
    }])


def _get_or_create_attr_value(models, db, uid, password, attr_id, name):
    """Obtiene o crea un valor del atributo Presentación."""
    ids = models.execute_kw(db, uid, password, "product.attribute.value", "search",
        [[["name", "=", name], ["attribute_id", "=", attr_id]]])
    if ids:
        return ids[0]
    return models.execute_kw(db, uid, password, "product.attribute.value", "create", [{
        "name": name,
        "attribute_id": attr_id,
    }])


def _find_variant_for_value(models, db, uid, password, tmpl_id, pav_id):
    """
    Encuentra el product.product (variante) de un template que corresponde
    a un product.attribute.value específico.
    """
    variants = models.execute_kw(db, uid, password, "product.product", "search_read",
        [[["product_tmpl_id", "=", tmpl_id]]],
        {"fields": ["id", "product_template_attribute_value_ids"]})

    if not variants:
        return None

    all_ptav_ids = []
    for v in variants:
        all_ptav_ids.extend(v["product_template_attribute_value_ids"])

    if not all_ptav_ids:
        return None

    ptav_records = models.execute_kw(db, uid, password,
        "product.template.attribute.value", "read",
        [all_ptav_ids], {"fields": ["id", "product_attribute_value_id"]})
    ptav_to_pav = {p["id"]: p["product_attribute_value_id"][0] for p in ptav_records}

    for variant in variants:
        for ptav_id in variant["product_template_attribute_value_ids"]:
            if ptav_to_pav.get(ptav_id) == pav_id:
                return variant["id"]
    return None


def _set_variant_price_extra(models, db, uid, password, tmpl_id, pav_id, price_extra):
    """Fija price_extra en el product.template.attribute.value correspondiente."""
    ptav_ids = models.execute_kw(db, uid, password,
        "product.template.attribute.value", "search",
        [[["product_tmpl_id", "=", tmpl_id],
          ["product_attribute_value_id", "=", pav_id]]])
    if ptav_ids:
        models.execute_kw(db, uid, password,
            "product.template.attribute.value", "write",
            [ptav_ids, {"price_extra": round(price_extra, 2)}])


def _get_or_create_public_category(models, db, uid, password, nombre, cache):
    """Busca o crea una product.public.category por nombre. Usa cache para evitar llamadas repetidas."""
    if nombre in cache:
        return cache[nombre]
    ids = models.execute_kw(db, uid, password, "product.public.category", "search",
        [[["name", "=ilike", nombre]]])
    categ_id = ids[0] if ids else models.execute_kw(
        db, uid, password, "product.public.category", "create", [{"name": nombre}])
    cache[nombre] = categ_id
    return categ_id


def _get_or_create_granel_template(models, db, uid, password, nombre, sku_code):
    """Crea o recupera el product.template de granel (storable, sin variantes, sin website)."""
    nombre_granel = f"{nombre} - Granel"
    ids = models.execute_kw(db, uid, password, "product.template", "search",
        [[["name", "=", nombre_granel]]])
    if ids:
        tmpl_id = ids[0]
        es_nuevo = False
    else:
        tmpl_id = models.execute_kw(db, uid, password, "product.template", "create", [{
            "name": nombre_granel,
        }])
        for type_val in ("product", "storable"):
            try:
                models.execute_kw(db, uid, password, "product.template", "write",
                    [[tmpl_id], {"type": type_val, "sale_ok": False}])
                break
            except Exception:
                continue
        es_nuevo = True
    variant_ids = models.execute_kw(db, uid, password, "product.product", "search",
        [[["product_tmpl_id", "=", tmpl_id]]])
    if variant_ids:
        models.execute_kw(db, uid, password, "product.product", "write",
            [[variant_ids[0]], {"default_code": sku_code}])
    return tmpl_id, es_nuevo


def subir_skus(url, db, uid, password, skus, solo_nuevos=False, website_ids=None):
    """
    Sube SKUs a Odoo:
    - Un product.template por (producto × tienda) con variantes por presentación.
      Todas las tiendas usan este flujo: minorista, mayorista y preventista.
    - Granel: un product.template compartido sin website_id.
    - website_ids: dict {tienda: odoo_website_id}
    Retorna (creados_web, actualizados_web, creados_granel, errores).
    """
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    if solo_nuevos:
        existentes = set(listar_skus_odoo(url, db, uid, password))
        # Los SKUs preventistas siempre se procesan: su template en el sitio preventista
        # puede no existir aunque el default_code ya esté asignado en otro template (minorista).
        skus = [
            s for s in skus
            if s.sku not in existentes
            or "preventista" in json.loads(s.tiendas or "[]")
        ]

    attr_id = _get_or_create_attribute(models, db, uid, password)

    # Agrupar: key=(producto_id, tienda) para web; key=(producto_id, None) para granel
    grupos: dict = {}
    for sku in skus:
        pid = sku.producto_id
        if sku.presentacion == "GRL":
            key = (pid, None)
            grupos.setdefault(key, {"producto": sku.producto, "web": [], "granel": None})
            grupos[key]["granel"] = sku
        else:
            tiendas_list = json.loads(sku.tiendas or '["minorista"]')
            for tienda in tiendas_list:
                key = (pid, tienda)
                grupos.setdefault(key, {"producto": sku.producto, "web": [], "granel": None})
                grupos[key]["web"].append(sku)

    creados_web, actualizados_web, creados_granel, errores = 0, 0, 0, []
    categ_cache: dict = {}

    for (pid, tienda), data in grupos.items():
        producto = data["producto"]
        web_skus = data["web"]
        granel_sku = data["granel"]

        try:
            # ── Template con variantes (todas las tiendas: minorista, mayorista, preventista) ──
            if tienda and web_skus:
                pres_to_pav: dict[str, int] = {}
                for sku in web_skus:
                    pres_to_pav[sku.presentacion] = _get_or_create_attr_value(
                        models, db, uid, password, attr_id, sku.presentacion)

                wid = (website_ids or {}).get(tienda)
                domain = [["name", "=", producto.nombre]]
                if wid:
                    domain.append(["website_id", "=", wid])
                tmpl_ids = models.execute_kw(db, uid, password, "product.template", "search", [domain])

                if tmpl_ids:
                    tmpl_id = tmpl_ids[0]
                    es_nuevo = False
                else:
                    create_vals = {"name": producto.nombre, "sale_ok": True}
                    if wid:
                        create_vals["website_id"] = wid
                    tmpl_id = models.execute_kw(db, uid, password, "product.template", "create",
                        [create_vals])
                    # Odoo 17+: "storable" | Odoo ≤16: "product"
                    for type_val in ("storable", "product"):
                        try:
                            models.execute_kw(db, uid, password, "product.template", "write",
                                [[tmpl_id], {"type": type_val}])
                            break
                        except Exception:
                            continue
                    es_nuevo = True
                    creados_web += 1

                # Asignar categoría web
                cat = getattr(producto, "categoria", None)
                if cat and cat.nombre:
                    try:
                        categ_id = _get_or_create_public_category(
                            models, db, uid, password, cat.nombre, categ_cache)
                        models.execute_kw(db, uid, password, "product.template", "write",
                            [[tmpl_id], {"public_categ_ids": [(4, categ_id)]}])
                    except Exception as e:
                        errores.append(f"{producto.nombre}: no se pudo asignar categoría ({e})")

                line_ids = models.execute_kw(db, uid, password,
                    "product.template.attribute.line", "search",
                    [[["product_tmpl_id", "=", tmpl_id], ["attribute_id", "=", attr_id]]])

                nuevos_pav_ids = list(pres_to_pav.values())

                if line_ids:
                    line_data = models.execute_kw(db, uid, password,
                        "product.template.attribute.line", "read",
                        [line_ids], {"fields": ["value_ids"]})[0]
                    existentes_pav = set(line_data["value_ids"])
                    for pav_id in nuevos_pav_ids:
                        if pav_id not in existentes_pav:
                            models.execute_kw(db, uid, password,
                                "product.template.attribute.line", "write",
                                [line_ids, {"value_ids": [(4, pav_id)]}])
                else:
                    models.execute_kw(db, uid, password,
                        "product.template.attribute.line", "create", [{
                            "product_tmpl_id": tmpl_id,
                            "attribute_id": attr_id,
                            "value_ids": [(6, 0, nuevos_pav_ids)],
                        }])

                for sku in web_skus:
                    pav_id = pres_to_pav[sku.presentacion]
                    variant_id = _find_variant_for_value(models, db, uid, password, tmpl_id, pav_id)
                    if variant_id:
                        models.execute_kw(db, uid, password, "product.product", "write",
                            [[variant_id], {"default_code": sku.sku}])
                        if not es_nuevo:
                            actualizados_web += 1
                    else:
                        errores.append(f"{sku.sku}: variante no encontrada en Odoo tras creación")

                # Precios: list_price en template + price_extra por variante
                tienda_precios = {}
                for sku in web_skus:
                    p = json.loads(sku.precios or '{}')
                    precio = p.get(tienda)
                    if precio and float(precio) > 0:
                        tienda_precios[sku.presentacion] = float(precio)
                if tienda_precios:
                    base = min(tienda_precios.values())
                    models.execute_kw(db, uid, password, "product.template", "write",
                        [[tmpl_id], {"list_price": base}])
                    for sku in web_skus:
                        pav_id = pres_to_pav[sku.presentacion]
                        extra = tienda_precios.get(sku.presentacion, base) - base
                        _set_variant_price_extra(models, db, uid, password, tmpl_id, pav_id, extra)

            # ── Granel template (compartido, sin website_id) ──
            if granel_sku:
                _, es_nuevo_granel = _get_or_create_granel_template(
                    models, db, uid, password, producto.nombre, granel_sku.sku)
                if es_nuevo_granel:
                    creados_granel += 1

        except Exception as e:
            label = f"{producto.nombre}" + (f" [{tienda}]" if tienda else " [granel]")
            errores.append(f"{label}: {e}")

    return creados_web, actualizados_web, creados_granel, errores


def subir_precios(url, db, uid, password, skus, website_ids=None):
    """
    Actualiza list_price y price_extra en templates ya existentes en Odoo.
    No crea ni elimina templates ni variantes.
    Retorna (actualizados, sin_precio, errores).
    """
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    attr_id = _get_or_create_attribute(models, db, uid, password)

    grupos: dict = {}
    for sku in skus:
        if sku.presentacion == "GRL":
            continue
        tiendas_list = json.loads(sku.tiendas or '["minorista"]')
        for tienda in tiendas_list:
            key = (sku.producto_id, tienda)
            grupos.setdefault(key, {"producto": sku.producto, "web": []})
            grupos[key]["web"].append(sku)

    actualizados, sin_precio, errores = 0, 0, []

    for (pid, tienda), data in grupos.items():
        producto = data["producto"]
        web_skus = data["web"]

        tienda_precios = {}
        for sku in web_skus:
            p = json.loads(sku.precios or '{}')
            precio = p.get(tienda)
            if precio and float(precio) > 0:
                tienda_precios[sku.presentacion] = float(precio)

        if not tienda_precios:
            sin_precio += 1
            continue

        try:
            wid = (website_ids or {}).get(tienda)
            domain = [["name", "=", producto.nombre]]
            if wid:
                domain.append(["website_id", "=", wid])
            tmpl_ids = models.execute_kw(db, uid, password, "product.template", "search", [domain])
            if not tmpl_ids:
                errores.append(f"{producto.nombre} [{tienda}]: template no encontrado en Odoo")
                continue
            tmpl_id = tmpl_ids[0]

            pres_to_pav = {}
            for sku in web_skus:
                pres_to_pav[sku.presentacion] = _get_or_create_attr_value(
                    models, db, uid, password, attr_id, sku.presentacion)

            base = min(tienda_precios.values())
            models.execute_kw(db, uid, password, "product.template", "write",
                [[tmpl_id], {"list_price": base}])
            for sku in web_skus:
                pav_id = pres_to_pav[sku.presentacion]
                extra = tienda_precios.get(sku.presentacion, base) - base
                _set_variant_price_extra(models, db, uid, password, tmpl_id, pav_id, extra)
            actualizados += 1

        except Exception as e:
            errores.append(f"{producto.nombre} [{tienda}]: {e}")

    return actualizados, sin_precio, errores


# ─── BoMs ────────────────────────────────────────────────────────────────────

def _parse_kg(presentacion):
    """
    Convierte un código de presentación en kg.
    500G → 0.5  |  1K → 1.0  |  10X100G → 1.0  |  5X200G → 1.0
    Retorna None si no es presentación de peso (GRL, 1U, 360C, 3X200C, etc.)
    """
    p = str(presentacion).upper().strip()
    # Pack de gramos: NXsizeG (e.g. 10X100G = 10 × 100g = 1 kg)
    m_pack = _re.match(r'^(\d+)X(\d+(?:[.,]\d+)?)(G|K)$', p)
    if m_pack:
        n_units = int(m_pack.group(1))
        size = float(m_pack.group(2).replace(",", "."))
        grams = size if m_pack.group(3) == "G" else size * 1000
        return round(n_units * grams / 1000, 6)
    # Presentación simple: 500G, 1K, etc.
    m = _re.match(r'^(\d+(?:[.,]\d+)?)(G|K)$', p)
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    return round(n / 1000.0, 6) if m.group(2) == "G" else n


def _get_uom_kg(models, db, uid, password):
    """Busca el ID de la UoM 'kg' en Odoo."""
    for nombre in ["kg", "Kg", "KG"]:
        ids = models.execute_kw(db, uid, password, "uom.uom", "search",
            [[["name", "=", nombre]]])
        if ids:
            return ids[0]
    ids = models.execute_kw(db, uid, password, "uom.uom", "search",
        [[["name", "ilike", "kg"]]])
    return ids[0] if ids else None


def crear_boms(url, db, uid, password, skus, solo_nuevos=False):
    """
    Crea o actualiza BoMs en Odoo para presentaciones de peso (G/K).

    Por cada SKU de peso que tenga un granel (GRL) subido a Odoo:
      - Busca la variante web y la variante granel por default_code
      - Crea mrp.bom con 1 unidad producida y componente = granel con kg calculados
      - Si ya existe una BoM para esa variante: actualiza la línea de granel
        (omite si solo_nuevos=True)

    Retorna (creadas, actualizadas, omitidas, errores).
    """
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    uom_kg_id = _get_uom_kg(models, db, uid, password)

    creadas, actualizadas, omitidas = 0, 0, 0
    errores = []

    for sku in skus:
        if sku.presentacion == "GRL":
            continue

        kg = _parse_kg(sku.presentacion)
        if kg is None:
            continue

        try:
            # Variante del producto envasado
            web_vars = models.execute_kw(
                db, uid, password, "product.product", "search_read",
                [[["default_code", "=", sku.sku]]],
                {"fields": ["id", "product_tmpl_id"]},
            )
            if not web_vars:
                omitidas += 1
                continue
            web_variant_id = web_vars[0]["id"]
            tmpl_id = web_vars[0]["product_tmpl_id"][0]

            # Variante granel del mismo producto
            grl_code = f"{sku.producto.sku_base}-GRL"
            grl_vars = models.execute_kw(
                db, uid, password, "product.product", "search_read",
                [[["default_code", "=", grl_code]]],
                {"fields": ["id"]},
            )
            if not grl_vars:
                omitidas += 1
                continue
            grl_variant_id = grl_vars[0]["id"]

            line_vals = {"product_id": grl_variant_id, "product_qty": kg}
            if uom_kg_id:
                line_vals["product_uom_id"] = uom_kg_id

            # ¿Ya existe una BoM para esta variante?
            existing = models.execute_kw(
                db, uid, password, "mrp.bom", "search",
                [[["product_id", "=", web_variant_id]]],
            )

            if existing:
                if solo_nuevos:
                    omitidas += 1
                    continue
                bom_id = existing[0]
                # Buscar la línea de granel dentro de la BoM
                lines = models.execute_kw(
                    db, uid, password, "mrp.bom.line", "search",
                    [[["bom_id", "=", bom_id], ["product_id", "=", grl_variant_id]]],
                )
                if lines:
                    models.execute_kw(db, uid, password, "mrp.bom.line", "write",
                        [lines, {"product_qty": kg}])
                else:
                    models.execute_kw(db, uid, password, "mrp.bom.line", "create",
                        [{**line_vals, "bom_id": bom_id}])
                actualizadas += 1
            else:
                models.execute_kw(db, uid, password, "mrp.bom", "create", [{
                    "product_tmpl_id": tmpl_id,
                    "product_id": web_variant_id,
                    "product_qty": 1,
                    "type": "normal",
                    "bom_line_ids": [(0, 0, line_vals)],
                }])
                creadas += 1

        except Exception as e:
            errores.append(f"{sku.sku}: {e}")

    return creadas, actualizadas, omitidas, errores
