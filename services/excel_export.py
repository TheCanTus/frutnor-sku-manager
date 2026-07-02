import pandas as pd

from database.models import SKU


def exportar_excel(session, archivo):

    registros = (
        session.query(SKU)
        .order_by(SKU.sku)
        .all()
    )

    datos = []

    for sku in registros:

        datos.append({
            "Category": sku.producto.categoria.codigo,
            "SKU Base": sku.producto.sku_base,
            "Internal Reference": sku.sku,
            "Name": sku.producto.nombre,
            "Presentation": sku.presentacion
        })

    df = pd.DataFrame(datos)

    df.to_excel(
        archivo,
        index=False
    )