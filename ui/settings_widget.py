import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QFormLayout, QLineEdit, QLabel,
    QMessageBox, QAbstractItemView, QInputDialog,
    QGroupBox, QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal

from database.db import SessionLocal
from database.models import Categoria, Presentacion, SKU, Producto

CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def _cargar_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"odoo_url": "", "odoo_db": "", "odoo_user": "", "odoo_password": ""}


def _guardar_config(cfg):
    CONFIG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ──────────────────────────────────────────────────────────────
class SettingsWidget(QWidget):

    def __init__(self):
        super().__init__()
        tabs = QTabWidget()
        layout = QVBoxLayout()
        layout.addWidget(tabs)
        self.setLayout(layout)

        tabs.addTab(_CategoriasTab(), "Categorías")
        tabs.addTab(_PresentacionesTab(), "Presentaciones")
        self._odoo_tab = _OdooTab()
        tabs.addTab(self._odoo_tab, "Odoo")


# ──────────────────────────────────────────────────────────────
class _CategoriasTab(QWidget):

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(2)
        self.tabla.setHorizontalHeaderLabels(["Código", "Nombre"])
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        layout.addWidget(self.tabla)

        btn_bar = QHBoxLayout()
        self.btn_agregar = QPushButton("Agregar")
        self.btn_editar = QPushButton("Editar")
        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_editar.setEnabled(False)
        self.btn_eliminar.setEnabled(False)
        for b in [self.btn_agregar, self.btn_editar, self.btn_eliminar]:
            btn_bar.addWidget(b)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        self.tabla.selectionModel().selectionChanged.connect(self._on_sel)
        self.btn_agregar.clicked.connect(self._agregar)
        self.btn_editar.clicked.connect(self._editar)
        self.btn_eliminar.clicked.connect(self._eliminar)

        self._cargar()

    def _cargar(self):
        session = SessionLocal()
        cats = session.query(Categoria).order_by(Categoria.codigo).all()
        self.tabla.setRowCount(len(cats))
        for i, c in enumerate(cats):
            self.tabla.setItem(i, 0, QTableWidgetItem(c.codigo))
            self.tabla.setItem(i, 1, QTableWidgetItem(c.nombre))
        session.close()

    def _on_sel(self):
        tiene = bool(self.tabla.selectedItems())
        self.btn_editar.setEnabled(tiene)
        self.btn_eliminar.setEnabled(tiene)

    def _agregar(self):
        codigo, ok = QInputDialog.getText(self, "Nueva categoría", "Código (3 letras, ej: FRU):")
        if not ok or not codigo.strip():
            return
        nombre, ok = QInputDialog.getText(self, "Nueva categoría", "Nombre completo:")
        if not ok or not nombre.strip():
            return
        session = SessionLocal()
        if session.query(Categoria).filter_by(codigo=codigo.strip().upper()).first():
            QMessageBox.warning(self, "Ya existe", f"El código {codigo.upper()} ya está registrado.")
            session.close()
            return
        session.add(Categoria(codigo=codigo.strip().upper(), nombre=nombre.strip()))
        session.commit()
        session.close()
        self._cargar()

    def _editar(self):
        row = self.tabla.currentRow()
        codigo_actual = self.tabla.item(row, 0).text()
        nombre_actual = self.tabla.item(row, 1).text()
        nombre, ok = QInputDialog.getText(
            self, "Editar categoría", "Nuevo nombre:", text=nombre_actual
        )
        if not ok or not nombre.strip():
            return
        session = SessionLocal()
        cat = session.query(Categoria).filter_by(codigo=codigo_actual).first()
        if cat:
            cat.nombre = nombre.strip()
            session.commit()
        session.close()
        self._cargar()

    def _eliminar(self):
        row = self.tabla.currentRow()
        codigo = self.tabla.item(row, 0).text()
        session = SessionLocal()
        en_uso = session.query(Producto).join(Categoria).filter(Categoria.codigo == codigo).count()
        if en_uso:
            QMessageBox.warning(
                self, "En uso",
                f"No se puede eliminar: hay {en_uso} producto(s) con esta categoría."
            )
            session.close()
            return
        resp = QMessageBox.question(
            self, "Confirmar", f"¿Eliminar la categoría {codigo}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            cat = session.query(Categoria).filter_by(codigo=codigo).first()
            if cat:
                session.delete(cat)
                session.commit()
        session.close()
        self._cargar()


# ──────────────────────────────────────────────────────────────
class _PresentacionesTab(QWidget):

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(2)
        self.tabla.setHorizontalHeaderLabels(["Código", "Descripción"])
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        layout.addWidget(self.tabla)

        btn_bar = QHBoxLayout()
        self.btn_agregar = QPushButton("Agregar")
        self.btn_editar = QPushButton("Editar descripción")
        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_editar.setEnabled(False)
        self.btn_eliminar.setEnabled(False)
        for b in [self.btn_agregar, self.btn_editar, self.btn_eliminar]:
            btn_bar.addWidget(b)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        self.tabla.selectionModel().selectionChanged.connect(self._on_sel)
        self.btn_agregar.clicked.connect(self._agregar)
        self.btn_editar.clicked.connect(self._editar)
        self.btn_eliminar.clicked.connect(self._eliminar)

        self._cargar()

    def _cargar(self):
        session = SessionLocal()
        pres = session.query(Presentacion).order_by(Presentacion.codigo).all()
        self.tabla.setRowCount(len(pres))
        for i, p in enumerate(pres):
            self.tabla.setItem(i, 0, QTableWidgetItem(p.codigo))
            self.tabla.setItem(i, 1, QTableWidgetItem(p.descripcion or ""))
        session.close()

    def _on_sel(self):
        tiene = bool(self.tabla.selectedItems())
        self.btn_editar.setEnabled(tiene)
        self.btn_eliminar.setEnabled(tiene)

    def _agregar(self):
        codigo, ok = QInputDialog.getText(self, "Nueva presentación", "Código (ej: 750G, 3K):")
        if not ok or not codigo.strip():
            return
        desc, ok = QInputDialog.getText(self, "Nueva presentación", "Descripción (opcional):")
        if not ok:
            return
        session = SessionLocal()
        if session.query(Presentacion).filter_by(codigo=codigo.strip().upper()).first():
            QMessageBox.warning(self, "Ya existe", f"El código {codigo.upper()} ya está registrado.")
            session.close()
            return
        session.add(Presentacion(codigo=codigo.strip().upper(), descripcion=desc.strip()))
        session.commit()
        session.close()
        self._cargar()

    def _editar(self):
        row = self.tabla.currentRow()
        codigo = self.tabla.item(row, 0).text()
        desc_actual = self.tabla.item(row, 1).text()
        desc, ok = QInputDialog.getText(
            self, "Editar descripción", "Descripción:", text=desc_actual
        )
        if not ok:
            return
        session = SessionLocal()
        p = session.query(Presentacion).filter_by(codigo=codigo).first()
        if p:
            p.descripcion = desc.strip()
            session.commit()
        session.close()
        self._cargar()

    def _eliminar(self):
        row = self.tabla.currentRow()
        codigo = self.tabla.item(row, 0).text()
        session = SessionLocal()
        en_uso = session.query(SKU).filter_by(presentacion=codigo).count()
        if en_uso:
            QMessageBox.warning(
                self, "En uso",
                f"No se puede eliminar: hay {en_uso} SKU(s) con esta presentación."
            )
            session.close()
            return
        resp = QMessageBox.question(
            self, "Confirmar", f"¿Eliminar la presentación {codigo}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            p = session.query(Presentacion).filter_by(codigo=codigo).first()
            if p:
                session.delete(p)
                session.commit()
        session.close()
        self._cargar()


# ──────────────────────────────────────────────────────────────
class _ComparacionThread(QThread):
    terminado = Signal(list, list)  # solo_odoo, solo_local

    def __init__(self, url, db, uid, password):
        super().__init__()
        self._url, self._db, self._uid, self._password = url, db, uid, password

    def run(self):
        from services.odoo_service import listar_skus_odoo
        try:
            odoo_skus = set(listar_skus_odoo(self._url, self._db, self._uid, self._password))
        except Exception:
            self.terminado.emit([], [])
            return

        session = SessionLocal()
        local_skus = {s.sku for s in session.query(SKU).all()}
        session.close()

        solo_odoo = sorted(odoo_skus - local_skus)
        solo_local = sorted(local_skus - odoo_skus)
        self.terminado.emit(solo_odoo, solo_local)


class _SubidaThread(QThread):
    terminado = Signal(int, int, list)

    def __init__(self, url, db, uid, password):
        super().__init__()
        self._url, self._db, self._uid, self._password = url, db, uid, password

    def run(self):
        from services.odoo_service import subir_skus
        from sqlalchemy.orm import joinedload
        session = SessionLocal()
        try:
            skus = (
                session.query(SKU)
                .options(joinedload(SKU.producto))
                .all()
            )
            creados, actualizados, errores = subir_skus(
                self._url, self._db, self._uid, self._password, skus
            )
        finally:
            session.close()
        self.terminado.emit(creados, actualizados, errores)


class _OdooTab(QWidget):

    def __init__(self):
        super().__init__()
        self._uid = None
        self._cfg = _cargar_config()

        layout = QVBoxLayout()
        self.setLayout(layout)

        # ── Conexión ──
        grp_con = QGroupBox("Conexión")
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
        grp_con.setLayout(form)
        layout.addWidget(grp_con)

        con_btns = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_guardar.clicked.connect(self._guardar)
        self.btn_test = QPushButton("Probar conexión")
        self.btn_test.clicked.connect(self._probar)
        self.lbl_estado = QLabel("")
        self.lbl_estado.setWordWrap(True)
        self.lbl_estado.setMaximumWidth(400)
        con_btns.addWidget(btn_guardar)
        con_btns.addWidget(self.btn_test)
        con_btns.addWidget(self.lbl_estado)
        con_btns.addStretch()
        layout.addLayout(con_btns)

        # ── Subir a Odoo ──
        grp_sub = QGroupBox("Subir productos a Odoo")
        sub_layout = QVBoxLayout()
        self.progress_sub = QProgressBar()
        self.progress_sub.setVisible(False)
        self.btn_subir = QPushButton("Subir todos los SKUs")
        self.btn_subir.setEnabled(False)
        self.btn_subir.clicked.connect(self._subir)
        sub_layout.addWidget(self.progress_sub)
        sub_layout.addWidget(self.btn_subir)
        grp_sub.setLayout(sub_layout)
        layout.addWidget(grp_sub)

        # ── Comparación ──
        grp_cmp = QGroupBox("Comparar Odoo vs base de datos local")
        cmp_layout = QVBoxLayout()

        self.btn_comparar = QPushButton("Comparar ahora")
        self.btn_comparar.setEnabled(False)
        self.btn_comparar.clicked.connect(self._comparar)
        self.progress_cmp = QProgressBar()
        self.progress_cmp.setVisible(False)
        cmp_layout.addWidget(self.btn_comparar)
        cmp_layout.addWidget(self.progress_cmp)

        sub_tabs = QTabWidget()

        self.tabla_solo_odoo = self._make_tabla(["SKU solo en Odoo (no está en la BD local)"])
        self.tabla_solo_local = self._make_tabla(["SKU solo en BD local (no subido a Odoo)"])
        sub_tabs.addTab(self._wrap(self.tabla_solo_odoo), "Solo en Odoo (0)")
        sub_tabs.addTab(self._wrap(self.tabla_solo_local), "Sin subir a Odoo (0)")
        self._sub_tabs = sub_tabs

        cmp_layout.addWidget(sub_tabs)
        grp_cmp.setLayout(cmp_layout)
        layout.addWidget(grp_cmp)

    # ── helpers ──

    @staticmethod
    def _make_tabla(headers):
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    @staticmethod
    def _wrap(widget):
        w = QWidget()
        l = QVBoxLayout()
        l.addWidget(widget)
        w.setLayout(l)
        return w

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
        QMessageBox.information(self, "Guardado", "Configuración guardada correctamente.")

    def _probar(self):
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
            self.btn_comparar.setEnabled(True)
            self._guardar_silencioso()
        except Exception as e:
            self._uid = None
            self.btn_subir.setEnabled(False)
            self.btn_comparar.setEnabled(False)
            msg = str(e)
            if len(msg) > 120:
                msg = msg[:120] + "…"
            self.lbl_estado.setText(f"✘ {msg}")
            self.lbl_estado.setStyleSheet("color: red;")
            self.lbl_estado.setWordWrap(True)

    def _guardar_silencioso(self):
        url, db, user, pwd = self._credenciales()
        _guardar_config({"odoo_url": url, "odoo_db": db, "odoo_user": user, "odoo_password": pwd})

    def _subir(self):
        if not self._uid:
            return
        url, db, _, pwd = self._credenciales()
        self.progress_sub.setVisible(True)
        self.progress_sub.setRange(0, 0)
        self.btn_subir.setEnabled(False)
        self._thread_sub = _SubidaThread(url, db, self._uid, pwd)
        self._thread_sub.terminado.connect(self._on_subida_terminada)
        self._thread_sub.start()

    def _on_subida_terminada(self, creados, actualizados, errores):
        self.progress_sub.setVisible(False)
        self.btn_subir.setEnabled(True)
        msg = f"Creados: {creados}\nActualizados: {actualizados}"
        if errores:
            msg += f"\nErrores ({len(errores)}):\n" + "\n".join(errores[:10])
        QMessageBox.information(self, "Subida completada", msg)

    def _comparar(self):
        if not self._uid:
            return
        url, db, _, pwd = self._credenciales()
        self.progress_cmp.setVisible(True)
        self.progress_cmp.setRange(0, 0)
        self.btn_comparar.setEnabled(False)
        self._thread_cmp = _ComparacionThread(url, db, self._uid, pwd)
        self._thread_cmp.terminado.connect(self._on_comparacion_terminada)
        self._thread_cmp.start()

    def _on_comparacion_terminada(self, solo_odoo, solo_local):
        self.progress_cmp.setVisible(False)
        self.btn_comparar.setEnabled(True)

        self.tabla_solo_odoo.setRowCount(len(solo_odoo))
        for i, sku in enumerate(solo_odoo):
            self.tabla_solo_odoo.setItem(i, 0, QTableWidgetItem(sku))

        self.tabla_solo_local.setRowCount(len(solo_local))
        for i, sku in enumerate(solo_local):
            self.tabla_solo_local.setItem(i, 0, QTableWidgetItem(sku))

        self._sub_tabs.setTabText(0, f"Solo en Odoo ({len(solo_odoo)})")
        self._sub_tabs.setTabText(1, f"Sin subir a Odoo ({len(solo_local)})")
