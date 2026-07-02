from database.db import SessionLocal, engine
from database.models import Base, Presentacion

Base.metadata.create_all(bind=engine)
session = SessionLocal()

PRESENTACIONES = [
    ("1U",    "1 Unidad"),
    ("3U",    "3 Unidades"),
    ("6U",    "6 Unidades"),
    ("50G",   "50 Gramos"),
    ("100G",  "100 Gramos"),
    ("250G",  "250 Gramos"),
    ("500G",  "500 Gramos"),
    ("800G",  "800 Gramos"),
    ("1K",    "1 Kilogramo"),
    ("2K",    "2 Kilogramos"),
    ("5K",    "5 Kilogramos"),
    ("10K",   "10 Kilogramos"),
    ("15K",   "15 Kilogramos"),
    ("25K",   "25 Kilogramos"),
    ("30K",   "30 Kilogramos"),
    ("GRL",   "Granel"),
    ("SET",   "Set / Kit"),
    ("1L",    "1 Litro"),
    ("2L",    "2 Litros"),
    ("500ML", "500 Mililitros"),
    ("200C",  "200 cc"),
    ("360C",  "360 cc"),
    ("1K5",   "1,5 Kilogramos"),
    ("NAT",   "Natural"),
    ("VAI",   "Vainilla"),
    ("FRRJ",  "Frutos Rojos"),
    ("LECH",  "Leche"),
    ("BLCK",  "Black"),
    ("BLAN",  "Blanca"),
]

for codigo, descripcion in PRESENTACIONES:
    existe = session.query(Presentacion).filter_by(codigo=codigo).first()
    if not existe:
        session.add(Presentacion(codigo=codigo, descripcion=descripcion))

session.commit()
session.close()
print(f"Presentaciones cargadas: {len(PRESENTACIONES)}")
