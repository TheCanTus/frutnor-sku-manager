import json

from version import VERSION
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QAbstractItemView, QFileDialog, QHeaderView,
    QTabWidget, QLabel, QProgressDialog,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from sqlalchemy import or_

from database.db import SessionLocal
from database.models import SKU, Producto, Categoria, Presentacion
from services.product_service import crear_producto, editar_producto, eliminar_producto
from services.excel_export import exportar_excel
from ui.dialogs import NuevoProductoDialog
from ui.edit_dialog import EditarProductoDialog


_TIENDA_ABREV = {"minorista": "min", "mayorista": "may", "preventista": "prev"}


class _UpdateChecker(QThread):
    resultado = Signal(object)  # (version, url, notas) o None

    def run(self):
        try:
            from core.paths import get_app_dir
            import json as _json
            cfg_path = get_app_dir() / "config.json"
            token = ""
            if cfg_path.exists():
                token = _json.loads(cfg_path.read_text(encoding="utf-8")).get("github_token", "")
            from services.updater import verificar_actualizacion
            self.resultado.emit(verificar_actualizacion(token=token))
        except Exception:
            self.resultado.emit(None)


def _fmt_tiendas(raw):
    try:
        lst = json.loads(raw or '["minorista"]')
    except (ValueError, TypeError):
        lst = ["minorista"]
    return ", ".join(_TIENDA_ABREV.get(t, t) for t in lst) or "—"



