from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QRadioButton, QButtonGroup, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox, QHeaderView,
    QTabWidget, QWidget, QComboBox, QCheckBox, QScrollArea,
    QFormLayout, QGroupBox, QSizePolicy,
)
from PySide6.QtCore import Qt

from database.db import SessionLocal
from database.models import Categoria


class ImportarPedixDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importar desde Pedix")
        self.setMinimumSize(750, 560)
        self._archivo = None
        self._extra_map = {}        # {cat_pedix: codigo_sku} asignado por el usuario
        self._forzar_nombres = set()

        layout = QVBoxLayout()
        self.setLayout(layout)

        # ── Tipo ──
        tipo_layout = QHBoxLayout()
        tipo_layout.addWidget(QLabel("Tipo:"))
        self.rb_min = QRadioButton("Minorista")
        self.rb_may = QRadioButton("Mayorista")
        self.rb_min.setChecked(True)
        grp = QButtonGroup()
        grp.addButton(self.rb_min)
        grp.addButton(self.rb_may)
        tipo_layout.addWidget(self.rb_min)
        tipo_layout.addWidget(self.rb_may)
        tipo_layout.addStretch()
        layout.addLayout(tipo_layout)

        # ── Selector de archivo ──
        file_layout = QHBoxLayout()
        self.lbl_archivo = QLineEdit()
        self.lbl_archivo.setReadOnly(True)
        self.lbl_archivo.setPlaceholderText("Ningún archivo seleccionado")
        btn_elegir = QPushButton("Elegir archivo...")
        btn_elegir.clicked.connect(self._elegir_archivo)
        file_layout.addWidget(self.lbl_archivo)
        file_layout.addWidget(btn_elegir)
        layout.addLayout(file_layout)

        # ── Sección categorías sin mapeo (oculta hasta que se elige archivo) ──
        self.grp_sin_mapeo = QGroupBox("Categorías sin mapeo automático — asigná una categoría")
        self.grp_sin_mapeo.setVisible(False)
        self._sin_mapeo_layout = QFormLayout()
        self._combos_cat = {}  # {cat_pedix: QComboBox}
        scroll_content = QWidget()
        scroll_content.setLayout(self._sin_mapeo_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_content)
        scroll.setMaximumHeight(180)
        grp_layout = QVBoxLayout()
        grp_layout.addWidget(scroll)
        self.grp_sin_mapeo.setLayout(grp_layout)
        layout.addWidget(self.grp_sin_mapeo)

        # ── Preview ──
        layout.addWidget(QLabel("Vista previa (primeros 50 productos):"))
        self.tabla_preview = QTableWidget()
        self.tabla_preview.setColumnCount(3)
        self.tabla_preview.setHorizontalHeaderLabels(["Nombre", "Categoría Pedix", "Código SKU"])
        self.tabla_preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_preview.horizontalHeader().setStretchLastSection(True)
        self.tabla_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.tabla_preview)

        # ── Botones ──
        btn_layout = QHBoxLayout()
        self.btn_importar = QPushButton("Importar")
        self.btn_importar.setEnabled(False)
        self.btn_importar.clicked.connect(self._importar)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancelar)
        btn_layout.addWidget(self.btn_importar)
        layout.addLayout(btn_layout)

    def _tipo(self):
        return "minorista" if self.rb_min.isChecked() else "mayorista"

    def _elegir_archivo(self):
        archivo, _ = QFileDialog.getOpenFileName(
            self, "Abrir Excel de Pedix", "", "Excel (*.xlsx *.xls *.xlsm)"
        )
        if not archivo:
            return
        self._archivo = archivo
        self.lbl_archivo.setText(archivo)
        self._cargar_sin_mapeo()
        self._cargar_preview()

    def _cargar_sin_mapeo(self):
        """Escanea el archivo y muestra combos para categorías sin mapeo."""
        from services.pedix_importer import escanear_categorias_sin_mapeo

        # Limpiar combos anteriores
        while self._sin_mapeo_layout.rowCount():
            self._sin_mapeo_layout.removeRow(0)
        self._combos_cat.clear()

        try:
            sin_mapeo = escanear_categorias_sin_mapeo(self._archivo)
        except Exception:
            return

        if not sin_mapeo:
            self.grp_sin_mapeo.setVisible(False)
            return

        session = SessionLocal()
        categorias = session.query(Categoria).order_by(Categoria.codigo).all()
        session.close()

        opciones = ["— Omitir productos de esta categoría —"] + [
            f"{c.codigo} — {c.nombre}" for c in categorias
        ]
        self._cats_objetos = categorias

        for cat_pedix in sin_mapeo:
            combo = QComboBox()
            combo.addItems(opciones)
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._combos_cat[cat_pedix] = combo
            lbl = QLabel(cat_pedix)
            lbl.setWordWrap(True)
            self._sin_mapeo_layout.addRow(lbl, combo)

        self.grp_sin_mapeo.setVisible(True)

    def _extra_map_actual(self):
        """Lee los combos y construye el dict extra_map."""
        extra = {}
        for cat_pedix, combo in self._combos_cat.items():
            idx = combo.currentIndex()
            if idx == 0:
                continue  # omitir
            cat_obj = self._cats_objetos[idx - 1]
            extra[cat_pedix] = cat_obj.codigo
        return extra

    def _cargar_preview(self):
        if not self._archivo:
            return
        from services.pedix_importer import previsualizar
        try:
            rows = previsualizar(self._archivo, self._tipo())
        except Exception as e:
            QMessageBox.critical(self, "Error leyendo archivo", str(e))
            return

        self.tabla_preview.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.tabla_preview.setItem(i, 0, QTableWidgetItem(r["nombre"]))
            self.tabla_preview.setItem(i, 1, QTableWidgetItem(r["categoria_pedix"]))
            item = QTableWidgetItem(r["codigo_sku"])
            if r["codigo_sku"] == "—":
                item.setForeground(Qt.red)
            self.tabla_preview.setItem(i, 2, item)

        self.btn_importar.setEnabled(bool(rows))

    def _importar(self):
        extra_map = self._extra_map_actual()
        session = SessionLocal()
        from services.pedix_importer import importar_desde_pedix
        try:
            importados, omitidos, errores = importar_desde_pedix(
                session, self._archivo, self._tipo(),
                extra_map=extra_map,
                forzar_nombres=self._forzar_nombres,
            )
        except Exception as e:
            session.close()
            QMessageBox.critical(self, "Error durante la importación", str(e))
            return
        session.close()

        # Filtrar omitidos que el usuario puede forzar
        pueden_forzar = [o for o in omitidos if o.get("puede_forzar")]

        resumen = _ResultadoDialog(importados, omitidos, errores, pueden_forzar, self)
        if resumen.exec() and resumen.nombres_a_forzar:
            # El usuario pidió reimportar algunos → segunda pasada
            self._forzar_nombres = resumen.nombres_a_forzar
            self._importar()
        else:
            self.accept()


