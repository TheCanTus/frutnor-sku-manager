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


def _get_or_create_granel_template(models, db, uid, password, nombre, sku_code):
    """Crea o recupera el product.template de granel (storable, sin variantes)."""
    nombre_granel = f"{nombre} - Granel"
    ids = models.execute_kw(db, uid, password, "product.template", "search",
        [[["name", "=", nombre_granel]]])
    if ids:
        tmpl_id = ids[0]
        es_nuevo = False
    else:
        tmpl_id = models.execute_kw(db, uid, password, "product.template", "create", [{
            "name": nombre_granel,
            "type": "product",
            "sale_ok": False,
        }])
        es_nuevo = True
    variant_ids = models.execute_kw(db, uid, password, "product.product", "search",
        [[["product_tmpl_id", "=", tmpl_id]]])
    if variant_ids:
        models.execute_kw(db, uid, password, "product.product", "write",
            [[variant_ids[0]], {"default_code": sku_code}])
    return tmpl_id, es_nuevo


def subir_skus(url, db, uid, password, skus, solo_nuevos=False):
    """
    Sube SKUs a Odoo usando el sistema de variantes:
    - Un product.template web por Producto (con variantes por presentación)
    - Un product.template granel separado para productos con presentación GRL (storable)
    - default_code se asigna a nivel de variante (product.product)
    Retorna (creados_web, actualizados_web, creados_granel, errores).
    """
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    # Paso 0: filtrar solo los que no están en Odoo
    if solo_nuevos:
        existentes = set(listar_skus_odoo(url, db, uid, password))
        skus = [s for s in skus if s.sku not in existentes]

    attr_id = _get_or_create_attribute(models, db, uid, password)

    # Paso A: agrupar por producto separando GRL del resto
    productos_map: dict = {}
    for sku in skus:
        pid = sku.producto_id
        if pid not in productos_map:
            productos_map[pid] = {"producto": sku.producto, "web": [], "granel": None}
        if sku.presentacion == "GRL":
            productos_map[pid]["granel"] = sku
        else:
            productos_map[pid]["web"].append(sku)

    creados_web, actualizados_web, creados_granel, errores = 0, 0, 0, []

    for data in productos_map.values():
        producto = data["producto"]
        web_skus = data["web"]
        granel_sku = data["granel"]

        try:
            # ── Web template (con variantes por presentación) ──
            if web_skus:
                pres_to_pav: dict[str, int] = {}
                for sku in web_skus:
                    pres_to_pav[sku.presentacion] = _get_or_create_attr_value(
                        models, db, uid, password, attr_id, sku.presentacion)

                tmpl_ids = models.execute_kw(db, uid, password, "product.template", "search",
                    [[["name", "=", producto.nombre]]])

                if tmpl_ids:
                    tmpl_id = tmpl_ids[0]
                    es_nuevo = False
                else:
                    tmpl_id = models.execute_kw(db, uid, password, "product.template", "create", [{
                        "name": producto.nombre,
                        "type": "consu",
                        "sale_ok": True,
                    }])
                    es_nuevo = True
                    creados_web += 1

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

            # ── Granel template (storable, sin variantes) ──
            if granel_sku:
                _, es_nuevo_granel = _get_or_create_granel_template(
                    models, db, uid, password, producto.nombre, granel_sku.sku)
                if es_nuevo_granel:
                    creados_granel += 1

        except Exception as e:
            errores.append(f"{producto.nombre}: {e}")

    return creados_web, actualizados_web, creados_granel, errores
