from database.models import Producto, SKU, Categoria, Presentacion
from services.sku_generator import generar_sku_base


def crear_producto(session, nombre, categoria_id, presentaciones, grupo=None, sku_base_override=None):
    import re as _re
    if not nombre.strip():
        raise ValueError("El nombre del producto no puede estar vacío")
    if not presentaciones:
        raise ValueError("Debe seleccionar al menos una presentación")

    categoria = session.query(Categoria).filter_by(id=categoria_id).first()
    if not categoria:
        raise ValueError("Categoría no encontrada")

    if sku_base_override:
        sku_base = sku_base_override.strip().upper()
        already_taken = session.query(Producto).filter_by(sku_base=sku_base).first()
        if already_taken:
            correlativo, sku_base = generar_sku_base(session, categoria.codigo)
        else:
            m = _re.match(r'^[A-Z]+(\d+)$', sku_base)
            correlativo = int(m.group(1)) if m else 0
    else:
        correlativo, sku_base = generar_sku_base(session, categoria.codigo)

    producto = Producto(
        nombre=nombre.strip(),
        grupo=grupo.strip() if grupo else categoria.nombre,
        categoria_id=categoria_id,
        correlativo=correlativo,
        sku_base=sku_base,
    )
    session.add(producto)
    session.flush()

    for pres in presentaciones:
        session.add(SKU(
            producto_id=producto.id,
            presentacion=pres,
            sku=f"{sku_base}-{pres}",
        ))

    session.commit()
    return producto


def editar_producto(session, producto_id, nombre, grupo, agregar_pres, quitar_pres):
    producto = session.query(Producto).filter_by(id=producto_id).first()
    if not producto:
        raise ValueError("Producto no encontrado")
    if not nombre.strip():
        raise ValueError("El nombre no puede estar vacío")

    producto.nombre = nombre.strip()
    producto.grupo = grupo.strip() if grupo else producto.grupo

    for pres in quitar_pres:
        sku = session.query(SKU).filter_by(
            producto_id=producto_id, presentacion=pres
        ).first()
        if sku:
            session.delete(sku)

    skus_actuales = {s.presentacion for s in producto.skus}
    for pres in agregar_pres:
        if pres not in skus_actuales:
            session.add(SKU(
                producto_id=producto_id,
                presentacion=pres,
                sku=f"{producto.sku_base}-{pres}",
            ))

    session.commit()
    return producto


def eliminar_producto(session, producto_id):
    producto = session.query(Producto).filter_by(id=producto_id).first()
    if not producto:
        raise ValueError("Producto no encontrado")
    session.delete(producto)
    session.commit()


def agregar_presentacion_global(session, codigo, descripcion=""):
    """Agrega una nueva presentación a la tabla de lookup si no existe."""
    existe = session.query(Presentacion).filter_by(codigo=codigo.upper()).first()
    if not existe:
        session.add(Presentacion(codigo=codigo.upper(), descripcion=descripcion))
        session.commit()


def agregar_presentaciones_granel(session):
    """
    Agrega SKU con presentación GRL a todos los productos que tengan
    al menos una presentación de peso (\d+(G|KG|GR)) y aún no tengan GRL.
    Retorna lista de nombres de productos modificados.
    """
    import re
    _PESO = re.compile(r'^\d+(G|KG|GR)$', re.IGNORECASE)
    productos = session.query(Producto).all()
    agregados = []
    for prod in productos:
        codigos = {s.presentacion for s in prod.skus}
        if "GRL" in codigos:
            continue
        if not any(_PESO.match(c) for c in codigos):
            continue
        session.add(SKU(
            producto_id=prod.id,
            presentacion="GRL",
            sku=f"{prod.sku_base}-GRL",
        ))
        agregados.append(prod.nombre)
    session.commit()
    return agregados
