from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.paths import get_app_dir

DB_PATH = get_app_dir() / "productos.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def _migraciones():
    """Aplica columnas nuevas que no existen en la DB actual."""
    with engine.connect() as conn:
        cols_skus = {row[1] for row in conn.execute(text("PRAGMA table_info(skus)")).fetchall()}
        if "precios" not in cols_skus:
            conn.execute(text("ALTER TABLE skus ADD COLUMN precios TEXT DEFAULT '{}'"))
            conn.commit()

        cols_prod = {row[1] for row in conn.execute(text("PRAGMA table_info(productos)")).fetchall()}
        if "stock" not in cols_prod:
            conn.execute(text("ALTER TABLE productos ADD COLUMN stock REAL"))
            conn.commit()
        if "stock_unidad" not in cols_prod:
            conn.execute(text("ALTER TABLE productos ADD COLUMN stock_unidad TEXT DEFAULT 'kg'"))
            conn.commit()


_migraciones()