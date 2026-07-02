import sys
from sqlalchemy import text

from PySide6.QtWidgets import QApplication

from database.db import engine
from database.models import Base

from ui.main_window import MainWindow


Base.metadata.create_all(bind=engine)

# Migración: agregar columna 'grupo' si no existe (SQLite no la crea con create_all)
with engine.connect() as conn:
    cols = [row[1] for row in conn.execute(text("PRAGMA table_info(productos)"))]
    if "grupo" not in cols:
        conn.execute(text("ALTER TABLE productos ADD COLUMN grupo VARCHAR"))
        conn.commit()

app = QApplication(sys.argv)

window = MainWindow()
window.show()

sys.exit(app.exec())