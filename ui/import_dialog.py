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
        self.rb_prev = QRadioButton("Preventista")
        self.rb_min.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.rb_min)
        grp.addButton(self.rb_may)
        grp.addButton(self.rb_prev)
        tipo_layout.addWidget(self.rb_min)
        tipo_layout.addWidget(self.rb_may)
        tipo_layout.addWidget(self.rb_prev)
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
        if self.rb_may.isChecked():
            return "mayorista"
        if self.rb_prev.isChecked():
            return "preventista"
        return "minorista"

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
        from services.pedix_importer import escanear_nombres_sin_coincidencia, importar_desde_pedix
        from services.nombre_alias_service import cargar_aliases, guardar_aliases

        # ── Paso 1: detectar nombres sin coincidencia y pedir aliases ──
        aliases = cargar_aliases()
        try:
            sin_coincidencia = escanear_nombres_sin_coincidencia(
                self._archivo, self._tipo(), aliases=aliases
            )
        except Exception as e:
            QMessageBox.critical(self, "Error escaneando archivo", str(e))
            return

        if sin_coincidencia:
            resolver = _AliasResolverDialog(sin_coincidencia, self)
            if resolver.exec() == QDialog.Rejected:
                return
            nuevos = resolver.aliases_confirmados()
            if nuevos:
                guardar_aliases({**aliases, **nuevos})

        # ── Paso 2: importar con aliases ya guardados ──
        extra_map = self._extra_map_actual()
        session = SessionLocal()
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


class _AliasResolverDialog(QDialog):
    """
    Muestra los productos del archivo Pedix que no se encontraron en la BD
    y permite al usuario confirmar a qué producto corresponde cada uno
    (o marcarlo como producto nuevo).

    Los aliases confirmados se guardan en nombre_aliases.json y el importer
    los usa en la siguiente ejecución.
    """

    def __init__(self, sin_coincidencia, parent=None):
        """
        sin_coincidencia: lista de dicts con
            {"nombre_pedix": str, "nombre_stripped": str|None, "matches": [(score, db_nombre)]}
        """
        super().__init__(parent)
        self.setWindowTitle("Productos sin coincidencia — confirmar aliases")
        self.setMinimumSize(820, 540)
        self._combos = {}  # {nombre_pedix: QComboBox}

        main_layout = QVBoxLayout(self)

        lbl = QLabel(
            f"Se encontraron <b>{len(sin_coincidencia)}</b> producto(s) del archivo que no "
            "coinciden con ningún nombre en la base de datos.<br>"
            "Para cada uno, seleccioná a qué producto de la BD corresponde, "
            "o dejalo como <i>«Producto nuevo»</i> si debe crearse."
        )
        lbl.setWordWrap(True)
        main_layout.addWidget(lbl)

        # Nota sobre patrones de pack
        nota = QLabel(
            "<small><i>Nota: los descriptores de pack como x18u, x24u se "
            "ignoran al buscar coincidencias &mdash; 'Chocman x18u Baño semiamargo' se "
            "compara como 'Chocman Baño semiamargo'.</i></small>"
        )
        nota.setWordWrap(True)
        main_layout.addWidget(nota)

        # ── Tabla de resolución ──
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(4)

        for item in sin_coincidencia:
            nombre_pedix = item["nombre_pedix"]
            nombre_stripped = item["nombre_stripped"]
            matches = item["matches"]

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 4, 4, 4)

            # Etiqueta con el nombre del archivo
            lbl_nombre = QLabel()
            texto = f"<b>{nombre_pedix}</b>"
            if nombre_stripped:
                texto += f"<br><small style='color:gray'>sin pack: <i>{nombre_stripped}</i></small>"
            lbl_nombre.setText(texto)
            lbl_nombre.setWordWrap(True)
            lbl_nombre.setMinimumWidth(280)
            lbl_nombre.setMaximumWidth(380)
            row_layout.addWidget(lbl_nombre)

            # Combo con sugerencias
            combo = QComboBox()
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            for score, db_nombre in matches:
                combo.addItem(f"[{score:.0%}]  {db_nombre}", db_nombre)
            combo.addItem("— Producto nuevo (no crear alias) —", None)

            # Pre-seleccionar la mejor sugerencia si supera 60 %
            if matches and matches[0][0] >= 0.60:
                combo.setCurrentIndex(0)
            else:
                combo.setCurrentIndex(len(matches))

            self._combos[nombre_pedix] = combo
            row_layout.addWidget(combo)

            scroll_layout.addWidget(row_widget)

        scroll_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        # ── Botones ──
        btn_layout = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar importación")
        btn_cancelar.clicked.connect(self.reject)
        btn_continuar = QPushButton("Guardar aliases y continuar")
        btn_continuar.setDefault(True)
        btn_continuar.clicked.connect(self.accept)
        btn_layout.addWidget(btn_cancelar)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_continuar)
        main_layout.addLayout(btn_layout)

    def aliases_confirmados(self):
        """Retorna {nombre_pedix: nombre_db} para los combos donde el usuario eligió un alias."""
        result = {}
        for nombre_pedix, combo in self._combos.items():
            db_nombre = combo.currentData()
            if db_nombre is not None:
                result[nombre_pedix] = db_nombre
        return result


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
