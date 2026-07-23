import json

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QInputDialog, QMessageBox,
    QHeaderView,
)
from PySide6.QtCore import Qt


_TIENDAS = ["minorista", "mayorista", "preventista"]
_TIENDAS_HDR = ["Min", "May", "Prev"]


class EditarProductoDialog(QDialog):

    def __init__(self, producto, todas_presentaciones, session=None):
        super().__init__()
        self.setWindowTitle("Editar Producto")
        self.setMinimumWidth(480)
        self._session = session
        self._producto = producto

        # Guardamos las tiendas originales por presentación para calcular cambios
        self._pres_orig = {}
        for sku in producto.skus:
            try:
                tiendas = json.loads(sku.tiendas or "[]")
            except (ValueError, TypeError):
                tiendas = []
            self._pres_orig[sku.presentacion] = tiendas

        form = QFormLayout()

        cat_label = QLabel(f"{producto.categoria.codigo} — {producto.categoria.nombre}")
        cat_label.setStyleSheet("color: gray;")
        form.addRow("Categoría:", cat_label)

        self.nombre = QLineEdit(producto.nombre)
        form.addRow("Nombre:", self.nombre)

        self.grupo = QLineEdit(producto.grupo or "")
        self.grupo.setPlaceholderText(producto.categoria.nombre)
        form.addRow("Grupo:", self.grupo)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(QLabel("Marcá qué tiendas venden cada presentación\n(quitar todas las marcas de una fila la elimina del producto):"))

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Presentación"] + _TIENDAS_HDR)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 4):
            self.tabla.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionMode(QTableWidget.NoSelection)
        layout.addWidget(self.tabla)

        codigos_en_tabla = set()

        # Presentaciones existentes del producto con sus tiendas actuales
        for pres_cod, tiendas in self._pres_orig.items():
            self._agregar_fila(pres_cod, tiendas)
            codigos_en_tabla.add(pres_cod)

        # Presentaciones globales que el producto aún no tiene (para poder agregarlas)
        for pres in todas_presentaciones:
            if pres.codigo not in codigos_en_tabla:
                self._agregar_fila(pres.codigo, [], descripcion=pres.descripcion or "")
                codigos_en_tabla.add(pres.codigo)

        btn_nueva = QPushButton("＋ Nueva presentación")
        btn_nueva.clicked.connect(self._nueva_presentacion)
        layout.addWidget(btn_nueva)

        btn_guardar = QPushButton("Guardar cambios")
        btn_guardar.setDefault(True)
        btn_guardar.clicked.connect(self._validar_y_aceptar)
        layout.addWidget(btn_guardar)

        self.setLayout(layout)

    def _agregar_fila(self, codigo, tiendas_checked, descripcion=""):
        row = self.tabla.rowCount()
        self.tabla.insertRow(row)

        item_cod = QTableWidgetItem(codigo)
        item_cod.setFlags(Qt.ItemIsEnabled)
        item_cod.setToolTip(descripcion)
        self.tabla.setItem(row, 0, item_cod)

        for col, tienda in enumerate(_TIENDAS, 1):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            chk.setCheckState(Qt.Checked if tienda in tiendas_checked else Qt.Unchecked)
            self.tabla.setItem(row, col, chk)

    def _nueva_presentacion(self):
        codigo, ok = QInputDialog.getText(
            self, "Nueva presentación",
            "Código de presentación (ej: 450G, 6X500):"
        )
        if not ok or not codigo.strip():
            return
        codigo = codigo.strip().upper()

        for row in range(self.tabla.rowCount()):
            if self.tabla.item(row, 0).text() == codigo:
                return

        self._agregar_fila(codigo, [])
        self.tabla.scrollToBottom()

        if self._session:
            from services.product_service import agregar_presentacion_global
            agregar_presentacion_global(self._session, codigo)

    def _tabla_state(self):
        """Lee el estado actual de la tabla como {codigo: [tiendas]}."""
        state = {}
        for row in range(self.tabla.rowCount()):
            codigo = self.tabla.item(row, 0).text()
            tiendas = [
                _TIENDAS[col]
                for col in range(3)
                if self.tabla.item(row, col + 1).checkState() == Qt.Checked
            ]
            state[codigo] = tiendas
        return state

    def _validar_y_aceptar(self):
        if not self.nombre.text().strip():
            QMessageBox.warning(self, "Error", "El nombre no puede estar vacío.")
            return

        state = self._tabla_state()
        # Contamos cuántas presentaciones van a quedar en el producto
        sobrevivientes = 0
        for codigo, tiendas in state.items():
            if codigo in self._pres_orig:
                orig = self._pres_orig[codigo]
                # GRL (tiendas=[]) siempre sobrevive; otros sobreviven si tienen tiendas
                if orig == [] or tiendas:
                    sobrevivientes += 1
            else:
                if tiendas:
                    sobrevivientes += 1

        if sobrevivientes == 0:
            QMessageBox.warning(self, "Error", "El producto debe tener al menos una presentación.")
            return

        self.accept()

    def calcular_cambios(self):
        """
        Retorna (agregar_dict, quitar_list, actualizar_dict):
          agregar_dict:   {codigo: [tiendas]} presentaciones nuevas
          quitar_list:    [codigo] presentaciones a eliminar
          actualizar_dict: {codigo: [tiendas]} presentaciones existentes con tiendas cambiadas
        """
        state = self._tabla_state()
        agregar, quitar, actualizar = {}, [], {}

        for codigo, tiendas_nuevas in state.items():
            if codigo in self._pres_orig:
                orig = self._pres_orig[codigo]
                if orig == []:
                    # GRL / interna: si el usuario marcó tiendas → actualizar; si sigue sin tiendas → no tocar
                    if tiendas_nuevas:
                        actualizar[codigo] = tiendas_nuevas
                elif sorted(tiendas_nuevas) != sorted(orig):
                    if tiendas_nuevas:
                        actualizar[codigo] = tiendas_nuevas
                    else:
                        quitar.append(codigo)
            else:
                if tiendas_nuevas:
                    agregar[codigo] = tiendas_nuevas

        return agregar, quitar, actualizar

    def grupo_texto(self):
        texto = self.grupo.text().strip()
        return texto if texto else (self._producto.grupo or self._producto.categoria.nombre)
