from sqlalchemy import func, text

from database.models import Producto


def generar_sku_base(session, codigo_categoria):
    """
    Genera el próximo correlativo para una categoría.
    Usa SELECT FOR UPDATE en PostgreSQL para evitar colisiones entre usuarios simultáneos.
    En SQLite usa MAX() simple (no hay concurrencia real).
    """
    dialect = session.bind.dialect.name if session.bind else "sqlite"

    if dialect == "postgresql":
        # Bloquea las filas de esta categoría hasta que termine el INSERT
        ultimo = (
            session.query(func.max(Producto.correlativo))
            .filter(Producto.sku_base.like(f"{codigo_categoria}%"))
            .with_for_update()
            .scalar()
        )
    else:
        ultimo = (
            session.query(func.max(Producto.correlativo))
            .filter(Producto.sku_base.like(f"{codigo_categoria}%"))
            .scalar()
        )

    if ultimo is None:
        ultimo = 0

    nuevo = ultimo + 1
    return nuevo, f"{codigo_categoria}{nuevo:03d}"
