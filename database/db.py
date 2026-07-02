from sqlalchemy import create_engine
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