class _ResultadoDialog(QDialog):

    def __init__(self, importados, omitidos, errores, pueden_forzar, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resultado de la importación")
        self.setMinimumSize(720, 460)
        self.nombres_a_forzar = set()

        layout = QVBoxLayout()
        self.setLayout(layout)

        total_om = len(omitidos)
        total_err = len(errores)
        resumen_lbl = QLabel(
            f"<b>Importados:</b> {importados} &nbsp;&nbsp; "
            f"<b>Omitidos:</b> {total_om} &nbsp;&nbsp; "
            f"<b>Errores:</b> {total_err}"
        )
        layout.addWidget(resumen_lbl)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ── Tab omitidos ──
        if omitidos:
            tab_om = QWidget()
            v = QVBoxLayout()
            tab_om.setLayout(v)

            tabla_om = QTableWidget()
            tabla_om.setColumnCount(2)
            tabla_om.setHorizontalHeaderLabels(["Producto", "Motivo"])
            tabla_om.setEditTriggers(QTableWidget.NoEditTriggers)
            tabla_om.setSelectionBehavior(QTableWidget.SelectRows)
            tabla_om.horizontalHeader().setStretchLastSection(True)
            tabla_om.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            tabla_om.setRowCount(len(omitidos))
            for i, o in enumerate(omitidos):
                tabla_om.setItem(i, 0, QTableWidgetItem(o["nombre"]))
                tabla_om.setItem(i, 1, QTableWidgetItem(o["motivo"]))
            v.addWidget(tabla_om)
            tabs.addTab(tab_om, f"Omitidos ({total_om})")

        # ── Tab reimportar (solo los que "pueden_forzar") ──
        if pueden_forzar:
            tab_forzar = QWidget()
            v2 = QVBoxLayout()
            tab_forzar.setLayout(v2)

            lbl = QLabel(
                "Estos productos ya existen en la BD. "
                "Marcá los que querés reimportar de todas formas (se creará un duplicado con nuevo SKU):"
            )
            lbl.setWordWrap(True)
            v2.addWidget(lbl)

            self._checks = {}
            scroll_w = QWidget()
            scroll_l = QVBoxLayout()
            scroll_w.setLayout(scroll_l)
            for o in pueden_forzar:
                cb = QCheckBox(o["nombre"])
                self._checks[o["nombre"]] = cb
                scroll_l.addWidget(cb)
            scroll_l.addStretch()

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(scroll_w)
            v2.addWidget(scroll)

            btn_forzar = QPushButton("Reimportar seleccionados")
            btn_forzar.clicked.connect(self._aceptar_forzar)
            v2.addWidget(btn_forzar)

            tabs.addTab(tab_forzar, f"Ya en BD — reimportar ({len(pueden_forzar)})")

        # ── Tab errores ──
        if errores:
            tab_err = QWidget()
            v3 = QVBoxLayout()
            tab_err.setLayout(v3)
            tabla_err = QTableWidget()
            tabla_err.setColumnCount(2)
            tabla_err.setHorizontalHeaderLabels(["Producto", "Error"])
            tabla_err.setEditTriggers(QTableWidget.NoEditTriggers)
            tabla_err.horizontalHeader().setStretchLastSection(True)
            tabla_err.setRowCount(len(errores))
            for i, e in enumerate(errores):
                tabla_err.setItem(i, 0, QTableWidgetItem(e["nombre"]))
                tabla_err.setItem(i, 1, QTableWidgetItem(e["motivo"]))
            v3.addWidget(tabla_err)
            tabs.addTab(tab_err, f"Errores ({total_err})")

        if not omitidos and not errores:
            layout.addWidget(QLabel("Todo se importó sin inconvenientes."))

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.reject)
        layout.addWidget(btn_cerrar)

    def _aceptar_forzar(self):
        self.nombres_a_forzar = {
            nombre for nombre, cb in self._checks.items() if cb.isChecked()
        }
        if not self.nombres_a_forzar:
            QMessageBox.information(self, "Sin selección", "No seleccionaste ningún producto.")
            return
        self.accept()
