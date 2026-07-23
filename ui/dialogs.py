from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QInputDialog, QMessageBox,
    QHeaderView,
)
from PySide6.QtCore import Qt


_TIENDAS = ["minorista", "mayorista", "preventista"]
_TIENDAS_HDR = ["Min", "May", "Prev"]


class NuevoProductoDialog(QDialog):

    def __init__(self, categorias, presentaciones, session=None):
        super().__init__()
        self.setWindowTitle("Nuevo Producto")
        self.setMinimumWidth(480)
        self._session = session

        form = QFormLayout()

        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Ej: Almendras Enteras")
        form.addRow("Nombre:", self.nombre)

        self.categoria = QComboBox()
        self._categorias = categorias
        for cat in categorias:
            self.categoria.addItem(f"{cat.codigo} — {cat.nombre}", cat.id)
        form.addRow("Categoría:", self.categoria)

        self.grupo = QLineEdit()
        self.grupo.setPlaceholderText("Se completa automáticamente")
        form.addRow("Grupo:", self.grupo)

        self.categoria.currentIndexChanged.connect(self._actualizar_grupo)
        self._actualizar_grupo()

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(QLabel("Marcá qué tiendas venden cada presentación:"))

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

        for pres in presentaciones:
            self._agregar_fila(pres.codigo, pres.descripcion or "")

        btn_nueva = QPushButton("＋ Nueva presentación")
        btn_nueva.clicked.connect(self._nueva_presentacion)
        layout.addWidget(btn_nueva)

        btn_guardar = QPushButton("Guardar")
        btn_guardar.setDefault(True)
        btn_guardar.clicked.connect(self._validar_y_aceptar)
        layout.addWidget(btn_guardar)

        self.setLayout(layout)

    def _agregar_fila(self, codigo, descripcion="", tiendas_checked=None):
        tiendas_checked = tiendas_checked or []
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

    def _actualizar_grupo(self):
        idx = self.categoria.currentIndex()
        if idx >= 0:
            self.grupo.setPlaceholderText(self._categorias[idx].nombre)

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

        self._agregar_fila(codigo)
        self.tabla.scrollToBottom()

        if self._session:
            from services.product_service import agregar_presentacion_global
            agregar_presentacion_global(self._session, codigo)

    def _validar_y_aceptar(self):
        if not self.nombre.text().strip():
            QMessageBox.warning(self, "Error", "El nombre no puede estar vacío.")
            return
        if not self.presentaciones_con_tiendas():
            QMessageBox.warning(
                self, "Error",
                "Marcá al menos una tienda en al menos una presentación."
            )
            return
        self.accept()

    def presentaciones_con_tiendas(self):
        """Retorna dict {codigo: [tiendas]} solo para filas con al menos una tienda marcada."""
        result = {}
        for row in range(self.tabla.rowCount()):
            codigo = self.tabla.item(row, 0).text()
            tiendas = [
                _TIENDAS[col]
                for col in range(3)
                if self.tabla.item(row, col + 1).checkState() == Qt.Checked
            ]
            if tiendas:
                result[codigo] = tiendas
        return result

    def grupo_texto(self):
        texto = self.grupo.text().strip()
        if texto:
            return texto
        idx = self.categoria.currentIndex()
        if idx >= 0:
            return self._categorias[idx].nombre
        return ""
