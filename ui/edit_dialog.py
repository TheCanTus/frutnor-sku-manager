from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt


class EditarProductoDialog(QDialog):

    def __init__(self, producto, todas_presentaciones, session=None):
        super().__init__()
        self.setWindowTitle("Editar Producto")
        self.setMinimumWidth(400)
        self._session = session
        self._producto = producto
        self._pres_originales = {s.presentacion for s in producto.skus}

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
        layout.addWidget(QLabel("Presentaciones:"))

        self.presentaciones = QListWidget()
        self.presentaciones.setSelectionMode(QListWidget.NoSelection)

        codigos_en_lista = set()
        for pres in todas_presentaciones:
            item = QListWidgetItem(pres.codigo)
            item.setToolTip(pres.descripcion)
            checked = pres.codigo in self._pres_originales
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            self.presentaciones.addItem(item)
            codigos_en_lista.add(pres.codigo)

        # Agregar presentaciones del producto que no estén en la lista global
        for pres_cod in self._pres_originales:
            if pres_cod not in codigos_en_lista:
                item = QListWidgetItem(pres_cod)
                item.setCheckState(Qt.Checked)
                self.presentaciones.addItem(item)

        layout.addWidget(self.presentaciones)

        btn_nueva = QPushButton("＋ Nueva presentación")
        btn_nueva.clicked.connect(self._nueva_presentacion)
        layout.addWidget(btn_nueva)

        btn_guardar = QPushButton("Guardar cambios")
        btn_guardar.setDefault(True)
        btn_guardar.clicked.connect(self._validar_y_aceptar)
        layout.addWidget(btn_guardar)

        self.setLayout(layout)

    def _nueva_presentacion(self):
        codigo, ok = QInputDialog.getText(
            self, "Nueva presentación",
            "Código de presentación (ej: 450G, 6X500):"
        )
        if not ok or not codigo.strip():
            return
        codigo = codigo.strip().upper()

        for i in range(self.presentaciones.count()):
            if self.presentaciones.item(i).text() == codigo:
                self.presentaciones.item(i).setCheckState(Qt.Checked)
                return

        item = QListWidgetItem(codigo)
        item.setCheckState(Qt.Checked)
        self.presentaciones.addItem(item)
        self.presentaciones.scrollToBottom()

        if self._session:
            from services.product_service import agregar_presentacion_global
            agregar_presentacion_global(self._session, codigo)

    def _validar_y_aceptar(self):
        if not self.nombre.text().strip():
            QMessageBox.warning(self, "Error", "El nombre no puede estar vacío.")
            return
        if not self.presentaciones_seleccionadas():
            QMessageBox.warning(self, "Error", "Debe quedar al menos una presentación.")
            return
        self.accept()

    def presentaciones_seleccionadas(self):
        return {
            self.presentaciones.item(i).text()
            for i in range(self.presentaciones.count())
            if self.presentaciones.item(i).checkState() == Qt.Checked
        }

    def calcular_cambios(self):
        seleccionadas = self.presentaciones_seleccionadas()
        agregar = seleccionadas - self._pres_originales
        quitar = self._pres_originales - seleccionadas
        return list(agregar), list(quitar)

    def grupo_texto(self):
        texto = self.grupo.text().strip()
        return texto if texto else (self._producto.grupo or self._producto.categoria.nombre)
