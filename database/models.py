from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(3), unique=True)
    nombre = Column(String)


class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True)

    nombre = Column(String)

    grupo = Column(String)

    categoria_id = Column(
        Integer,
        ForeignKey("categorias.id")
    )

    categoria = relationship("Categoria")

    correlativo = Column(Integer)

    sku_base = Column(
        String,
        unique=True
    )

    fecha_creacion = Column(
        DateTime,
        default=datetime.now
    )

    skus = relationship(
        "SKU",
        back_populates="producto",
        cascade="all, delete-orphan"
    )


class SKU(Base):
    __tablename__ = "skus"

    id = Column(Integer, primary_key=True)

    producto_id = Column(
        Integer,
        ForeignKey("productos.id")
    )

    presentacion = Column(String)

    sku = Column(
        String,
        unique=True
    )

    tiendas = Column(String, default='["minorista"]')

    producto = relationship(
        "Producto",
        back_populates="skus"
        )
    
class Presentacion(Base):
    __tablename__ = "presentaciones"

    id = Column(
        Integer,
        primary_key=True
    )

    codigo = Column(
        String,
        unique=True,
        nullable=False
    )

    descripcion = Column(
        String
    )