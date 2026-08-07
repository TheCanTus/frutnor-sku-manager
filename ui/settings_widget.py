import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QFormLayout, QLineEdit, QLabel,
    QMessageBox, QAbstractItemView, QInputDialog,
    QGroupBox, QProgressBar, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal

from database.db import SessionLocal
from database.models import Categoria, Presentacion, SKU, Producto
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
        tabs.addTab(_BaseDatosTab(), "Base de datos")
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
class _BaseDatosTab(QWidget):

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        self.setLayout(layout)

        grp = QGroupBox("Conexión a la base de datos")
        form = QFormLayout()
        form.setContentsMargins(10, 12, 10, 12)
        form.setSpacing(10)

        cfg = _cargar_config()
        self._inp_url = QLineEdit(cfg.get("db_url", ""))
        self._inp_url.setPlaceholderText(
            "postgresql://usuario:password@host:5432/db   —   vacío = SQLite local"
        )
        self._inp_url.setEchoMode(QLineEdit.Normal)
        form.addRow("URL:", self._inp_url)

        self._lbl_estado = QLabel("")
        self._lbl_estado.setWordWrap(True)
        form.addRow("Estado:", self._lbl_estado)

        btns = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_guardar.clicked.connect(self._guardar)
        btn_test = QPushButton("Probar conexión")
        btn_test.clicked.connect(self._probar)
        btns.addWidget(btn_guardar)
        btns.addWidget(btn_test)
        btns.addStretch()
        form.addRow("", btns)

        grp.setLayout(form)
        layout.addWidget(grp)

        info = QLabel(
            "• Dejá el campo vacío para usar la base de datos local (SQLite).\n"
            "• Para Supabase usá la URL del Session Pooler (puerto 5432).\n"
            "• El cambio aplica la próxima vez que se abre la aplicación."
        )
        info.setStyleSheet("color: gray; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()

    def _guardar(self):
        url = self._inp_url.text().strip()
        cfg = _cargar_config()
        cfg["db_url"] = url
        _guardar_config(cfg)
        QMessageBox.information(
            self, "Guardado",
            "URL guardada. Reiniciá la aplicación para aplicar el cambio."
        )

    def _probar(self):
        url = self._inp_url.text().strip()
        if not url:
            self._lbl_estado.setText("Sin URL — se usará SQLite local.")
            self._lbl_estado.setStyleSheet("color: gray;")
            return
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(url, pool_pre_ping=True, connect_args={})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self._lbl_estado.setText("✔ Conexión exitosa")
            self._lbl_estado.setStyleSheet("color: green;")
        except Exception as e:
            msg = str(e)
            if len(msg) > 120:
                msg = msg[:120] + "…"
            self._lbl_estado.setText(f"✘ {msg}")
            self._lbl_estado.setStyleSheet("color: red;")


# ── Threads ────────────────────────────────────────────────────

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
    terminado = Signal(int, int, int, list)  # creados_web, actualizados_web, creados_granel, errores

    def __init__(self, url, db, uid, password, solo_nuevos=False):
        super().__init__()
        self._url, self._db, self._uid, self._password = url, db, uid, password
        self._solo_nuevos = solo_nuevos

    def run(self):
        from services.odoo_service import subir_skus
        from sqlalchemy.orm import joinedload
        session = SessionLocal()
        cfg = _cargar_config()
        website_ids = cfg.get("website_ids") or {}
        try:
            skus = (
                session.query(SKU)
                .options(joinedload(SKU.producto))
                .all()
            )
            creados_web, actualizados_web, creados_granel, errores = subir_skus(
                self._url, self._db, self._uid, self._password, skus,
                solo_nuevos=self._solo_nuevos,
                website_ids=website_ids,
            )
        finally:
            session.close()
        self.terminado.emit(creados_web, actualizados_web, creados_granel, errores)


class _PreciosThread(QThread):
    terminado = Signal(int, int, list)  # actualizados, sin_precio, errores

    def __init__(self, url, db, uid, password):
        super().__init__()
        self._url, self._db, self._uid, self._password = url, db, uid, password

    def run(self):
        from services.odoo_service import subir_precios
        from sqlalchemy.orm import joinedload
        session = SessionLocal()
        cfg = _cargar_config()
        website_ids = cfg.get("website_ids") or {}
        try:
            skus = (
                session.query(SKU)
                .options(joinedload(SKU.producto))
                .all()
            )
            actualizados, sin_precio, errores = subir_precios(
                self._url, self._db, self._uid, self._password, skus,
                website_ids=website_ids,
            )
        finally:
            session.close()
        self.terminado.emit(actualizados, sin_precio, errores)


class _SubirBomsKitThread(QThread):
    done = Signal(int, int, int, list)   # creadas, actualizadas, omitidas, errores
    error = Signal(str)

    def run(self):
        import json as _json
        import xmlrpc.client

        cfg_path = get_app_dir() / "config.json"
        if not cfg_path.exists():
            self.error.emit("No hay configuración de Odoo.")
            return
        cfg = _json.loads(cfg_path.read_text(encoding="utf-8"))
        url = cfg.get("odoo_url", "").strip()
        db = cfg.get("odoo_db", "").strip()
        user = cfg.get("odoo_user", "").strip()
        pwd = cfg.get("odoo_password", "").strip()
        if not all([url, db, user, pwd]):
            self.error.emit("Faltan datos de conexión a Odoo en Configuración.")
            return

        try:
            uid = xmlrpc.client.ServerProxy(
                f"{url}/xmlrpc/2/common", allow_none=True
            ).authenticate(db, user, pwd, {})
            if not uid:
                self.error.emit("No se pudo autenticar en Odoo.")
                return
        except Exception as e:
            self.error.emit(f"Error de conexión: {e}")
            return

        from sqlalchemy.orm import joinedload
        from services.bom_exporter import _sugerir_boms_producto
        from services.odoo_service import subir_boms_kit

        session = SessionLocal()
        try:
            productos = (session.query(Producto)
                         .options(joinedload(Producto.skus))
                         .order_by(Producto.sku_base).all())
            boms_data = []
            for p in productos:
                boms_data.extend(_sugerir_boms_producto(p))
        finally:
            session.close()

        try:
            creadas, actualizadas, omitidas, errores = subir_boms_kit(url, db, uid, pwd, boms_data)
            self.done.emit(creadas, actualizadas, omitidas, errores)
        except Exception as e:
            self.error.emit(str(e))


class _CorregirUomThread(QThread):
    done = Signal(int, int, list)   # actualizados, sin_cambio, errores
    error = Signal(str)

    def run(self):
        import json as _json
        import xmlrpc.client

        cfg_path = get_app_dir() / "config.json"
        if not cfg_path.exists():
            self.error.emit("No hay configuración de Odoo.")
            return
        cfg = _json.loads(cfg_path.read_text(encoding="utf-8"))
        url = cfg.get("odoo_url", "").strip()
        db = cfg.get("odoo_db", "").strip()
        user = cfg.get("odoo_user", "").strip()
        pwd = cfg.get("odoo_password", "").strip()
        if not all([url, db, user, pwd]):
            self.error.emit("Faltan datos de conexión a Odoo.")
            return
        try:
            uid = xmlrpc.client.ServerProxy(
                f"{url}/xmlrpc/2/common", allow_none=True
            ).authenticate(db, user, pwd, {})
            if not uid:
                self.error.emit("No se pudo autenticar en Odoo.")
                return
        except Exception as e:
            self.error.emit(f"Error de conexión: {e}")
            return

        from sqlalchemy.orm import joinedload
        from services.odoo_service import corregir_uom_granel

        session = SessionLocal()
        try:
            productos = (session.query(Producto)
                         .options(joinedload(Producto.skus))
                         .order_by(Producto.sku_base).all())
        finally:
            session.close()

        try:
            actualizados, sin_cambio, errores = corregir_uom_granel(url, db, uid, pwd, productos)
            self.done.emit(actualizados, sin_cambio, errores)
        except Exception as e:
            self.error.emit(str(e))


# ──────────────────────────────────────────────────────────────
class _OdooTab(QWidget):

    def __init__(self):
        super().__init__()
        self._uid = None
        self._cfg = _cargar_config()

        # Scroll area externa — permite que el contenido sea más alto que la ventana
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        self.setLayout(outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(10, 10, 10, 10)
        content.setLayout(layout)
        scroll.setWidget(content)

        # ── Conexión ──────────────────────────────────────────
        grp_con = QGroupBox("Conexión a Odoo")
        form = QFormLayout()
        form.setContentsMargins(10, 12, 10, 10)
        form.setSpacing(8)
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

        con_btns = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_guardar.clicked.connect(self._guardar)
        self.btn_test = QPushButton("Probar conexión")
        self.btn_test.clicked.connect(self._probar)
        con_btns.addWidget(btn_guardar)
        con_btns.addWidget(self.btn_test)
        con_btns.addStretch()
        form.addRow("", con_btns)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setWordWrap(True)
        form.addRow("Estado:", self.lbl_estado)

        grp_con.setLayout(form)
        layout.addWidget(grp_con)

        # ── Sitios web ────────────────────────────────────────
        grp_web = QGroupBox("Sitios web de Odoo")
        web_form = QFormLayout()
        web_form.setContentsMargins(10, 12, 10, 10)
        web_form.setSpacing(8)

        cfg_wids = self._cfg.get("website_ids") or {}
        self._inp_web_min = QLineEdit(str(cfg_wids.get("minorista") or ""))
        self._inp_web_may = QLineEdit(str(cfg_wids.get("mayorista") or ""))
        self._inp_web_prev = QLineEdit(str(cfg_wids.get("preventista") or ""))
        for inp in [self._inp_web_min, self._inp_web_may, self._inp_web_prev]:
            inp.setPlaceholderText("ID numérico — ver /odoo/websites/N en Odoo")
        web_form.addRow("Minorista:", self._inp_web_min)
        web_form.addRow("Mayorista:", self._inp_web_may)
        web_form.addRow("Preventista:", self._inp_web_prev)

        web_btns = QHBoxLayout()
        btn_buscar_sitios = QPushButton("Buscar automáticamente")
        btn_buscar_sitios.setToolTip("Requiere conexión activa. Obtiene los IDs desde Odoo.")
        btn_buscar_sitios.clicked.connect(self._buscar_sitios)
        btn_guardar_sitios = QPushButton("Guardar")
        btn_guardar_sitios.clicked.connect(self._guardar_sitios)
        web_btns.addWidget(btn_buscar_sitios)
        web_btns.addWidget(btn_guardar_sitios)
        web_btns.addStretch()
        web_form.addRow("", web_btns)

        grp_web.setLayout(web_form)
        layout.addWidget(grp_web)

        # ── Sincronización ────────────────────────────────────
        grp_sub = QGroupBox("Sincronización con Odoo")
        sub_layout = QVBoxLayout()
        sub_layout.setContentsMargins(10, 12, 10, 10)
        sub_layout.setSpacing(10)

        self.progress_sub = QProgressBar()
        self.progress_sub.setVisible(False)
        sub_layout.addWidget(self.progress_sub)

        # Preparar GRL
        grl_row = QHBoxLayout()
        self.btn_preparar_grl = QPushButton("Agregar presentación Granel (GRL)")
        self.btn_preparar_grl.setToolTip(
            "Agrega la presentación GRL a todos los productos de peso que aún no la tengan.\n"
            "Necesario antes de subir los SKUs de granel a Odoo."
        )
        self.btn_preparar_grl.clicked.connect(self._preparar_grl)
        grl_row.addWidget(self.btn_preparar_grl)
        grl_row.addStretch()
        sub_layout.addLayout(grl_row)

        # Subir SKUs
        sku_row = QHBoxLayout()
        self.btn_subir = QPushButton("Subir todos los SKUs")
        self.btn_subir.setEnabled(False)
        self.btn_subir.clicked.connect(self._subir)
        self.btn_subir_nuevos = QPushButton("Subir solo nuevos")
        self.btn_subir_nuevos.setEnabled(False)
        self.btn_subir_nuevos.setToolTip("Solo sube los SKUs que todavía no están en Odoo.")
        self.btn_subir_nuevos.clicked.connect(self._subir_nuevos)
        sku_row.addWidget(self.btn_subir)
        sku_row.addWidget(self.btn_subir_nuevos)
        sku_row.addStretch()
        sub_layout.addLayout(sku_row)

        # Precios y BoMs
        sync_row2 = QHBoxLayout()
        self.btn_subir_precios = QPushButton("Actualizar precios")
        self.btn_subir_precios.setEnabled(False)
        self.btn_subir_precios.setToolTip(
            "Actualiza list_price y price_extra en los templates ya existentes en Odoo.\n"
            "No crea ni elimina productos — solo aplica los precios de la pestaña Precios."
        )
        self.btn_subir_precios.clicked.connect(self._subir_precios)

        self.btn_subir_boms = QPushButton("Subir BoMs Kit a Odoo")
        self.btn_subir_boms.setToolTip(
            "Crea o actualiza las listas de materiales (tipo Kit) en Odoo.\n"
            "Permite que al confirmar un pedido se descuente automáticamente el componente correcto del stock."
        )
        self.btn_subir_boms.clicked.connect(self._subir_boms_kit)
        self.progress_boms = QProgressBar()
        self.progress_boms.setVisible(False)

        sync_row2.addWidget(self.btn_subir_precios)
        sync_row2.addWidget(self.btn_subir_boms)
        sync_row2.addStretch()
        sub_layout.addLayout(sync_row2)
        sub_layout.addWidget(self.progress_boms)

        grp_sub.setLayout(sub_layout)
        layout.addWidget(grp_sub)

        # ── Mantenimiento ─────────────────────────────────────
        grp_mant = QGroupBox("Mantenimiento")
        mant_layout = QVBoxLayout()
        mant_layout.setContentsMargins(10, 12, 10, 10)
        mant_layout.setSpacing(10)

        mant_row = QHBoxLayout()
        self.btn_corregir_uom = QPushButton("Corregir UoM Graneles")
        self.btn_corregir_uom.setToolTip(
            "Cambia la unidad de medida de los productos granel de 'Unidades' a 'kg' en Odoo.\n"
            "Solo necesario si los graneles se subieron originalmente en unidades."
        )
        self.btn_corregir_uom.clicked.connect(self._corregir_uom_granel)

        self.btn_comparar = QPushButton("Comparar Odoo vs BD local")
        self.btn_comparar.setEnabled(False)
        self.btn_comparar.setToolTip(
            "Muestra qué SKUs están en Odoo pero no en la base local, y viceversa."
        )
        self.btn_comparar.clicked.connect(self._comparar)

        mant_row.addWidget(self.btn_corregir_uom)
        mant_row.addWidget(self.btn_comparar)
        mant_row.addStretch()
        mant_layout.addLayout(mant_row)

        self.progress_cmp = QProgressBar()
        self.progress_cmp.setVisible(False)
        mant_layout.addWidget(self.progress_cmp)

        sub_tabs = QTabWidget()
        self.tabla_solo_odoo = self._make_tabla(["SKU solo en Odoo (no está en la BD local)"])
        self.tabla_solo_local = self._make_tabla(["SKU solo en BD local (no subido a Odoo)"])
        sub_tabs.addTab(self._wrap(self.tabla_solo_odoo), "Solo en Odoo (0)")
        sub_tabs.addTab(self._wrap(self.tabla_solo_local), "Sin subir a Odoo (0)")
        self._sub_tabs = sub_tabs
        mant_layout.addWidget(sub_tabs)

        grp_mant.setLayout(mant_layout)
        layout.addWidget(grp_mant)

        # ── Actualizaciones ───────────────────────────────────
        grp_upd = QGroupBox("Actualizaciones automáticas")
        upd_layout = QFormLayout()
        upd_layout.setContentsMargins(10, 12, 10, 10)
        upd_layout.setSpacing(8)
        self._inp_gh_token = QLineEdit(self._cfg.get("github_token", ""))
        self._inp_gh_token.setEchoMode(QLineEdit.Password)
        self._inp_gh_token.setPlaceholderText("ghp_xxxx… (solo para repositorios privados)")
        self._inp_gh_token.setToolTip(
            "Personal Access Token de GitHub con permiso 'Contents: Read'.\n"
            "Dejá vacío si el repositorio es público."
        )
        upd_layout.addRow("GitHub Token:", self._inp_gh_token)
        btn_guardar_token = QPushButton("Guardar token")
        btn_guardar_token.clicked.connect(self._guardar_token)
        upd_layout.addRow("", btn_guardar_token)
        grp_upd.setLayout(upd_layout)
        layout.addWidget(grp_upd)

        layout.addStretch()

    # ── helpers ───────────────────────────────────────────────

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
        cfg = _cargar_config()
        cfg.update({"odoo_url": url, "odoo_db": db, "odoo_user": user, "odoo_password": pwd})
        _guardar_config(cfg)
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
            self.btn_subir_nuevos.setEnabled(True)
            self.btn_subir_precios.setEnabled(True)
            self.btn_comparar.setEnabled(True)
            self._guardar_silencioso()
        except Exception as e:
            self._uid = None
            self.btn_subir.setEnabled(False)
            self.btn_subir_nuevos.setEnabled(False)
            self.btn_subir_precios.setEnabled(False)
            self.btn_comparar.setEnabled(False)
            msg = str(e)
            if len(msg) > 120:
                msg = msg[:120] + "…"
            self.lbl_estado.setText(f"✘ {msg}")
            self.lbl_estado.setStyleSheet("color: red;")

    def _guardar_silencioso(self):
        url, db, user, pwd = self._credenciales()
        cfg = _cargar_config()
        cfg.update({"odoo_url": url, "odoo_db": db, "odoo_user": user, "odoo_password": pwd})
        _guardar_config(cfg)

    def _buscar_sitios(self):
        if not self._uid:
            QMessageBox.warning(self, "Sin conexión", "Primero probá la conexión a Odoo.")
            return
        from services.odoo_service import listar_websites
        url, db, _, pwd = self._credenciales()
        try:
            sitios = listar_websites(url, db, self._uid, pwd)
        except Exception:
            sitios = None

        if not sitios:
            QMessageBox.information(
                self, "Ingreso manual",
                "No se pudieron obtener los sitios automáticamente (permisos de API).\n\n"
                "Ingresá el ID manualmente:\n"
                "  1. En Odoo abrí Sitio web → Configuración\n"
                "  2. Hacé clic en cada sitio → mirá el número en la URL: /odoo/websites/N\n\n"
                "Ingresá ese N en el campo correspondiente y guardá."
            )
            return

        sitios_txt = "\n".join(
            f"  ID {s['id']}: {s['name']}  ({s.get('domain') or 'sin dominio'})"
            for s in sitios
        )
        QMessageBox.information(
            self, "Sitios encontrados",
            f"Sitios disponibles en Odoo:\n\n{sitios_txt}\n\n"
            "Ingresá el ID que corresponde a cada tienda en los campos de abajo y guardá."
        )
        cfg = _cargar_config()
        wids = cfg.get("website_ids") or {}
        for inp, key in [
            (self._inp_web_min, "minorista"),
            (self._inp_web_may, "mayorista"),
            (self._inp_web_prev, "preventista"),
        ]:
            if wids.get(key) is not None and not inp.text().strip():
                inp.setText(str(wids[key]))

    def _guardar_sitios(self):
        def _parse_id(inp):
            txt = inp.text().strip()
            try:
                return int(txt) if txt else None
            except ValueError:
                return None

        cfg = _cargar_config()
        cfg["website_ids"] = {
            "minorista": _parse_id(self._inp_web_min),
            "mayorista": _parse_id(self._inp_web_may),
            "preventista": _parse_id(self._inp_web_prev),
        }
        _guardar_config(cfg)
        QMessageBox.information(self, "Guardado", "Sitios web guardados correctamente.")

    def _preparar_grl(self):
        from services.product_service import agregar_presentaciones_granel
        session = SessionLocal()
        try:
            agregados = agregar_presentaciones_granel(session)
        finally:
            session.close()
        if agregados:
            lista = "\n".join(f"  • {n}" for n in agregados[:30])
            if len(agregados) > 30:
                lista += f"\n  … y {len(agregados) - 30} más"
            QMessageBox.information(
                self, "Presentaciones GRL agregadas",
                f"Se agregó GRL a {len(agregados)} producto(s):\n\n{lista}",
            )
        else:
            QMessageBox.information(
                self, "Sin cambios",
                "Todos los productos de peso ya tienen presentación GRL.",
            )

    def _subir(self, solo_nuevos=False):
        if not self._uid:
            return
        url, db, _, pwd = self._credenciales()
        self.progress_sub.setVisible(True)
        self.progress_sub.setRange(0, 0)
        self.btn_subir.setEnabled(False)
        self.btn_subir_nuevos.setEnabled(False)
        self._thread_sub = _SubidaThread(url, db, self._uid, pwd, solo_nuevos=solo_nuevos)
        self._thread_sub.terminado.connect(self._on_subida_terminada)
        self._thread_sub.start()

    def _subir_nuevos(self):
        self._subir(solo_nuevos=True)

    def _subir_precios(self):
        if not self._uid:
            return
        url, db, _, pwd = self._credenciales()
        self.progress_sub.setVisible(True)
        self.progress_sub.setRange(0, 0)
        self.btn_subir_precios.setEnabled(False)
        self._thread_precios = _PreciosThread(url, db, self._uid, pwd)
        self._thread_precios.terminado.connect(self._on_precios_terminado)
        self._thread_precios.finished.connect(lambda: self.progress_sub.setVisible(False))
        self._thread_precios.start()

    def _on_precios_terminado(self, actualizados, sin_precio, errores):
        self.btn_subir_precios.setEnabled(True)
        msg = (
            f"Templates actualizados: {actualizados}\n"
            f"Sin precio cargado (omitidos): {sin_precio}"
        )
        if errores:
            msg += f"\n\nErrores ({len(errores)}):\n" + "\n".join(errores[:10])
        QMessageBox.information(self, "Precios actualizados", msg)

    def _on_subida_terminada(self, creados_web, actualizados_web, creados_granel, errores):
        self.progress_sub.setVisible(False)
        self.btn_subir.setEnabled(True)
        self.btn_subir_nuevos.setEnabled(True)
        msg = (
            f"Templates web creados: {creados_web}\n"
            f"Variantes actualizadas: {actualizados_web}\n"
            f"Templates granel creados: {creados_granel}"
        )
        if errores:
            msg += f"\nErrores ({len(errores)}):\n" + "\n".join(errores[:10])
        QMessageBox.information(self, "Subida completada", msg)

    def _subir_boms_kit(self):
        self.btn_subir_boms.setEnabled(False)
        self.btn_subir_boms.setText("Subiendo BoMs…")
        self.progress_boms.setVisible(True)
        self.progress_boms.setRange(0, 0)
        self._thread_boms = _SubirBomsKitThread()
        self._thread_boms.done.connect(self._on_boms_kit_listo)
        self._thread_boms.error.connect(self._on_boms_kit_error)
        self._thread_boms.finished.connect(lambda: (
            self.btn_subir_boms.setEnabled(True),
            self.btn_subir_boms.setText("Subir BoMs Kit a Odoo"),
            self.progress_boms.setVisible(False),
        ))
        self._thread_boms.start()

    def _on_boms_kit_listo(self, creadas, actualizadas, omitidas, errores):
        msg = (
            f"BoMs Kit subidas a Odoo:\n"
            f"  Creadas:      {creadas}\n"
            f"  Actualizadas: {actualizadas}\n"
            f"  Omitidas:     {omitidas} (verificación manual o sin componente)\n"
        )
        if errores:
            detalle = "\n".join(errores[:20])
            if len(errores) > 20:
                detalle += f"\n… y {len(errores) - 20} más"
            QMessageBox.warning(self, "BoMs subidas con errores",
                                msg + f"\nErrores ({len(errores)}):\n{detalle}")
        else:
            QMessageBox.information(self, "Listo", msg)

    def _on_boms_kit_error(self, msg):
        QMessageBox.critical(self, "Error al subir BoMs", msg)

    def _corregir_uom_granel(self):
        self.btn_corregir_uom.setEnabled(False)
        self.btn_corregir_uom.setText("Corrigiendo UoM…")
        self._thread_uom = _CorregirUomThread()
        self._thread_uom.done.connect(self._on_uom_listo)
        self._thread_uom.error.connect(
            lambda msg: QMessageBox.critical(self, "Error", msg)
        )
        self._thread_uom.finished.connect(lambda: (
            self.btn_corregir_uom.setEnabled(True),
            self.btn_corregir_uom.setText("Corregir UoM Graneles"),
        ))
        self._thread_uom.start()

    def _on_uom_listo(self, actualizados, sin_cambio, errores):
        msg = f"UoM corregidas: {actualizados}\nSin cambio: {sin_cambio}"
        if errores:
            msg += f"\nErrores ({len(errores)}):\n" + "\n".join(errores[:10])
            QMessageBox.warning(self, "UoM Graneles", msg)
        else:
            QMessageBox.information(self, "Listo", msg)

    def _guardar_token(self):
        cfg = _cargar_config()
        cfg["github_token"] = self._inp_gh_token.text().strip()
        _guardar_config(cfg)
        QMessageBox.information(self, "Guardado", "Token guardado correctamente.")

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
