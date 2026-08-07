import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.paths import get_app_dir


def _get_db_url():
    cfg_path = get_app_dir() / "config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            url = cfg.get("db_url", "").strip()
            if url:
                return url
        except Exception:
            pass
    return f"sqlite:///{get_app_dir() / 'productos.db'}"


DATABASE_URL = _get_db_url()

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    # Migraciones SQLite legacy (solo aplica en modo local)
    from sqlalchemy import text
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
else:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
