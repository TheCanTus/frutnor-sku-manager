import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox,
    QLineEdit, QHeaderView, QAbstractItemView, QLabel,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QColor

from database.db import SessionLocal
from database.models import SKU, Producto

_TIENDAS = ["minorista", "mayorista", "preventista"]
_COL_PRECIO = 4
_GRIS = QColor(60, 60, 60)


class _LoaderWorker(QObject):
    done = Signal(list)

    def run(self):
        session = SessionLocal()
        try:
            skus = (
                session.query(SKU)
                .join(Producto)
                .order_by(Producto.nombre, SKU.presentacion)
                .all()
            )
            filas = [
                (
                    sku.id,
                    sku.producto.nombre,
                    sku.sku,
                    sku.presentacion,
                    json.loads(sku.tiendas or '["minorista"]'),
                    json.loads(sku.precios or '{}'),
                )
                for sku in skus
            ]
        finally:
            session.close()
        self.done.emit(filas)


class PreciosWidget(QWidget):

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por SKU, nombre o presentación...")
        top.addWidget(self.search)
        self.lbl_estado = QLabel("")
        top.addWidget(self.lbl_estado)
        layout.addLayout(top)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Producto", "SKU", "Presentación", "Tiendas",
            "Minorista ($)", "Mayorista ($)", "Preventista ($)",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 7):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 110)
        layout.addWidget(self.table)

        btn_bar = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar precios")
        self.btn_refrescar = QPushButton("Refrescar")
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_refrescar)
        btn_bar.addWidget(self.btn_guardar)
        layout.addLayout(btn_bar)

        self._sku_ids: list[int] = []
        self._cambios: dict[int, dict] = {}
        self._thread: QThread | None = None

        self.search.textChanged.connect(self._filtrar)
        self.table.cellChanged.connect(self._on_celda_cambiada)
        self.btn_guardar.clicked.connect(self._guardar)
        self.btn_refrescar.clicked.connect(self.cargar)

    # ── Carga en hilo secundario ────────────────────────────────

    def cargar(self):
        if self._thread and self._thread.isRunning():
            return
        self.lbl_estado.setText("Cargando…")
        self.btn_refrescar.setEnabled(False)

        self._thread = QThread(self)
        self._worker = _LoaderWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_datos_listos)
        self._worker.done.connect(self._thread.quit)
        self._thread.start()

    def _on_datos_listos(self, filas: list):
        self._sku_ids.clear()

        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(filas))

        for fila, (sku_id, nombre, sku_str, pres, tiendas, precios) in enumerate(filas):
            self._sku_ids.append(sku_id)

            for col, val in enumerate([nombre, sku_str, pres, ", ".join(tiendas)]):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(fila, col, item)

            for i, tienda in enumerate(_TIENDAS):
                precio = precios.get(tienda)
                if precio is not None:
                    texto = str(int(precio)) if float(precio) == int(precio) else str(precio)
                else:
                    texto = ""
                item = QTableWidgetItem(texto)
                if tienda not in tiendas:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setBackground(_GRIS)
                    item.setToolTip("Esta presentación no se vende en esta tienda")
                self.table.setItem(fila, _COL_PRECIO + i, item)

        self.table.setUpdatesEnabled(True)
        self.table.blockSignals(False)

        self.btn_refrescar.setEnabled(True)
        self.lbl_estado.setText(f"{len(filas)} SKUs cargados.")

    # ── Edición ─────────────────────────────────────────────────

    def _on_celda_cambiada(self, fila, col):
        if col < _COL_PRECIO or fila >= len(self._sku_ids):
            return
        sku_id = self._sku_ids[fila]
        tienda = _TIENDAS[col - _COL_PRECIO]
        texto = (self.table.item(fila, col).text() or "").strip().replace(",", ".")
        try:
            precio = float(texto) if texto else 0.0
        except ValueError:
            return
        self._cambios.setdefault(sku_id, {})[tienda] = precio
        self.lbl_estado.setText(f"{len(self._cambios)} fila(s) con cambios sin guardar")

    def _filtrar(self, texto):
        texto = texto.lower()
        for fila in range(self.table.rowCount()):
            visible = not texto or any(
                texto in ((self.table.item(fila, c) or QTableWidgetItem("")).text().lower())
                for c in range(4)
            )
            self.table.setRowHidden(fila, not visible)

    # ── Guardar ─────────────────────────────────────────────────

    def _guardar(self):
        if not self._cambios:
            QMessageBox.information(self, "Sin cambios", "No hay precios modificados.")
            return
        session = SessionLocal()
        try:
            for sku_id, cambios in self._cambios.items():
                sku = session.query(SKU).filter_by(id=sku_id).first()
                if not sku:
                    continue
                precios = json.loads(sku.precios or '{}')
                for tienda, precio in cambios.items():
                    if precio > 0:
                        precios[tienda] = precio
                    else:
                        precios.pop(tienda, None)
                sku.precios = json.dumps(precios)
            session.commit()
            self._cambios.clear()
            self.lbl_estado.setText("Guardado correctamente.")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error al guardar", str(e))
        finally:
            session.close()
