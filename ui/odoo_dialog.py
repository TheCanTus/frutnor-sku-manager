import json

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QProgressBar, QMessageBox, QGroupBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from core.paths import get_app_dir

CONFIG_PATH = get_app_dir() / "config.json"


def _cargar_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"odoo_url": "", "odoo_db": "", "odoo_user": "", "odoo_password": ""}


def _guardar_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


class _SubidaThread(QThread):
    progreso = Signal(int)
    terminado = Signal(int, int, list)

    def __init__(self, url, db, uid, password, skus):
        super().__init__()
        self._url = url
        self._db = db
        self._uid = uid
        self._password = password
        self._skus = skus

    def run(self):
        from services.odoo_service import subir_skus
        creados, actualizados, errores = subir_skus(
            self._url, self._db, self._uid, self._password, self._skus
        )
        self.terminado.emit(creados, actualizados, errores)


class OdooDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Subir a Odoo")
        self.setMinimumWidth(480)
        self._uid = None
        self._cfg = _cargar_config()

        layout = QVBoxLayout()
        self.setLayout(layout)

        # ── Configuración ──
        grp_cfg = QGroupBox("Configuración de conexión")
        form = QFormLayout()
        self.inp_url = QLineEdit(self._cfg.get("odoo_url", ""))
        self.inp_url.setPlaceholderText("https://miempresa.odoo.com")
        self.inp_db = QLineEdit(self._cfg.get("odoo_db", ""))
        self.inp_user = QLineEdit(self._cfg.get("odoo_user", ""))
        self.inp_pass = QLineEdit(self._cfg.get("odoo_password", ""))
        self.inp_pass.setEchoMode(QLineEdit.Password)
        form.addRow("URL:", self.inp_url)
        form.addRow("Base de datos:", self.inp_db)
        form.addRow("Usuario:", self.inp_user)
        form.addRow("Contraseña:", self.inp_pass)
        grp_cfg.setLayout(form)
        layout.addWidget(grp_cfg)

        btn_test = QPushButton("Probar conexión")
        btn_test.clicked.connect(self._probar_conexion)
        layout.addWidget(btn_test)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_estado)

        # ── Subida ──
        grp_sub = QGroupBox("Subir productos")
        sub_layout = QVBoxLayout()
        self.chk_solo_nuevos = QCheckBox("Solo productos que aún no están en Odoo")
        self.chk_solo_nuevos.setChecked(True)
        sub_layout.addWidget(self.chk_solo_nuevos)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        sub_layout.addWidget(self.progress)

        self.btn_subir = QPushButton("Subir a Odoo")
        self.btn_subir.setEnabled(False)
        self.btn_subir.clicked.connect(self._subir)
        sub_layout.addWidget(self.btn_subir)
        grp_sub.setLayout(sub_layout)
        layout.addWidget(grp_sub)

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.reject)
        layout.addWidget(btn_cerrar)

    def _credenciales(self):
        return (
            self.inp_url.text().strip(),
            self.inp_db.text().strip(),
            self.inp_user.text().strip(),
            self.inp_pass.text().strip(),
        )

    def _guardar(self):
        url, db, user, pwd = self._credenciales()
        _guardar_config({"odoo_url": url, "odoo_db": db, "odoo_user": user, "odoo_password": pwd})

    def _probar_conexion(self):
        from services.odoo_service import conectar
        url, db, user, pwd = self._credenciales()
        if not all([url, db, user, pwd]):
            QMessageBox.warning(self, "Faltan datos", "Complete todos los campos.")
            return
        try:
            self._uid = conectar(url, db, user, pwd)
            self.lbl_estado.setText("✔ Conexión exitosa")
            self.lbl_estado.setStyleSheet("color: green;")
            self.btn_subir.setEnabled(True)
            self._guardar()
        except Exception as e:
            self._uid = None
            self.btn_subir.setEnabled(False)
            self.lbl_estado.setText(f"✘ Error: {e}")
            self.lbl_estado.setStyleSheet("color: red;")

    def _subir(self):
        if not self._uid:
            return
        from database.db import SessionLocal
        from database.models import SKU
        session = SessionLocal()
        skus = session.query(SKU).all()
        session.close()

        if not skus:
            QMessageBox.information(self, "Sin productos", "No hay SKUs en la base de datos.")
            return

        url, db, _, pwd = self._credenciales()
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # indeterminate
        self.btn_subir.setEnabled(False)

        self._thread = _SubidaThread(url, db, self._uid, pwd, skus)
        self._thread.terminado.connect(self._on_terminado)
        self._thread.start()

    def _on_terminado(self, creados, actualizados, errores):
        self.progress.setVisible(False)
        self.btn_subir.setEnabled(True)
        msg = f"Creados: {creados}\nActualizados: {actualizados}"
        if errores:
            msg += f"\nErrores ({len(errores)}):\n" + "\n".join(errores[:10])
        QMessageBox.information(self, "Subida completada", msg)
