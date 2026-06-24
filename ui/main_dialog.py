import csv
import json
from pathlib import Path

from qgis.core import (
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsMapLayerType,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant, Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.project_manager import ProjectManager


class MainDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.project_manager = ProjectManager()
        self.current_project = None

        self.setWindowTitle("SmartGrain")
        self.resize(760, 520)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_project_tab(), "Projeto")
        self.tabs.addTab(self._build_fields_tab(), "Talhões")
        self.tabs.addTab(self._build_data_tab(), "Dados")
        self.tabs.addTab(self._build_analysis_tab(), "Análises")
        self.tabs.addTab(self._build_prescription_tab(), "Prescrição")
        self.tabs.addTab(self._build_export_tab(), "Exportação")

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self._build_header())
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _build_header(self):
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 8)

        logo_label = QLabel()
        logo_path = self._logo_path()

        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            logo_label.setPixmap(
                pixmap.scaled(
                    180,
                    64,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            logo_label.setFixedSize(190, 70)
        else:
            logo_label.setText("SmartGrain")
            logo_label.setStyleSheet("font-size: 22px; font-weight: 700;")

        logo_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(logo_label)
        layout.addStretch()
        return header

    def _logo_path(self):
        return Path(__file__).resolve().parents[1] / "assets" / "logo.png"

    def _build_project_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        project_box = QGroupBox("Informações do projeto")
        form = QFormLayout(project_box)

        self.project_name_input = QLineEdit()
        self.property_input = QLineEdit()
        self.crop_season_input = QLineEdit()
        self.technician_input = QLineEdit()
        self.project_dir_input = QLineEdit()
        self.project_dir_input.setReadOnly(True)

        choose_dir_button = QPushButton("Escolher pasta")
        choose_dir_button.clicked.connect(self._choose_project_dir)

        project_dir_layout = QHBoxLayout()
        project_dir_layout.addWidget(self.project_dir_input)
        project_dir_layout.addWidget(choose_dir_button)

        form.addRow("Nome:", self.project_name_input)
        form.addRow("Propriedade:", self.property_input)
        form.addRow("Safra:", self.crop_season_input)
        form.addRow("Responsável técnico:", self.technician_input)
        form.addRow("Pasta:", project_dir_layout)

        actions = QHBoxLayout()
        self.new_project_button = QPushButton("Novo projeto")
        self.new_project_button.clicked.connect(self._create_project)

        self.open_project_button = QPushButton("Abrir projeto")
        self.open_project_button.clicked.connect(self._open_project)

        actions.addWidget(self.new_project_button)
        actions.addWidget(self.open_project_button)
        actions.addStretch()

        layout.addWidget(project_box)
        layout.addLayout(actions)
        layout.addStretch()
        return tab

    def _choose_project_dir(self):
        project_dir = QFileDialog.getExistingDirectory(
            self,
            "Escolher pasta do projeto",
            self.project_dir_input.text(),
        )

        if project_dir:
            self.project_dir_input.setText(project_dir)

    def _create_project(self):
        project_dir = self.project_dir_input.text().strip()

        if not project_dir:
            QMessageBox.warning(
                self,
                "Projeto",
                "Escolha uma pasta para salvar o projeto.",
            )
            return

        if not self.project_name_input.text().strip():
            QMessageBox.warning(
                self,
                "Projeto",
                "Informe o nome do projeto.",
            )
            return

        project_data = self._collect_project_data()
        self.current_project = self.project_manager.create_project(
            project_dir,
            project_data,
        )

        QMessageBox.information(
            self,
            "Projeto",
            "Projeto criado com sucesso.",
        )
        self._restore_selected_field_layer()
        self._restore_selected_soil_sample_layer()
        self._restore_analysis_options()
        self._restore_prescription_options()
        self._restore_export_options()

    def _open_project(self):
        project_file, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir projeto",
            self.project_dir_input.text(),
            "Projetos SmartGrain (projeto.json);;Arquivos JSON (*.json)",
        )

        if not project_file:
            return

        try:
            self.current_project = self.project_manager.open_project(project_file)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Projeto",
                f"Não foi possível abrir o projeto:\n{error}",
            )
            return

        self._fill_project_form(self.current_project)
        self._restore_selected_field_layer()
        self._restore_selected_soil_sample_layer()
        self._restore_analysis_options()
        self._restore_prescription_options()
        self._restore_export_options()
        QMessageBox.information(
            self,
            "Projeto",
            "Projeto aberto com sucesso.",
        )

    def _collect_project_data(self):
        return {
            "nome": self.project_name_input.text(),
            "propriedade": self.property_input.text(),
            "safra": self.crop_season_input.text(),
            "responsavel": self.technician_input.text(),
        }

    def _fill_project_form(self, project_data):
        self.project_name_input.setText(project_data.get("nome", ""))
        self.property_input.setText(project_data.get("propriedade", ""))
        self.crop_season_input.setText(project_data.get("safra", ""))
        self.technician_input.setText(project_data.get("responsavel", ""))
        self.project_dir_input.setText(project_data.get("diretorio", ""))

    def _build_fields_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        fields_box = QGroupBox("Camada de talhões")
        form = QFormLayout(fields_box)

        self.field_layer_combo = QComboBox()
        self.field_layer_combo.setMinimumWidth(360)
        self.field_layer_combo.currentIndexChanged.connect(
            self._update_field_layer_summary
        )

        refresh_button = QPushButton("Atualizar camadas")
        refresh_button.clicked.connect(self._load_field_layers)

        save_button = QPushButton("Salvar camada de talhões")
        save_button.clicked.connect(self._save_field_layer)

        layer_layout = QHBoxLayout()
        layer_layout.addWidget(self.field_layer_combo)
        layer_layout.addWidget(refresh_button)

        form.addRow("Camada:", layer_layout)

        self.field_layer_status = QLabel(
            "Carregue uma camada vetorial de polígonos no QGIS e clique em Atualizar camadas."
        )
        self.field_layer_status.setWordWrap(True)

        self.field_layer_summary = QLabel("Nenhuma camada selecionada.")
        self.field_layer_summary.setWordWrap(True)
        self.field_layer_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.field_layer_summary.setStyleSheet(
            "background: #f6f8fa; border: 1px solid #d0d7de; padding: 8px;"
        )

        actions = QHBoxLayout()
        actions.addWidget(save_button)
        actions.addStretch()

        layout.addWidget(fields_box)
        layout.addWidget(self.field_layer_status)
        layout.addWidget(self.field_layer_summary)
        layout.addLayout(actions)
        layout.addStretch()

        self._load_field_layers()
        return tab

    def _load_field_layers(self):
        if not hasattr(self, "field_layer_combo"):
            return

        current_layer_id = self.field_layer_combo.currentData()
        self.field_layer_combo.clear()

        polygon_layers = self._polygon_layers()

        if not polygon_layers:
            self.field_layer_combo.addItem("Nenhuma camada de polígono encontrada", "")
            self.field_layer_status.setText(
                "Nenhuma camada vetorial de polígonos foi encontrada no projeto QGIS."
            )
            self.field_layer_summary.setText("Nenhuma camada selecionada.")
            return

        for layer in polygon_layers:
            self.field_layer_combo.addItem(layer.name(), layer.id())

        selected_layer_id = self._saved_field_layer_id() or current_layer_id
        self._select_field_layer(selected_layer_id)
        self.field_layer_status.setText(
            f"{len(polygon_layers)} camada(s) de polígono disponível(is)."
        )
        self._update_field_layer_summary()

    def _save_field_layer(self):
        if not self.current_project:
            QMessageBox.warning(
                self,
                "Talhões",
                "Crie ou abra um projeto antes de salvar a camada de talhões.",
            )
            return

        layer_id = self.field_layer_combo.currentData()

        if not layer_id:
            QMessageBox.warning(
                self,
                "Talhões",
                "Selecione uma camada de polígonos válida.",
            )
            return

        layer = QgsProject.instance().mapLayer(layer_id)

        if layer is None:
            QMessageBox.warning(
                self,
                "Talhões",
                "A camada selecionada não está mais carregada no QGIS.",
            )
            self._load_field_layers()
            return

        summary = self._field_layer_summary(layer)
        self.current_project["talhoes"] = {
            "camada": {
                "id": layer.id(),
                "nome": layer.name(),
                "fonte": layer.source(),
            },
            "resumo": summary,
        }

        self.current_project["camada_talhoes"] = {
            "id": layer.id(),
            "nome": layer.name(),
            "fonte": layer.source(),
        }

        try:
            self.project_manager.save_project(self.current_project)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Talhões",
                f"Não foi possível salvar a camada de talhões:\n{error}",
            )
            return

        self.field_layer_status.setText(
            f"Camada de talhões salva: {layer.name()}"
        )
        self.field_layer_summary.setText(self._format_field_summary(summary))
        self._restore_analysis_options()
        QMessageBox.information(
            self,
            "Talhões",
            "Camada de talhões salva no projeto.",
        )

    def _update_field_layer_summary(self):
        if not hasattr(self, "field_layer_summary"):
            return

        layer_id = self.field_layer_combo.currentData()

        if not layer_id:
            self.field_layer_summary.setText("Nenhuma camada selecionada.")
            return

        layer = QgsProject.instance().mapLayer(layer_id)

        if layer is None:
            self.field_layer_summary.setText(
                "A camada selecionada não está mais carregada no QGIS."
            )
            return

        self.field_layer_summary.setText(
            self._format_field_summary(self._field_layer_summary(layer))
        )

    def _field_layer_summary(self, layer):
        feature_count = layer.featureCount()
        invalid_geometry_count = 0
        empty_geometry_count = 0
        total_area_m2 = 0.0
        distance_area = QgsDistanceArea()
        crs = layer.crs()

        if crs.isValid():
            distance_area.setSourceCrs(crs, QgsProject.instance().transformContext())

        distance_area.setEllipsoid(QgsProject.instance().ellipsoid() or "WGS84")

        for feature in layer.getFeatures():
            geometry = feature.geometry()

            if geometry is None or geometry.isEmpty():
                empty_geometry_count += 1
                continue

            if not geometry.isGeosValid():
                invalid_geometry_count += 1

            total_area_m2 += distance_area.measureArea(geometry)

        warnings = []

        if feature_count == 0:
            warnings.append("A camada não possui feições.")

        if not crs.isValid():
            warnings.append("A camada não possui sistema de coordenadas válido.")

        if empty_geometry_count:
            warnings.append(f"{empty_geometry_count} feição(ões) sem geometria.")

        if invalid_geometry_count:
            warnings.append(f"{invalid_geometry_count} geometria(s) inválida(s).")

        return {
            "quantidade_talhoes": int(feature_count),
            "area_total_ha": round(total_area_m2 / 10000, 4),
            "crs": crs.authid() or crs.description() or "Indefinido",
            "crs_valido": crs.isValid(),
            "geometrias_vazias": empty_geometry_count,
            "geometrias_invalidas": invalid_geometry_count,
            "fonte": layer.source(),
            "avisos": warnings,
        }

    def _format_field_summary(self, summary):
        lines = [
            f"Talhões: {summary['quantidade_talhoes']}",
            f"Área total: {summary['area_total_ha']:.4f} ha",
            f"SRC/CRS: {summary['crs']}",
            f"Geometrias vazias: {summary['geometrias_vazias']}",
            f"Geometrias inválidas: {summary['geometrias_invalidas']}",
        ]

        if summary["avisos"]:
            lines.append("")
            lines.append("Avisos:")
            lines.extend(f"- {warning}" for warning in summary["avisos"])
        else:
            lines.append("")
            lines.append("Validação básica: sem avisos.")

        return "\n".join(lines)

    def _polygon_layers(self):
        layers = []

        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() != QgsMapLayerType.VectorLayer:
                continue

            if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
                continue

            layers.append(layer)

        return sorted(layers, key=lambda layer: layer.name().lower())

    def _saved_field_layer_id(self):
        if not self.current_project:
            return None

        fields = self.current_project.get("talhoes", {})
        field_layer = fields.get("camada") or self.current_project.get(
            "camada_talhoes", {}
        )
        return field_layer.get("id")

    def _restore_selected_field_layer(self):
        if not hasattr(self, "field_layer_combo"):
            return

        self._load_field_layers()
        fields = (self.current_project or {}).get("talhoes", {})
        field_layer = fields.get("camada") or (self.current_project or {}).get(
            "camada_talhoes"
        )

        if field_layer:
            self.field_layer_status.setText(
                f"Camada de talhões salva: {field_layer.get('nome', '')}"
            )

        summary = fields.get("resumo")

        if summary:
            self.field_layer_summary.setText(self._format_field_summary(summary))

    def _select_field_layer(self, layer_id):
        self._select_combo_layer(self.field_layer_combo, layer_id)

    def _select_combo_layer(self, combo, layer_id):
        if not layer_id:
            return

        index = combo.findData(layer_id)

        if index >= 0:
            combo.setCurrentIndex(index)

    def _build_data_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        data_box = QGroupBox("Amostras de solo")
        form = QFormLayout(data_box)

        self.soil_sample_layer_combo = QComboBox()
        self.soil_sample_layer_combo.setMinimumWidth(360)
        self.soil_sample_layer_combo.currentIndexChanged.connect(
            self._update_soil_sample_summary
        )

        refresh_button = QPushButton("Atualizar camadas")
        refresh_button.clicked.connect(self._load_soil_sample_layers)

        save_button = QPushButton("Salvar amostras de solo")
        save_button.clicked.connect(self._save_soil_sample_layer)

        layer_layout = QHBoxLayout()
        layer_layout.addWidget(self.soil_sample_layer_combo)
        layer_layout.addWidget(refresh_button)

        form.addRow("Camada:", layer_layout)

        self.soil_sample_status = QLabel(
            "Carregue uma camada vetorial de pontos no QGIS e clique em Atualizar camadas."
        )
        self.soil_sample_status.setWordWrap(True)

        self.soil_sample_summary = QLabel("Nenhuma camada selecionada.")
        self.soil_sample_summary.setWordWrap(True)
        self.soil_sample_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.soil_sample_summary.setStyleSheet(
            "background: #f6f8fa; border: 1px solid #d0d7de; padding: 8px;"
        )

        actions = QHBoxLayout()
        actions.addWidget(save_button)
        actions.addStretch()

        layout.addWidget(data_box)
        layout.addWidget(self.soil_sample_status)
        layout.addWidget(self.soil_sample_summary)
        layout.addLayout(actions)
        layout.addStretch()

        self._load_soil_sample_layers()
        return tab

    def _load_soil_sample_layers(self):
        if not hasattr(self, "soil_sample_layer_combo"):
            return

        current_layer_id = self.soil_sample_layer_combo.currentData()
        self.soil_sample_layer_combo.clear()

        point_layers = self._point_layers()

        if not point_layers:
            self.soil_sample_layer_combo.addItem("Nenhuma camada de ponto encontrada", "")
            self.soil_sample_status.setText(
                "Nenhuma camada vetorial de pontos foi encontrada no projeto QGIS."
            )
            self.soil_sample_summary.setText("Nenhuma camada selecionada.")
            return

        for layer in point_layers:
            self.soil_sample_layer_combo.addItem(layer.name(), layer.id())

        selected_layer_id = self._saved_soil_sample_layer_id() or current_layer_id
        self._select_combo_layer(self.soil_sample_layer_combo, selected_layer_id)
        self.soil_sample_status.setText(
            f"{len(point_layers)} camada(s) de ponto disponível(is)."
        )
        self._update_soil_sample_summary()

    def _save_soil_sample_layer(self):
        if not self.current_project:
            QMessageBox.warning(
                self,
                "Dados",
                "Crie ou abra um projeto antes de salvar as amostras de solo.",
            )
            return

        layer_id = self.soil_sample_layer_combo.currentData()

        if not layer_id:
            QMessageBox.warning(
                self,
                "Dados",
                "Selecione uma camada de pontos válida.",
            )
            return

        layer = QgsProject.instance().mapLayer(layer_id)

        if layer is None:
            QMessageBox.warning(
                self,
                "Dados",
                "A camada selecionada não está mais carregada no QGIS.",
            )
            self._load_soil_sample_layers()
            return

        summary = self._soil_sample_summary(layer)
        data = self.current_project.setdefault("dados", {})
        data["amostras_solo"] = {
            "camada": {
                "id": layer.id(),
                "nome": layer.name(),
                "fonte": layer.source(),
            },
            "resumo": summary,
        }

        try:
            self.project_manager.save_project(self.current_project)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Dados",
                f"Não foi possível salvar as amostras de solo:\n{error}",
            )
            return

        self.soil_sample_status.setText(
            f"Amostras de solo salvas: {layer.name()}"
        )
        self.soil_sample_summary.setText(self._format_soil_sample_summary(summary))
        self._restore_analysis_options()
        QMessageBox.information(
            self,
            "Dados",
            "Amostras de solo salvas no projeto.",
        )

    def _update_soil_sample_summary(self):
        if not hasattr(self, "soil_sample_summary"):
            return

        layer_id = self.soil_sample_layer_combo.currentData()

        if not layer_id:
            self.soil_sample_summary.setText("Nenhuma camada selecionada.")
            return

        layer = QgsProject.instance().mapLayer(layer_id)

        if layer is None:
            self.soil_sample_summary.setText(
                "A camada selecionada não está mais carregada no QGIS."
            )
            return

        self.soil_sample_summary.setText(
            self._format_soil_sample_summary(self._soil_sample_summary(layer))
        )

    def _soil_sample_summary(self, layer):
        crs = layer.crs()
        numeric_fields = self._numeric_field_names(layer)
        warnings = []
        feature_count = layer.featureCount()

        if feature_count == 0:
            warnings.append("A camada não possui pontos de amostragem.")

        if not crs.isValid():
            warnings.append("A camada não possui sistema de coordenadas válido.")

        if not numeric_fields:
            warnings.append("A camada não possui campos numéricos para análise.")

        return {
            "quantidade_pontos": int(feature_count),
            "crs": crs.authid() or crs.description() or "Indefinido",
            "crs_valido": crs.isValid(),
            "campos_numericos": numeric_fields,
            "quantidade_campos_numericos": len(numeric_fields),
            "fonte": layer.source(),
            "avisos": warnings,
        }

    def _format_soil_sample_summary(self, summary):
        fields = summary["campos_numericos"]
        field_text = ", ".join(fields) if fields else "Nenhum"

        lines = [
            f"Pontos de amostragem: {summary['quantidade_pontos']}",
            f"SRC/CRS: {summary['crs']}",
            f"Campos numéricos: {summary['quantidade_campos_numericos']}",
            f"Campos disponíveis: {field_text}",
        ]

        if summary["avisos"]:
            lines.append("")
            lines.append("Avisos:")
            lines.extend(f"- {warning}" for warning in summary["avisos"])
        else:
            lines.append("")
            lines.append("Validação básica: sem avisos.")

        return "\n".join(lines)

    def _point_layers(self):
        layers = []

        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() != QgsMapLayerType.VectorLayer:
                continue

            if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PointGeometry:
                continue

            layers.append(layer)

        return sorted(layers, key=lambda layer: layer.name().lower())

    def _numeric_field_names(self, layer):
        field_names = []
        numeric_type_names = (
            "int",
            "integer",
            "long",
            "double",
            "real",
            "float",
            "decimal",
            "numeric",
        )

        for field in layer.fields():
            if hasattr(field, "isNumeric") and field.isNumeric():
                field_names.append(field.name())
                continue

            type_name = field.typeName().lower()

            if any(name in type_name for name in numeric_type_names):
                field_names.append(field.name())

        return field_names

    def _saved_soil_sample_layer_id(self):
        if not self.current_project:
            return None

        data = self.current_project.get("dados", {})
        soil_samples = data.get("amostras_solo", {})
        layer = soil_samples.get("camada", {})
        return layer.get("id")

    def _restore_selected_soil_sample_layer(self):
        if not hasattr(self, "soil_sample_layer_combo"):
            return

        self._load_soil_sample_layers()
        data = (self.current_project or {}).get("dados", {})
        soil_samples = data.get("amostras_solo", {})
        layer = soil_samples.get("camada")

        if layer:
            self.soil_sample_status.setText(
                f"Amostras de solo salvas: {layer.get('nome', '')}"
            )

        summary = soil_samples.get("resumo")

        if summary:
            self.soil_sample_summary.setText(
                self._format_soil_sample_summary(summary)
            )

    def _build_analysis_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        analysis_box = QGroupBox("Amostras por talhão")
        form = QFormLayout(analysis_box)

        self.analysis_field_combo = QComboBox()
        self.analysis_field_combo.setMinimumWidth(240)

        refresh_button = QPushButton("Atualizar dados")
        refresh_button.clicked.connect(self._restore_analysis_options)

        run_button = QPushButton("Executar análise")
        run_button.clicked.connect(self._run_samples_by_field_analysis)

        field_layout = QHBoxLayout()
        field_layout.addWidget(self.analysis_field_combo)
        field_layout.addWidget(refresh_button)

        form.addRow("Atributo:", field_layout)

        self.analysis_status = QLabel(
            "Salve uma camada de talhões e uma camada de amostras de solo antes de executar."
        )
        self.analysis_status.setWordWrap(True)

        self.analysis_summary = QLabel("Nenhuma análise executada.")
        self.analysis_summary.setWordWrap(True)
        self.analysis_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.analysis_summary.setStyleSheet(
            "background: #f6f8fa; border: 1px solid #d0d7de; padding: 8px;"
        )

        actions = QHBoxLayout()
        actions.addWidget(run_button)
        actions.addStretch()

        layout.addWidget(analysis_box)
        layout.addWidget(self.analysis_status)
        layout.addWidget(self.analysis_summary)
        layout.addLayout(actions)
        layout.addStretch()

        self._restore_analysis_options()
        return tab

    def _restore_analysis_options(self):
        if not hasattr(self, "analysis_field_combo"):
            return

        current_field = self.analysis_field_combo.currentData()
        self.analysis_field_combo.clear()

        soil_layer = self._saved_soil_sample_layer()
        field_layer = self._saved_field_layer()

        if field_layer is None or soil_layer is None:
            self.analysis_field_combo.addItem("Nenhum campo disponível", "")
            self.analysis_status.setText(
                "Salve uma camada de talhões e uma camada de amostras de solo antes de executar."
            )
            self.analysis_summary.setText("Nenhuma análise executada.")
            return

        numeric_fields = self._numeric_field_names(soil_layer)
        self.analysis_field_combo.addItem("Somente contar pontos", "")

        for field_name in numeric_fields:
            self.analysis_field_combo.addItem(field_name, field_name)

        self._select_combo_layer(self.analysis_field_combo, current_field)
        self.analysis_status.setText(
            "Dados prontos para cruzar amostras de solo com talhões."
        )

        saved_analysis = (self.current_project or {}).get("analises", {}).get(
            "amostras_por_talhao"
        )

        if saved_analysis:
            self.analysis_summary.setText(
                self._format_samples_by_field_analysis(saved_analysis)
            )

    def _run_samples_by_field_analysis(self):
        if not self.current_project:
            QMessageBox.warning(
                self,
                "Análises",
                "Crie ou abra um projeto antes de executar a análise.",
            )
            return

        field_layer = self._saved_field_layer()
        soil_layer = self._saved_soil_sample_layer()

        if field_layer is None or soil_layer is None:
            QMessageBox.warning(
                self,
                "Análises",
                "Salve uma camada de talhões e uma camada de amostras de solo antes de executar.",
            )
            self._restore_analysis_options()
            return

        attribute_name = self.analysis_field_combo.currentData()
        analysis = self._samples_by_field_analysis(
            field_layer,
            soil_layer,
            attribute_name,
        )

        analyses = self.current_project.setdefault("analises", {})
        analyses["amostras_por_talhao"] = analysis

        try:
            self.project_manager.save_project(self.current_project)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Análises",
                f"Não foi possível salvar a análise:\n{error}",
            )
            return

        self.analysis_status.setText("Análise salva no projeto.")
        self.analysis_summary.setText(
            self._format_samples_by_field_analysis(analysis)
        )
        self._restore_prescription_options()
        self._restore_export_options()
        QMessageBox.information(
            self,
            "Análises",
            "Análise concluída e salva no projeto.",
        )

    def _samples_by_field_analysis(self, field_layer, soil_layer, attribute_name):
        soil_features = self._soil_sample_geometries_for_analysis(
            soil_layer,
            field_layer.crs(),
            attribute_name,
        )
        total_inside = 0
        results = []

        for field_feature in field_layer.getFeatures():
            field_geometry = field_feature.geometry()

            if field_geometry is None or field_geometry.isEmpty():
                continue

            matched_values = []
            sample_count = 0

            for sample in soil_features:
                if not field_geometry.contains(sample["geometry"]):
                    continue

                sample_count += 1

                if sample["value"] is not None:
                    matched_values.append(sample["value"])

            total_inside += sample_count
            average = None

            if matched_values:
                average = round(sum(matched_values) / len(matched_values), 4)

            results.append(
                {
                    "talhao_id": int(field_feature.id()),
                    "talhao_nome": self._field_feature_label(field_feature),
                    "quantidade_amostras": sample_count,
                    "media": average,
                }
            )

        return {
            "talhoes": results,
            "total_talhoes": len(results),
            "total_amostras": len(soil_features),
            "amostras_dentro_talhoes": total_inside,
            "amostras_fora_talhoes": max(len(soil_features) - total_inside, 0),
            "atributo": attribute_name or "",
            "camada_talhoes": field_layer.name(),
            "camada_amostras": soil_layer.name(),
        }

    def _soil_sample_geometries_for_analysis(
        self,
        soil_layer,
        target_crs,
        attribute_name,
    ):
        coordinate_transform = None

        if soil_layer.crs().isValid() and target_crs.isValid():
            if soil_layer.crs() != target_crs:
                coordinate_transform = QgsCoordinateTransform(
                    soil_layer.crs(),
                    target_crs,
                    QgsProject.instance(),
                )

        samples = []

        for feature in soil_layer.getFeatures():
            geometry = feature.geometry()

            if geometry is None or geometry.isEmpty():
                continue

            geometry = QgsGeometry(geometry)

            if coordinate_transform is not None:
                geometry.transform(coordinate_transform)

            value = None

            if attribute_name:
                raw_value = feature[attribute_name]

                if raw_value not in (None, ""):
                    try:
                        value = float(raw_value)
                    except (TypeError, ValueError):
                        value = None

            samples.append(
                {
                    "geometry": geometry,
                    "value": value,
                }
            )

        return samples

    def _field_feature_label(self, feature):
        preferred_names = ("nome", "name", "talhao", "talhão", "id", "codigo", "código")

        for field_name in preferred_names:
            if field_name in feature.fields().names():
                value = feature[field_name]

                if value not in (None, ""):
                    return str(value)

        return f"Talhão {feature.id()}"

    def _format_samples_by_field_analysis(self, analysis):
        attribute_name = analysis.get("atributo") or "nenhum"
        lines = [
            f"Camada de talhões: {analysis.get('camada_talhoes', '')}",
            f"Camada de amostras: {analysis.get('camada_amostras', '')}",
            f"Atributo analisado: {attribute_name}",
            f"Talhões analisados: {analysis.get('total_talhoes', 0)}",
            f"Amostras dentro dos talhões: {analysis.get('amostras_dentro_talhoes', 0)}",
            f"Amostras fora dos talhões: {analysis.get('amostras_fora_talhoes', 0)}",
            "",
            "Resumo por talhão:",
        ]

        for result in analysis.get("talhoes", []):
            line = (
                f"- {result['talhao_nome']}: "
                f"{result['quantidade_amostras']} amostra(s)"
            )

            if result.get("media") is not None:
                line += f", média {result['media']:.4f}"

            lines.append(line)

        return "\n".join(lines)

    def _saved_field_layer(self):
        if not self.current_project:
            return None

        fields = self.current_project.get("talhoes", {})
        layer_data = fields.get("camada") or self.current_project.get(
            "camada_talhoes", {}
        )
        return self._saved_layer_from_data(layer_data)

    def _saved_soil_sample_layer(self):
        if not self.current_project:
            return None

        data = self.current_project.get("dados", {})
        soil_samples = data.get("amostras_solo", {})
        return self._saved_layer_from_data(soil_samples.get("camada", {}))

    def _saved_layer_from_data(self, layer_data):
        if not layer_data:
            return None

        layer = QgsProject.instance().mapLayer(layer_data.get("id", ""))

        if layer is not None:
            return layer

        source = layer_data.get("fonte")
        name = layer_data.get("nome")

        for candidate in QgsProject.instance().mapLayers().values():
            if source and candidate.source() == source:
                return candidate

            if name and candidate.name() == name:
                return candidate

        return None

    def _build_prescription_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        prescription_box = QGroupBox("Prescrição por faixa")
        form = QFormLayout(prescription_box)

        self.prescription_attribute_label = QLabel("Nenhuma análise disponível.")

        self.prescription_low_limit_input = self._build_decimal_input(8.0)
        self.prescription_medium_limit_input = self._build_decimal_input(15.0)
        self.prescription_low_dose_input = self._build_decimal_input(120.0)
        self.prescription_medium_dose_input = self._build_decimal_input(80.0)
        self.prescription_high_dose_input = self._build_decimal_input(40.0)

        form.addRow("Atributo:", self.prescription_attribute_label)
        form.addRow("Baixo até:", self.prescription_low_limit_input)
        form.addRow("Médio até:", self.prescription_medium_limit_input)
        form.addRow("Dose para baixo:", self.prescription_low_dose_input)
        form.addRow("Dose para médio:", self.prescription_medium_dose_input)
        form.addRow("Dose para alto:", self.prescription_high_dose_input)

        generate_button = QPushButton("Gerar prescrição")
        generate_button.clicked.connect(self._generate_field_prescription)

        self.prescription_status = QLabel(
            "Execute uma análise com atributo numérico antes de gerar a prescrição."
        )
        self.prescription_status.setWordWrap(True)

        self.prescription_summary = QLabel("Nenhuma prescrição gerada.")
        self.prescription_summary.setWordWrap(True)
        self.prescription_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.prescription_summary.setStyleSheet(
            "background: #f6f8fa; border: 1px solid #d0d7de; padding: 8px;"
        )

        actions = QHBoxLayout()
        actions.addWidget(generate_button)
        actions.addStretch()

        layout.addWidget(prescription_box)
        layout.addWidget(self.prescription_status)
        layout.addWidget(self.prescription_summary)
        layout.addLayout(actions)
        layout.addStretch()

        self._restore_prescription_options()
        return tab

    def _build_decimal_input(self, value):
        input_widget = QDoubleSpinBox()
        input_widget.setRange(-1000000.0, 1000000.0)
        input_widget.setDecimals(4)
        input_widget.setValue(value)
        input_widget.setSingleStep(1.0)
        return input_widget

    def _restore_prescription_options(self):
        if not hasattr(self, "prescription_attribute_label"):
            return

        analysis = self._saved_samples_by_field_analysis()
        prescription = (self.current_project or {}).get("prescricoes", {}).get(
            "por_talhao"
        )

        if not analysis or not analysis.get("atributo"):
            self.prescription_attribute_label.setText("Nenhuma análise disponível.")
            self.prescription_status.setText(
                "Execute uma análise com atributo numérico antes de gerar a prescrição."
            )
            self.prescription_summary.setText("Nenhuma prescrição gerada.")
            return

        self.prescription_attribute_label.setText(analysis["atributo"])
        self.prescription_status.setText(
            "Análise disponível para gerar prescrição por talhão."
        )

        if prescription:
            rules = prescription.get("regras", {})
            self.prescription_low_limit_input.setValue(
                float(rules.get("baixo_ate", self.prescription_low_limit_input.value()))
            )
            self.prescription_medium_limit_input.setValue(
                float(
                    rules.get(
                        "medio_ate",
                        self.prescription_medium_limit_input.value(),
                    )
                )
            )
            self.prescription_low_dose_input.setValue(
                float(rules.get("dose_baixa", self.prescription_low_dose_input.value()))
            )
            self.prescription_medium_dose_input.setValue(
                float(
                    rules.get(
                        "dose_media",
                        self.prescription_medium_dose_input.value(),
                    )
                )
            )
            self.prescription_high_dose_input.setValue(
                float(rules.get("dose_alta", self.prescription_high_dose_input.value()))
            )
            self.prescription_summary.setText(
                self._format_field_prescription(prescription)
            )

    def _generate_field_prescription(self):
        if not self.current_project:
            QMessageBox.warning(
                self,
                "Prescrição",
                "Crie ou abra um projeto antes de gerar a prescrição.",
            )
            return

        analysis = self._saved_samples_by_field_analysis()

        if not analysis or not analysis.get("atributo"):
            QMessageBox.warning(
                self,
                "Prescrição",
                "Execute uma análise com atributo numérico antes de gerar a prescrição.",
            )
            self._restore_prescription_options()
            return

        low_limit = self.prescription_low_limit_input.value()
        medium_limit = self.prescription_medium_limit_input.value()

        if medium_limit < low_limit:
            QMessageBox.warning(
                self,
                "Prescrição",
                "O limite médio deve ser maior ou igual ao limite baixo.",
            )
            return

        prescription = self._field_prescription_from_analysis(
            analysis,
            {
                "baixo_ate": low_limit,
                "medio_ate": medium_limit,
                "dose_baixa": self.prescription_low_dose_input.value(),
                "dose_media": self.prescription_medium_dose_input.value(),
                "dose_alta": self.prescription_high_dose_input.value(),
            },
        )

        prescriptions = self.current_project.setdefault("prescricoes", {})
        prescriptions["por_talhao"] = prescription

        try:
            self.project_manager.save_project(self.current_project)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Prescrição",
                f"Não foi possível salvar a prescrição:\n{error}",
            )
            return

        self.prescription_status.setText("Prescrição salva no projeto.")
        self.prescription_summary.setText(
            self._format_field_prescription(prescription)
        )
        self._restore_export_options()
        QMessageBox.information(
            self,
            "Prescrição",
            "Prescrição gerada e salva no projeto.",
        )

    def _field_prescription_from_analysis(self, analysis, rules):
        results = []

        for field_result in analysis.get("talhoes", []):
            average = field_result.get("media")
            classification = "sem média"
            dose = None

            if average is not None:
                if average <= rules["baixo_ate"]:
                    classification = "baixo"
                    dose = rules["dose_baixa"]
                elif average <= rules["medio_ate"]:
                    classification = "médio"
                    dose = rules["dose_media"]
                else:
                    classification = "alto"
                    dose = rules["dose_alta"]

            results.append(
                {
                    "talhao_id": field_result.get("talhao_id"),
                    "talhao_nome": field_result.get("talhao_nome"),
                    "media": average,
                    "classe": classification,
                    "dose": dose,
                    "quantidade_amostras": field_result.get("quantidade_amostras", 0),
                }
            )

        return {
            "atributo": analysis.get("atributo", ""),
            "regras": rules,
            "resultados": results,
        }

    def _format_field_prescription(self, prescription):
        rules = prescription.get("regras", {})
        lines = [
            f"Atributo: {prescription.get('atributo', '')}",
            (
                "Regras: "
                f"baixo <= {rules.get('baixo_ate')}, "
                f"médio <= {rules.get('medio_ate')}, "
                "alto acima disso"
            ),
            (
                "Doses: "
                f"baixo {rules.get('dose_baixa')}, "
                f"médio {rules.get('dose_media')}, "
                f"alto {rules.get('dose_alta')}"
            ),
            "",
            "Prescrição por talhão:",
        ]

        for result in prescription.get("resultados", []):
            average = result.get("media")
            average_text = f"{average:.4f}" if average is not None else "sem média"
            dose = result.get("dose")
            dose_text = f"{dose:.4f}" if dose is not None else "sem dose"
            lines.append(
                f"- {result.get('talhao_nome')}: média {average_text}, "
                f"classe {result.get('classe')}, dose {dose_text}"
            )

        return "\n".join(lines)

    def _saved_samples_by_field_analysis(self):
        if not self.current_project:
            return None

        return self.current_project.get("analises", {}).get("amostras_por_talhao")

    def _build_export_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        export_box = QGroupBox("Exportação de resultados")
        form = QFormLayout(export_box)

        self.export_status = QLabel(
            "Salve um projeto e gere análises/prescrições para ativar a exportação."
        )
        self.export_status.setWordWrap(True)

        self.export_summary = QLabel("Nenhuma exportação gerada.")
        self.export_summary.setWordWrap(True)
        self.export_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.export_summary.setStyleSheet(
            "background: #f6f8fa; border: 1px solid #d0d7de; padding: 8px;"
        )

        export_analysis_csv_button = QPushButton("Análise (CSV)")
        export_analysis_csv_button.clicked.connect(self._export_analysis_to_csv)

        export_analysis_shp_button = QPushButton("Análise (Shapefile)")
        export_analysis_shp_button.clicked.connect(self._export_analysis_to_shapefile)

        export_prescription_csv_button = QPushButton("Prescrição (CSV)")
        export_prescription_csv_button.clicked.connect(self._export_prescription_to_csv)

        export_prescription_shp_button = QPushButton("Prescrição (Shapefile)")
        export_prescription_shp_button.clicked.connect(self._export_prescription_to_shapefile)

        export_package_button = QPushButton("Pacote Agrícola")
        export_package_button.clicked.connect(self._export_agricultural_package)

        actions = QHBoxLayout()
        actions.addWidget(export_analysis_csv_button)
        actions.addWidget(export_analysis_shp_button)
        actions.addWidget(export_prescription_csv_button)
        actions.addWidget(export_prescription_shp_button)
        actions.addWidget(export_package_button)
        actions.addStretch()

        layout.addWidget(export_box)
        layout.addWidget(self.export_status)
        layout.addWidget(self.export_summary)
        layout.addLayout(actions)
        layout.addStretch()

        self._restore_export_options()
        return tab

    def _restore_export_options(self):
        export_ready = False
        analysis = self._saved_samples_by_field_analysis()
        prescription = (self.current_project or {}).get("prescricoes", {}).get("por_talhao")

        if self.current_project and analysis:
            export_ready = True

        if export_ready:
            self.export_status.setText(
                "Exportação disponível. Exporte análise ou prescrição nos formatos desejados."
            )
            self.export_summary.setText(
                "Use os botões abaixo para gerar arquivos (CSV, Shapefile ou pacote agrícola)."
            )
        else:
            self.export_status.setText(
                "Salve um projeto e gere análises/prescrições para ativar a exportação."
            )
            self.export_summary.setText("Nenhuma exportação gerada.")

    def _choose_export_folder(self, default_dir=None):
        """Abre diálogo para escolher pasta de exportação."""
        if default_dir is None:
            default_dir = (
                self.current_project.get("diretorio")
                if self.current_project
                else ""
            )

        folder = QFileDialog.getExistingDirectory(
            self,
            "Escolher pasta para exportação",
            default_dir,
        )
        return folder if folder else None

    def _export_project(self):
        if not self.current_project:
            QMessageBox.warning(
                self,
                "Exportação",
                "Abra ou crie um projeto antes de exportar.",
            )
            return

        project_dir = self.current_project.get("diretorio")

        if not project_dir:
            QMessageBox.critical(
                self,
                "Exportação",
                "O projeto não possui diretório definido.",
            )
            return

        project_path = Path(project_dir)
        export_file = project_path / "projeto_exportado.json"

        try:
            with export_file.open("w", encoding="utf-8") as file:
                json.dump(self.current_project, file, ensure_ascii=False, indent=2)
        except OSError as error:
            QMessageBox.critical(
                self,
                "Exportação",
                f"Não foi possível exportar o projeto:\n{error}",
            )
            return

        self.export_summary.setText(
            f"Projeto exportado para: {export_file.name}"
        )
        QMessageBox.information(
            self,
            "Exportação",
            "Projeto exportado com sucesso.",
        )

    def _export_analysis_to_csv(self):
        analysis = self._saved_samples_by_field_analysis()

        if not analysis:
            QMessageBox.warning(
                self,
                "Exportação",
                "Execute uma análise antes de exportar para CSV.",
            )
            return

        export_dir = self._choose_export_folder()

        if not export_dir:
            return

        csv_path = Path(export_dir) / "analise_talhoes.csv"
        try:
            with csv_path.open("w", encoding="utf-8", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    "talhao_id",
                    "talhao_nome",
                    "quantidade_amostras",
                    "media",
                ])

                for result in analysis.get("talhoes", []):
                    writer.writerow([
                        result.get("talhao_id"),
                        result.get("talhao_nome"),
                        result.get("quantidade_amostras", 0),
                        result.get("media") if result.get("media") is not None else "",
                    ])
        except OSError as error:
            QMessageBox.critical(
                self,
                "Exportação",
                f"Não foi possível exportar a análise:\n{error}",
            )
            return

        self.export_summary.setText(
            f"Análise exportada para: {csv_path.name}"
        )
        QMessageBox.information(
            self,
            "Exportação",
            "Análise exportada para CSV com sucesso.",
        )

    def _export_analysis_to_shapefile(self):
        analysis = self._saved_samples_by_field_analysis()
        field_layer = self._saved_field_layer()

        if not analysis:
            QMessageBox.warning(
                self,
                "Exportação",
                "Execute uma análise antes de exportar para Shapefile.",
            )
            return

        if not field_layer:
            QMessageBox.warning(
                self,
                "Exportação",
                "Camada de talhões não encontrada.",
            )
            return

        export_dir = self._choose_export_folder()

        if not export_dir:
            return

        output_path = Path(export_dir) / "analise_talhoes.shp"

        try:
            memory_layer = self._create_analysis_layer_copy(field_layer, analysis)

            writer = QgsVectorFileWriter.create(
                str(output_path),
                memory_layer.fields(),
                memory_layer.wkbType(),
                field_layer.crs(),
            )

            if writer.hasError() != QgsVectorFileWriter.NoError:
                raise Exception(f"Erro ao criar shapefile: {writer.errorMessage()}")

            for feature in memory_layer.getFeatures():
                if not writer.addFeature(feature):
                    raise Exception(f"Erro ao adicionar feature: {writer.lastError()}")

            del writer

            self.export_summary.setText(
                f"Análise exportada para: {output_path.name}"
            )
            QMessageBox.information(
                self,
                "Exportação",
                "Análise exportada para Shapefile com sucesso.",
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "Exportação",
                f"Não foi possível exportar a análise para Shapefile:\n{error}",
            )

    def _create_analysis_layer_copy(self, field_layer, analysis):
        """Cria uma camada em memória com os resultados da análise."""
        memory_layer = QgsVectorLayer(
            f"{QgsWkbTypes.geometryType(field_layer.wkbType())}?crs={field_layer.crs().authid()}",
            "analise_temporaria",
            "memory",
        )

        provider = memory_layer.dataProvider()

        fields = QgsFields()
        fields.append(QgsField("talhao_id", QVariant.Int))
        fields.append(QgsField("talhao_nome", QVariant.String))
        fields.append(QgsField("quantidade_amostras", QVariant.Int))
        fields.append(QgsField("media", QVariant.Double))

        provider.addAttributes(fields)
        memory_layer.updateFields()

        analysis_by_id = {
            r["talhao_id"]: r for r in analysis.get("talhoes", [])
        }

        features = []

        for feature in field_layer.getFeatures():
            field_id = int(feature.id())
            result = analysis_by_id.get(field_id, {})

            new_feature = QgsFeature()
            new_feature.setGeometry(feature.geometry())

            attrs = [
                field_id,
                result.get("talhao_nome", ""),
                result.get("quantidade_amostras", 0),
                result.get("media"),
            ]

            new_feature.setAttributes(attrs)
            features.append(new_feature)

        provider.addFeatures(features)

        return memory_layer

    def _export_prescription_to_csv(self):
        prescription = (self.current_project or {}).get("prescricoes", {}).get("por_talhao")

        if not prescription:
            QMessageBox.warning(
                self,
                "Exportação",
                "Gere uma prescrição antes de exportar para CSV.",
            )
            return

        export_dir = self._choose_export_folder()

        if not export_dir:
            return

        csv_path = Path(export_dir) / "prescricao_talhoes.csv"
        try:
            with csv_path.open("w", encoding="utf-8", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    "talhao_id",
                    "talhao_nome",
                    "media",
                    "classe",
                    "dose",
                    "quantidade_amostras",
                ])

                for result in prescription.get("resultados", []):
                    writer.writerow([
                        result.get("talhao_id"),
                        result.get("talhao_nome"),
                        result.get("media") if result.get("media") is not None else "",
                        result.get("classe", ""),
                        result.get("dose") if result.get("dose") is not None else "",
                        result.get("quantidade_amostras", 0),
                    ])
        except OSError as error:
            QMessageBox.critical(
                self,
                "Exportação",
                f"Não foi possível exportar a prescrição:\n{error}",
            )
            return

        self.export_summary.setText(
            f"Prescrição exportada para: {csv_path.name}"
        )
        QMessageBox.information(
            self,
            "Exportação",
            "Prescrição exportada para CSV com sucesso.",
        )

    def _export_prescription_to_shapefile(self):
        prescription = (self.current_project or {}).get("prescricoes", {}).get("por_talhao")
        field_layer = self._saved_field_layer()

        if not prescription:
            QMessageBox.warning(
                self,
                "Exportação",
                "Gere uma prescrição antes de exportar para Shapefile.",
            )
            return

        if not field_layer:
            QMessageBox.warning(
                self,
                "Exportação",
                "Camada de talhões não encontrada.",
            )
            return

        export_dir = self._choose_export_folder()

        if not export_dir:
            return

        output_path = Path(export_dir) / "prescricao_talhoes.shp"

        try:
            memory_layer = self._create_prescription_layer_copy(field_layer, prescription)

            writer = QgsVectorFileWriter.create(
                str(output_path),
                memory_layer.fields(),
                memory_layer.wkbType(),
                field_layer.crs(),
            )

            if writer.hasError() != QgsVectorFileWriter.NoError:
                raise Exception(f"Erro ao criar shapefile: {writer.errorMessage()}")

            for feature in memory_layer.getFeatures():
                if not writer.addFeature(feature):
                    raise Exception(f"Erro ao adicionar feature: {writer.lastError()}")

            del writer

            self.export_summary.setText(
                f"Prescrição exportada para: {output_path.name}"
            )
            QMessageBox.information(
                self,
                "Exportação",
                "Prescrição exportada para Shapefile com sucesso.",
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "Exportação",
                f"Não foi possível exportar a prescrição para Shapefile:\n{error}",
            )

    def _create_prescription_layer_copy(self, field_layer, prescription):
        """Cria uma camada em memória com os resultados da prescrição."""
        memory_layer = QgsVectorLayer(
            f"{QgsWkbTypes.geometryType(field_layer.wkbType())}?crs={field_layer.crs().authid()}",
            "prescricao_temporaria",
            "memory",
        )

        provider = memory_layer.dataProvider()

        fields = QgsFields()
        fields.append(QgsField("talhao_id", QVariant.Int))
        fields.append(QgsField("talhao_nome", QVariant.String))
        fields.append(QgsField("media", QVariant.Double))
        fields.append(QgsField("classe", QVariant.String))
        fields.append(QgsField("dose", QVariant.Double))
        fields.append(QgsField("quantidade_amostras", QVariant.Int))

        provider.addAttributes(fields)
        memory_layer.updateFields()

        prescription_by_id = {
            r["talhao_id"]: r for r in prescription.get("resultados", [])
        }

        features = []

        for feature in field_layer.getFeatures():
            field_id = int(feature.id())
            result = prescription_by_id.get(field_id, {})

            new_feature = QgsFeature()
            new_feature.setGeometry(feature.geometry())

            attrs = [
                field_id,
                result.get("talhao_nome", ""),
                result.get("media"),
                result.get("classe", ""),
                result.get("dose"),
                result.get("quantidade_amostras", 0),
            ]

            new_feature.setAttributes(attrs)
            features.append(new_feature)

        provider.addFeatures(features)

        return memory_layer

    def _export_agricultural_package(self):
        """Exporta prescrição em formato de pacote agrícola (txt com coordenadas de aplicação)."""
        prescription = (self.current_project or {}).get("prescricoes", {}).get("por_talhao")
        field_layer = self._saved_field_layer()

        if not prescription:
            QMessageBox.warning(
                self,
                "Exportação",
                "Gere uma prescrição antes de exportar o pacote agrícola.",
            )
            return

        if not field_layer:
            QMessageBox.warning(
                self,
                "Exportação",
                "Camada de talhões não encontrada.",
            )
            return

        export_dir = self._choose_export_folder()

        if not export_dir:
            return

        output_path = Path(export_dir) / "pacote_agricola.txt"

        try:
            with output_path.open("w", encoding="utf-8") as f:
                f.write("PACOTE AGRÍCOLA - SmartGrain\n")
                f.write("=" * 60 + "\n\n")

                project_info = self.current_project or {}
                f.write(f"Projeto: {project_info.get('nome', 'N/A')}\n")
                f.write(f"Propriedade: {project_info.get('propriedade', 'N/A')}\n")
                f.write(f"Safra: {project_info.get('safra', 'N/A')}\n")
                f.write(f"Responsável: {project_info.get('responsavel', 'N/A')}\n\n")

                rules = prescription.get("regras", {})
                f.write("REGRAS DE PRESCRIÇÃO\n")
                f.write("-" * 60 + "\n")
                f.write(f"Baixo: até {rules.get('baixo_ate')} | Dose: {rules.get('dose_baixa')}\n")
                f.write(f"Médio: até {rules.get('medio_ate')} | Dose: {rules.get('dose_media')}\n")
                f.write(f"Alto: acima disso | Dose: {rules.get('dose_alta')}\n\n")

                f.write("PRESCRIÇÃO POR TALHÃO\n")
                f.write("-" * 60 + "\n")
                f.write("TALHÃO ID | NOME | CLASSE | DOSE | MÉDIA | AMOSTRAS\n")
                f.write("-" * 60 + "\n")

                prescription_by_id = {
                    r["talhao_id"]: r for r in prescription.get("resultados", [])
                }

                for feature in field_layer.getFeatures():
                    field_id = int(feature.id())
                    result = prescription_by_id.get(field_id, {})

                    if result:
                        talhao_id = result.get("talhao_id", field_id)
                        talhao_nome = result.get("talhao_nome", "")
                        classe = result.get("classe", "N/A")
                        dose = result.get("dose", 0)
                        media = result.get("media", "N/A")
                        amostras = result.get("quantidade_amostras", 0)

                        f.write(
                            f"{talhao_id:>8} | {talhao_nome:<10} | "
                            f"{classe:<7} | {dose:>8} | {str(media):<8} | {amostras:>8}\n"
                        )

                f.write("\n" + "=" * 60 + "\n")
                f.write("Arquivo gerado pelo SmartGrain Plugin para QGIS\n")

        except OSError as error:
            QMessageBox.critical(
                self,
                "Exportação",
                f"Não foi possível exportar o pacote agrícola:\n{error}",
            )
            return

        self.export_summary.setText(
            f"Pacote agrícola exportado para: {output_path.name}"
        )
        QMessageBox.information(
            self,
            "Exportação",
            "Pacote agrícola exportado com sucesso.",
        )


