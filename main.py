import sys
from sqlalchemy import text

from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog
from PySide6.QtCore import QThread, Signal, QTimer

from database.db import engine
from database.models import Base
from ui.main_window import MainWindow
from version import VERSION


Base.metadata.create_all(bind=engine)

# Migraciones legacy — solo SQLite (PRAGMA no existe en PostgreSQL)
if engine.dialect.name == "sqlite":
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(productos)"))]
        if "grupo" not in cols:
            conn.execute(text("ALTER TABLE productos ADD COLUMN grupo VARCHAR"))
            conn.commit()

        sku_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(skus)"))]
        if "tiendas" not in sku_cols:
            conn.execute(text('ALTER TABLE skus ADD COLUMN tiendas TEXT DEFAULT \'["minorista"]\''))
            conn.commit()


class _UpdateChecker(QThread):
    resultado = Signal(str, str, str)  # (version, url, notas)

    def run(self):
        try:
            from services.updater import verificar_actualizacion
            info = verificar_actualizacion()
            if info:
                self.resultado.emit(*info)
        except Exception:
            pass


def _ofrecer_actualizacion(version, url, notas, ventana):
    msg = QMessageBox(ventana)
    msg.setWindowTitle("Actualización disponible")
    msg.setText(
        f"<b>Nueva versión disponible: {version}</b><br><br>"
        f"{notas}<br><br>"
        "¿Descargar e instalar ahora?"
    )
    msg.setIcon(QMessageBox.Information)
    btn_si = msg.addButton("Instalar ahora", QMessageBox.AcceptRole)
    msg.addButton("Más tarde", QMessageBox.RejectRole)
    msg.exec()

    if msg.clickedButton() != btn_si:
        return

    progreso = QProgressDialog("Descargando actualización...", None, 0, 100, ventana)
    progreso.setWindowTitle("Actualizando")
    progreso.setCancelButton(None)
    progreso.setModal(True)
    progreso.show()

    try:
        from services.updater import descargar_e_instalar
        ok = descargar_e_instalar(url, progreso_callback=lambda p: progreso.setValue(p))
        progreso.close()
        if ok:
            QMessageBox.information(
                ventana, "Listo",
                "La actualización se instalará al cerrar la aplicación.\n"
                "La app se va a reiniciar sola."
            )
            ventana.close()
        else:
            QMessageBox.warning(
                ventana, "No disponible",
                "La actualización automática solo funciona en la versión instalada (.exe)."
            )
    except Exception as e:
        progreso.close()
        QMessageBox.critical(ventana, "Error al actualizar", str(e))


app = QApplication(sys.argv)
app.setApplicationName("SKU Generator — Fruntor")
app.setApplicationVersion(VERSION)

window = MainWindow()
window.show()

# Chequeo de actualización en segundo plano, 4 segundos después del arranque
_checker = _UpdateChecker()
_checker.resultado.connect(lambda v, u, n: _ofrecer_actualizacion(v, u, n, window))
QTimer.singleShot(4000, _checker.start)

sys.exit(app.exec())
