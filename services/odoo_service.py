import xmlrpc.client


def listar_skus_odoo(url, db, uid, password):
    """Retorna lista de default_code de todos los product.template en Odoo."""
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    ids = models.execute_kw(
        db, uid, password,
        "product.template", "search",
        [[["default_code", "!=", False]]],
    )
    if not ids:
        return []
    records = models.execute_kw(
        db, uid, password,
        "product.template", "read",
        [ids], {"fields": ["default_code"]},
    )
    return [r["default_code"] for r in records if r.get("default_code")]


def conectar(url, db, user, password):
    """Autentica contra Odoo. Retorna uid o lanza excepción."""
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})
    if not uid:
        raise ValueError("Credenciales incorrectas o base de datos no encontrada.")
    return uid


def subir_skus(url, db, uid, password, skus):
    """
    Sube una lista de objetos SKU a Odoo como product.template.
    Retorna (creados, actualizados, errores).
    """
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    creados, actualizados, errores = 0, 0, []

    for sku in skus:
        nombre_odoo = f"{sku.producto.nombre} {sku.presentacion}"
        default_code = sku.sku

        vals = {
            "name": nombre_odoo,
            "default_code": default_code,
            "type": "consu",
        }

        try:
            existing = models.execute_kw(
                db, uid, password,
                "product.template", "search",
                [[["default_code", "=", default_code]]],
            )
            if existing:
                models.execute_kw(
                    db, uid, password,
                    "product.template", "write",
                    [existing, {"name": nombre_odoo}],
                )
                actualizados += 1
            else:
                models.execute_kw(
                    db, uid, password,
                    "product.template", "create",
                    [vals],
                )
                creados += 1
        except Exception as e:
            errores.append(f"{default_code}: {e}")

    return creados, actualizados, errores
