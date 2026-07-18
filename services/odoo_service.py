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


def subir_skus(url, db, uid, password, skus):
    """
    Sube SKUs a Odoo usando el sistema de variantes:
    - Un product.template por Producto (nombre base)
    - Un product.product (variante) por presentación
    - default_code se asigna a nivel de variante (product.product)
    Retorna (creados, actualizados, errores).
    """
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    attr_id = _get_or_create_attribute(models, db, uid, password)

    # Agrupar SKUs por Producto
    productos_map: dict = {}
    for sku in skus:
        pid = sku.producto_id
        if pid not in productos_map:
            productos_map[pid] = {"producto": sku.producto, "skus": []}
        productos_map[pid]["skus"].append(sku)

    creados, actualizados, errores = 0, 0, []

    for data in productos_map.values():
        producto = data["producto"]
        skus_grupo = data["skus"]

        try:
            # Obtener o crear valores de atributo para cada presentación
            pres_to_pav: dict[str, int] = {}
            for sku in skus_grupo:
                pres_to_pav[sku.presentacion] = _get_or_create_attr_value(
                    models, db, uid, password, attr_id, sku.presentacion)

            # Obtener o crear product.template
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
                creados += 1

            # Obtener o actualizar la línea de atributo "Presentación" en el template
            line_ids = models.execute_kw(db, uid, password,
                "product.template.attribute.line", "search",
                [[["product_tmpl_id", "=", tmpl_id], ["attribute_id", "=", attr_id]]])

            nuevos_pav_ids = list(pres_to_pav.values())

            if line_ids:
                line_data = models.execute_kw(db, uid, password,
                    "product.template.attribute.line", "read",
                    [line_ids], {"fields": ["value_ids"]})[0]
                existentes = set(line_data["value_ids"])
                for pav_id in nuevos_pav_ids:
                    if pav_id not in existentes:
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

            # Asignar default_code a cada variante
            for sku in skus_grupo:
                pav_id = pres_to_pav[sku.presentacion]
                variant_id = _find_variant_for_value(models, db, uid, password, tmpl_id, pav_id)
                if variant_id:
                    models.execute_kw(db, uid, password, "product.product", "write",
                        [[variant_id], {"default_code": sku.sku}])
                    if not es_nuevo:
                        actualizados += 1
                else:
                    errores.append(f"{sku.sku}: variante no encontrada en Odoo tras creación")

        except Exception as e:
            errores.append(f"{producto.nombre}: {e}")

    return creados, actualizados, errores