class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SKU Manager v{VERSION}")
        self.resize(1100, 680)

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        # ── Pestaña Productos ──
        productos_widget = QWidget()
        layout = QVBoxLayout()
        productos_widget.setLayout(layout)
        tabs.addTab(productos_widget, "Productos")

        # Barra de búsqueda
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por SKU, nombre, categoría o tienda...")
        layout.addWidget(self.search)

        # Tabla: 7 columnas
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Tiendas", "Categoría", "Grupo", "SKU Base", "SKU", "Producto", "Presentación"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        # Barra de botones
        btn_bar = QHBoxLayout()
        self.btn_nuevo = QPushButton("Nuevo")
        self.btn_editar = QPushButton("Editar")
        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_exportar = QPushButton("Exportar Excel")
        self.btn_bom = QPushButton("Exportar BoMs")

        for btn in [self.btn_nuevo, self.btn_editar, self.btn_eliminar,
                    self.btn_exportar, self.btn_bom]:
            btn_bar.addWidget(btn)
        btn_bar.addStretch()

        self.btn_editar.setEnabled(False)
        self.btn_eliminar.setEnabled(False)
        layout.addLayout(btn_bar)

        # ── Pestaña Precios ──
        from ui.precios_widget import PreciosWidget
        self.precios_widget = PreciosWidget()
        tabs.addTab(self.precios_widget, "Precios")

        # ── Pestaña Stock ──
        from ui.stock_widget import StockWidget
        self.stock_widget = StockWidget()
        tabs.addTab(self.stock_widget, "Stock")

        # ── Pestaña Configuración ──
        from ui.settings_widget import SettingsWidget
        self.settings_widget = SettingsWidget()
        tabs.addTab(self.settings_widget, "Configuración")

        tabs.currentChanged.connect(self._on_tab_changed)

        # Señales — debounce 300 ms para no consultar en cada tecla
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self.buscar_productos)
        self.search.textChanged.connect(self._search_timer.start)
        self.table.selectionModel().selectionChanged.connect(self._on_seleccion)

        self.btn_nuevo.clicked.connect(self.nuevo_producto)
        self.btn_editar.clicked.connect(self.abrir_editar)
        self.btn_eliminar.clicked.connect(self.confirmar_eliminar)
        self.btn_exportar.clicked.connect(self.exportar_excel)
        self.btn_bom.clicked.connect(self.exportar_boms)

        # Banner de actualización (oculto hasta que se detecte versión nueva)
        self._update_info = None
        self._update_banner = QLabel("")
        self._update_banner.setAlignment(Qt.AlignCenter)
        self._update_banner.setStyleSheet(
            "background:#1a6b3c; color:white; padding:6px; font-weight:bold;"
        )
        self._update_banner.setCursor(Qt.PointingHandCursor)
        self._update_banner.setVisible(False)
        self._update_banner.mousePressEvent = lambda _: self._aplicar_actualizacion()
        layout.addWidget(self._update_banner)

        self.cargar_productos()

        # Verificar actualizaciones 5 s después de abrir (sin bloquear el inicio)
        QTimer.singleShot(5000, self._verificar_actualizacion)

    # ─── Helpers ────────────────────────────────────────────────

    def _on_tab_changed(self, index):
        tabs = self.centralWidget()
        widget = tabs.widget(index)
        if widget is self.precios_widget:
            if not self.precios_widget._sku_ids or not self.precios_widget._cambios:
                self.precios_widget.cargar()
        elif widget is self.stock_widget:
            if not self.stock_widget._producto_ids or not self.stock_widget._cambios:
                self.stock_widget.cargar()

    def _on_seleccion(self):
        filas = len(self.table.selectionModel().selectedRows())
        self.btn_editar.setEnabled(filas == 1)
        self.btn_eliminar.setEnabled(filas >= 1)

    def _producto_seleccionado(self, session):
        row = self.table.currentRow()
        if row < 0:
            return None
        sku_str = self.table.item(row, 4).text()  # columna SKU (índice 4)
        sku = session.query(SKU).filter_by(sku=sku_str).first()
        return sku.producto if sku else None

    # ─── Carga / búsqueda ───────────────────────────────────────

    def cargar_productos(self):
        session = SessionLocal()
        registros = session.query(SKU).order_by(SKU.sku).all()
        self.llenar_tabla(registros)
        session.close()

    def buscar_productos(self):
        texto = self.search.text().strip()
        session = SessionLocal()
        query = session.query(SKU).join(Producto).join(Categoria)
        if texto:
            query = query.filter(
                or_(
                    SKU.sku.ilike(f"%{texto}%"),
                    SKU.tiendas.ilike(f"%{texto}%"),
                    Producto.nombre.ilike(f"%{texto}%"),
                    Producto.grupo.ilike(f"%{texto}%"),
                    Categoria.codigo.ilike(f"%{texto}%"),
                    Categoria.nombre.ilike(f"%{texto}%"),
                )
            )
        self.llenar_tabla(query.order_by(SKU.sku).all())
        session.close()

    def llenar_tabla(self, registros):
        self.table.clearContents()
        self.table.setRowCount(len(registros))
        for fila, sku in enumerate(registros):
            prod = sku.producto
            cat = prod.categoria
            valores = [
                _fmt_tiendas(sku.tiendas),
                cat.codigo,
                prod.grupo or "",
                prod.sku_base,
                sku.sku,
                prod.nombre,
                sku.presentacion,
            ]
            for col, val in enumerate(valores):
                self.table.setItem(fila, col, QTableWidgetItem(val))
        self.table.resizeColumnsToContents()

    # ─── Acciones CRUD ──────────────────────────────────────────

    def nuevo_producto(self):
        session = SessionLocal()
        categorias = session.query(Categoria).all()
        if not categorias:
            session.close()
            QMessageBox.warning(self, "Sin categorías", "Ejecute seed.py primero.")
            return
        presentaciones = session.query(Presentacion).order_by(Presentacion.codigo).all()
        dialog = NuevoProductoDialog(categorias, presentaciones, session=session)
        if dialog.exec():
            try:
                crear_producto(
                    session,
                    dialog.nombre.text(),
                    dialog.categoria.currentData(),
                    dialog.presentaciones_con_tiendas(),
                    grupo=dialog.grupo_texto(),
                )
                self.cargar_productos()
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))
        session.close()

    def abrir_editar(self):
        session = SessionLocal()
        producto = self._producto_seleccionado(session)
        if not producto:
            session.close()
            return
        presentaciones = session.query(Presentacion).order_by(Presentacion.codigo).all()
        producto = session.query(Producto).filter_by(id=producto.id).first()
        dialog = EditarProductoDialog(producto, presentaciones, session=session)
        if dialog.exec():
            agregar, quitar, actualizar = dialog.calcular_cambios()
            try:
                editar_producto(
                    session,
                    producto.id,
                    dialog.nombre.text(),
                    dialog.grupo_texto(),
                    agregar,
                    quitar,
                    actualizar_tiendas=actualizar,
                )
                self.cargar_productos()
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))
        session.close()

    def confirmar_eliminar(self):
        session = SessionLocal()

        filas_seleccionadas = self.table.selectionModel().selectedRows()
        producto_ids = set()
        nombres = []
        for idx in filas_seleccionadas:
            sku_str = self.table.item(idx.row(), 4).text()
            sku = session.query(SKU).filter_by(sku=sku_str).first()
            if sku and sku.producto_id not in producto_ids:
                producto_ids.add(sku.producto_id)
                nombres.append(sku.producto.nombre)

        if not producto_ids:
            session.close()
            return

        if len(nombres) == 1:
            msg = f"¿Eliminar «{nombres[0]}» y todos sus SKUs?"
        else:
            lista = "\n".join(f"• {n}" for n in nombres[:10])
            if len(nombres) > 10:
                lista += f"\n… y {len(nombres) - 10} más"
            msg = f"¿Eliminar {len(nombres)} productos y todos sus SKUs?\n\n{lista}"

        resp = QMessageBox.question(
            self, "Confirmar eliminación", msg, QMessageBox.Yes | QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            errores = []
            for pid in producto_ids:
                try:
                    eliminar_producto(session, pid)
                except ValueError as e:
                    errores.append(str(e))
            if errores:
                QMessageBox.warning(self, "Errores al eliminar", "\n".join(errores))
            self.cargar_productos()

        session.close()

    # ─── Export ─────────────────────────────────────────────────

    def exportar_boms(self):
        archivo, _ = QFileDialog.getSaveFileName(
            self, "Exportar BoMs sugeridas", "boms_sugeridas.xlsx", "Excel (*.xlsx)"
        )
        if not archivo:
            return
        session = SessionLocal()
        try:
            from services.bom_exporter import exportar_boms
            total = exportar_boms(session, archivo)
            QMessageBox.information(
                self, "Listo",
                f"Se exportaron {total} BoMs sugeridas.\n\n"
                "Revisá las filas en amarillo — son relaciones que no son múltiplos exactos "
                "y necesitan verificación manual.\n\n"
                "La segunda hoja lista los productos con una sola presentación (no necesitan BoM)."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def exportar_excel(self):
        archivo, _ = QFileDialog.getSaveFileName(
            self, "Exportar Excel", "productos.xlsx", "Excel (*.xlsx)"
        )
        if not archivo:
            return
        session = SessionLocal()
        try:
            exportar_excel(session, archivo)
            QMessageBox.information(self, "Éxito", "Archivo exportado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    # ─── Actualizaciones ────────────────────────────────────────

    def _verificar_actualizacion(self):
        self._checker = _UpdateChecker(self)
        self._checker.resultado.connect(self._on_update_resultado)
        self._checker.start()

    def _on_update_resultado(self, resultado):
        if not resultado:
            return
        version, url, notas = resultado
        self._update_info = (version, url, notas)
        self._update_banner.setText(
            f"  Nueva versión disponible: v{version}  —  Hacé clic aquí para actualizar  "
        )
        self._update_banner.setVisible(True)

    def _aplicar_actualizacion(self):
        if not self._update_info:
            return
        version, url, notas = self._update_info
        msg = f"Versión disponible: {version}\n\n"
        if notas:
            msg += f"Novedades:\n{notas[:600]}\n\n"
        msg += "¿Descargar e instalar ahora? El programa se cerrará y se reabrirá automáticamente."
        resp = QMessageBox.question(self, "Actualizar SKU Manager", msg,
                                    QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return

        progress = QProgressDialog("Descargando actualización…", None, 0, 100, self)
        progress.setWindowTitle("Actualizando")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        try:
            from core.paths import get_app_dir
            import json as _json
            cfg_path = get_app_dir() / "config.json"
            token = ""
            if cfg_path.exists():
                token = _json.loads(cfg_path.read_text(encoding="utf-8")).get("github_token", "")

            from services.updater import descargar_e_instalar
            descargar_e_instalar(url, token=token, progreso_callback=progress.setValue)
            progress.close()
            QMessageBox.information(
                self, "Listo",
                "Descarga completa. El programa se cerrará y la nueva versión se abrirá en segundos."
            )
            self.close()
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error al actualizar", str(e))
