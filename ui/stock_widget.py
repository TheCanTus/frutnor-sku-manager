import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QProgressBar, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QColor

from database.db import SessionLocal
from database.models import Producto
from core.paths import get_app_dir

_COL_CAT = 0
_COL_PROD = 1
_COL_UNIDAD = 2
_COL_STOCK = 3
_COL_ODOO = 4

_GRAY = QColor(220, 220, 220)


class _LoaderWorker(QObject):
    done = Signal(list)

    def run(self):
        from sqlalchemy.orm import joinedload
        session = SessionLocal()
        try:
            productos = (
                session.query(Producto)
                .options(joinedload(Producto.skus), joinedload(Producto.categoria))
                .order_by(Producto.nombre)
                .all()
            )
            filas = [
                (
                    p.id,
                    p.categoria.codigo if p.categoria else "",
                    p.nombre,
                    p.stock_unidad or "kg",
                    p.stock,
                    [s.sku for s in p.skus],
                )
                for p in productos
            ]
        finally:
            session.close()
        self.done.emit(filas)


class _DescargaThread(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, url, db, uid, password, producto_skus):
        super().__init__()
        self._url, self._db, self._uid, self._password = url, db, uid, password
        self._producto_skus = producto_skus

    def run(self):
        from services.odoo_service import descargar_stock
        try:
            result = descargar_stock(
                self._url, self._db, self._uid, self._password, self._producto_skus
            )
            self.done.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _ActualizaThread(QThread):
    done = Signal(int, list)
    error = Signal(str)

    def __init__(self, url, db, uid, password, items):
        super().__init__()
        self._url, self._db, self._uid, self._password = url, db, uid, password
        self._items = items

    def run(self):
        from services.odoo_service import actualizar_stock
        try:
            actualizados, errores = actualizar_stock(
                self._url, self._db, self._uid, self._password, self._items
            )
            self.done.emit(actualizados, errores)
        except Exception as e:
            self.error.emit(str(e))


class StockWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._producto_ids = []
        self._producto_skus = {}
        self._cambios = {}
        self._cargado = False

        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QLabel(
            "Stock por producto. Unidad: 'kg' para granel, 'u' para productos ya fraccionados.\n"
            "El stock de Odoo es la suma de todas las variantes (referencial)."
        ))

        btn_row = QHBoxLayout()
        self.btn_descargar = QPushButton("Descargar de Odoo")
        self.btn_guardar = QPushButton("Guardar cambios")
        self.btn_actualizar = QPushButton("Actualizar en Odoo")
        self.btn_guardar.setEnabled(False)
        self.lbl_estado = QLabel("")
        for b in [self.btn_descargar, self.btn_guardar, self.btn_actualizar]:
            btn_row.addWidget(b)
        btn_row.addWidget(self.lbl_estado)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(
            ["Categoría", "Producto", "Unidad", "Stock local", "Stock Odoo"]
        )
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        hdr = self.tabla.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        layout.addWidget(self.tabla)

        self.tabla.itemChanged.connect(self._on_item_changed)
        self.btn_descargar.clicked.connect(self._descargar_odoo)
        self.btn_guardar.clicked.connect(self._guardar)
        self.btn_actualizar.clicked.connect(self._actualizar_odoo)

    def cargar(self):
        self._cargado = False
        self.lbl_estado.setText("Cargando…")
        self._thread_load = QThread()
        self._worker = _LoaderWorker()
        self._worker.moveToThread(self._thread_load)
        self._thread_load.started.connect(self._worker.run)
        self._worker.done.connect(self._on_datos_listos)
        self._worker.done.connect(self._thread_load.quit)
        self._thread_load.start()

    def _on_datos_listos(self, filas):
        self.tabla.blockSignals(True)
        self.setUpdatesEnabled(False)
        self.tabla.clearContents()
        self.tabla.setRowCount(len(filas))
        self._producto_ids = []
        self._producto_skus = {}

        for row, (pid, cat, nombre, unidad, stock, sku_codes) in enumerate(filas):
            self._producto_ids.append(pid)
            self._producto_skus[pid] = sku_codes

            item_cat = QTableWidgetItem(cat)
            item_cat.setFlags(Qt.ItemIsEnabled)
            self.tabla.setItem(row, _COL_CAT, item_cat)

            item_prod = QTableWidgetItem(nombre)
            item_prod.setFlags(Qt.ItemIsEnabled)
            self.tabla.setItem(row, _COL_PROD, item_prod)

            item_unidad = QTableWidgetItem(unidad)
            self.tabla.setItem(row, _COL_UNIDAD, item_unidad)

            stock_txt = "" if stock is None else f"{stock:g}"
            self.tabla.setItem(row, _COL_STOCK, QTableWidgetItem(stock_txt))

            item_odoo = QTableWidgetItem("")
            item_odoo.setFlags(Qt.ItemIsEnabled)
            item_odoo.setBackground(_GRAY)
            self.tabla.setItem(row, _COL_ODOO, item_odoo)

        self.setUpdatesEnabled(True)
        self.tabla.blockSignals(False)
        self._cambios = {}
        self.btn_guardar.setEnabled(False)
        self._cargado = True
        self.lbl_estado.setText(f"{len(filas)} productos")

    def _on_item_changed(self, item):
        if not self._cargado:
            return
        if item.column() not in (_COL_STOCK, _COL_UNIDAD):
            return
        row = item.row()
        if row >= len(self._producto_ids):
            return
        pid = self._producto_ids[row]
        txt_stock = (self.tabla.item(row, _COL_STOCK) or QTableWidgetItem("")).text().strip()
        txt_unidad = (self.tabla.item(row, _COL_UNIDAD) or QTableWidgetItem("kg")).text().strip()
        try:
            qty = float(txt_stock.replace(",", ".")) if txt_stock else None
        except ValueError:
            qty = None
        self._cambios[pid] = (qty, txt_unidad or "kg")
        self.btn_guardar.setEnabled(True)

    def _guardar(self):
        if not self._cambios:
            return
        session = SessionLocal()
        try:
            for pid, (qty, unidad) in self._cambios.items():
                p = session.query(Producto).filter_by(id=pid).first()
                if p:
                    p.stock = qty
                    p.stock_unidad = unidad if unidad in ("kg", "u") else "kg"
            session.commit()
        finally:
            session.close()
        self._cambios = {}
        self.btn_guardar.setEnabled(False)
        self.lbl_estado.setText("Guardado ✔")

    def _credenciales_odoo(self):
        cfg_path = get_app_dir() / "config.json"
        if not cfg_path.exists():
            return None
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        url = cfg.get("odoo_url", "").strip()
        db = cfg.get("odoo_db", "").strip()
        user = cfg.get("odoo_user", "").strip()
        pwd = cfg.get("odoo_password", "").strip()
        if not all([url, db, user, pwd]):
            return None
        return url, db, user, pwd

    def _conectar_odoo(self):
        creds = self._credenciales_odoo()
        if not creds:
            QMessageBox.warning(
                self, "Sin configuración",
                "Configurá la conexión a Odoo en la pestaña Configuración → Odoo."
            )
            return None, None, None, None
        url, db, user, pwd = creds
        from services.odoo_service import conectar
        try:
            uid = conectar(url, db, user, pwd)
            return url, db, uid, pwd
        except Exception as e:
            QMessageBox.critical(self, "Error de conexión", str(e))
            return None, None, None, None

    def _set_busy(self, busy):
        self.progress.setVisible(busy)
        self.btn_descargar.setEnabled(not busy)
        self.btn_actualizar.setEnabled(not busy)

    def _descargar_odoo(self):
        url, db, uid, pwd = self._conectar_odoo()
        if not uid:
            return
        self._set_busy(True)
        self.lbl_estado.setText("Descargando de Odoo…")
        self._thread_desc = _DescargaThread(url, db, uid, pwd, self._producto_skus)
        self._thread_desc.done.connect(self._on_descarga_lista)
        self._thread_desc.error.connect(self._on_descarga_error)
        self._thread_desc.finished.connect(lambda: self._set_busy(False))
        self._thread_desc.start()

    def _on_descarga_lista(self, stock_odoo):
        self.tabla.blockSignals(True)
        for row, pid in enumerate(self._producto_ids):
            qty = stock_odoo.get(pid)
            item = self.tabla.item(row, _COL_ODOO)
            if item:
                item.setText("" if qty is None else f"{qty:g}")
        self.tabla.blockSignals(False)
        encontrados = sum(1 for pid in self._producto_ids if pid in stock_odoo)
        self.lbl_estado.setText(f"Descargado ✔ — {encontrados} de {len(self._producto_ids)} productos en Odoo")

    def _on_descarga_error(self, msg):
        QMessageBox.critical(self, "Error al descargar", msg)
        self.lbl_estado.setText("Error al descargar")

    def _actualizar_odoo(self):
        if self._cambios:
            resp = QMessageBox.question(
                self, "Cambios sin guardar",
                "Hay cambios sin guardar. ¿Guardarlos antes de actualizar Odoo?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if resp == QMessageBox.Cancel:
                return
            if resp == QMessageBox.Yes:
                self._guardar()

        items = []
        for row, pid in enumerate(self._producto_ids):
            txt = (self.tabla.item(row, _COL_STOCK) or QTableWidgetItem("")).text().strip()
            nombre = (self.tabla.item(row, _COL_PROD) or QTableWidgetItem("")).text()
            try:
                qty = float(txt.replace(",", ".")) if txt else None
            except ValueError:
                qty = None
            if qty is not None and qty >= 0:
                items.append((nombre, qty, self._producto_skus.get(pid, [])))

        if not items:
            QMessageBox.information(self, "Sin stock", "No hay stock cargado para actualizar en Odoo.")
            return

        resp = QMessageBox.question(
            self, "Confirmar actualización",
            f"¿Actualizar stock de {len(items)} producto(s) en Odoo?\n\n"
            "El stock total se asigna a la primera variante de cada producto.\n"
            "Las demás variantes quedan en 0.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        url, db, uid, pwd = self._conectar_odoo()
        if not uid:
            return
        self._set_busy(True)
        self.lbl_estado.setText("Actualizando en Odoo…")
        self._thread_act = _ActualizaThread(url, db, uid, pwd, items)
        self._thread_act.done.connect(self._on_actualizacion_lista)
        self._thread_act.error.connect(self._on_actualizacion_error)
        self._thread_act.finished.connect(lambda: self._set_busy(False))
        self._thread_act.start()

    def _on_actualizacion_lista(self, actualizados, errores):
        msg = f"Stock actualizado: {actualizados} producto(s)"
        if errores:
            msg += f"\n\nErrores ({len(errores)}):\n" + "\n".join(errores[:10])
            QMessageBox.warning(self, "Resultado", msg)
        else:
            QMessageBox.information(self, "Listo", msg)
        self.lbl_estado.setText(f"Actualizado ✔ ({actualizados} productos)")

    def _on_actualizacion_error(self, msg):
        QMessageBox.critical(self, "Error al actualizar", msg)
        self.lbl_estado.setText("Error al actualizar")
