from database.db import SessionLocal
from database.models import Base, Categoria
from sqlalchemy import create_engine
from pathlib import Path

DB_PATH = Path(__file__).parent / "productos.db"
from database.db import engine
from database.models import Base
Base.metadata.create_all(bind=engine)

session = SessionLocal()

CATEGORIAS = [
    ("ACE", "Aceites Coco y Oliva"),
    ("ALM", "Almacén"),
    ("ALF", "Alfajores y Barras de Cereal"),
    ("AVN", "Avena, Semillas y Legumbres"),
    ("CER", "Cereales"),
    ("CEC", "Cereales Combos"),
    ("COC", "Condimentos Combo"),
    ("CON", "Condimentos 100% Puros"),
    ("CGD", "Congelados"),
    ("CHO", "Chocolatería"),
    ("FRC", "Frutos Secos y Disecados Combo"),
    ("FRU", "Frutos Secos y Disecados"),
    ("GRN", "Granolas"),
    ("HAR", "Harinas"),
    ("GRA", "Granger"),
    ("HOG", "Hogar / Bazar"),
    ("MIX", "Mix"),
    ("MIE", "Miel, Pastas, Mermeladas y DdL"),
    ("REP", "Repostería, Té y Endulzantes"),
    ("SAB", "Saborizados Frutos Secos"),
    ("SUP", "Suplementos"),
    ("YER", "Yerbas"),
    ("MAY", "Venta Mayorista"),
    ("YOG", "Yogurt Natural y Griego"),
    ("GEN", "Genérico / Canastas"),
    ("SGL", "Sin Gluten"),
]

for codigo, nombre in CATEGORIAS:
    existe = session.query(Categoria).filter_by(codigo=codigo).first()
    if not existe:
        session.add(Categoria(codigo=codigo, nombre=nombre))

session.commit()
session.close()
print(f"Categorías cargadas: {len(CATEGORIAS)}")
