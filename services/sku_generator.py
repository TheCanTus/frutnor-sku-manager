from sqlalchemy import func

from database.models import Producto


def generar_sku_base(session, codigo_categoria):

    ultimo = (
        session.query(
            func.max(
                Producto.correlativo
            )
        )
        .filter(
            Producto.sku_base.like(
                f"{codigo_categoria}%"
            )
        )
        .scalar()
    )

    if ultimo is None:
        ultimo = 0

    nuevo = ultimo + 1

    return (
        nuevo,
        f"{codigo_categoria}{nuevo:03d}"
    )