from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt


class NuevoProductoDialog(QDialog):

    def __init__(self, categorias, presentaciones, session=None):
        super().__init__()
        self.setWindowTitle("Nuevo Producto")
        self.setMinimumWidth(400)
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
        layout.addWidget(QLabel("Presentaciones:"))

        self.presentaciones = QListWidget()
        self.presentaciones.setSelectionMode(QListWidget.NoSelection)
        for pres in presentaciones:
            item = QListWidgetItem(pres.codigo)
            item.setToolTip(pres.descripcion)
            item.setCheckState(Qt.Unchecked)
            self.presentaciones.addItem(item)
        layout.addWidget(self.presentaciones)

        btn_nueva = QPushButton("＋ Nueva presentación")
        btn_nueva.clicked.connect(self._nueva_presentacion)
        layout.addWidget(btn_nueva)

        btn_guardar = QPushButton("Guardar")
        btn_guardar.setDefault(True)
        btn_guardar.clicked.connect(self._validar_y_aceptar)
        layout.addWidget(btn_guardar)

        self.setLayout(layout)

    def _actualizar_grupo(self):
        idx = self.categoria.currentIndex()
        if idx >= 0:
            cat = self._categorias[idx]
            self.grupo.setPlaceholderText(cat.nombre)

    def _nueva_presentacion(self):
        codigo, ok = QInputDialog.getText(
            self, "Nueva presentación",
            "Código de presentación (ej: 450G, 6X500):"
        )
        if not ok or not codigo.strip():
            return
        codigo = codigo.strip().upper()

        # Agregar a la lista visual
        for i in range(self.presentaciones.count()):
            if self.presentaciones.item(i).text() == codigo:
                self.presentaciones.item(i).setCheckState(Qt.Checked)
                return

        item = QListWidgetItem(codigo)
        item.setCheckState(Qt.Checked)
        self.presentaciones.addItem(item)
        self.presentaciones.scrollToBottom()

        # Persistir en BD si tenemos sesión
        if self._session:
            from services.product_service import agregar_presentacion_global
            agregar_presentacion_global(self._session, codigo)

    def _validar_y_aceptar(self):
        if not self.nombre.text().strip():
            QMessageBox.warning(self, "Error", "El nombre no puede estar vacío.")
            return
        if not self.presentaciones_seleccionadas():
            QMessageBox.warning(self, "Error", "Seleccioná al menos una presentación.")
            return
        self.accept()

    def presentaciones_seleccionadas(self):
        return [
            self.presentaciones.item(i).text()
            for i in range(self.presentaciones.count())
            if self.presentaciones.item(i).checkState() == Qt.Checked
        ]

    def grupo_texto(self):
        texto = self.grupo.text().strip()
        if texto:
            return texto
        # Usar el nombre de la categoría como fallback
        idx = self.categoria.currentIndex()
        if idx >= 0:
            return self._categorias[idx].nombre
        return ""
