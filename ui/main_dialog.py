from pathlib import Path

from qgis.core import QgsMapLayerType, QgsProject, QgsWkbTypes
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
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

        actions = QHBoxLayout()
        actions.addWidget(save_button)
        actions.addStretch()

        layout.addWidget(fields_box)
        layout.addWidget(self.field_layer_status)
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
            return

        for layer in polygon_layers:
            self.field_layer_combo.addItem(layer.name(), layer.id())

        selected_layer_id = self._saved_field_layer_id() or current_layer_id
        self._select_field_layer(selected_layer_id)
        self.field_layer_status.setText(
            f"{len(polygon_layers)} camada(s) de polígono disponível(is)."
        )

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
        QMessageBox.information(
            self,
            "Talhões",
            "Camada de talhões salva no projeto.",
        )

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

        field_layer = self.current_project.get("camada_talhoes", {})
        return field_layer.get("id")

    def _restore_selected_field_layer(self):
        if not hasattr(self, "field_layer_combo"):
            return

        self._load_field_layers()
        field_layer = (self.current_project or {}).get("camada_talhoes")

        if field_layer:
            self.field_layer_status.setText(
                f"Camada de talhões salva: {field_layer.get('nome', '')}"
            )

    def _select_field_layer(self, layer_id):
        if not layer_id:
            return

        index = self.field_layer_combo.findData(layer_id)

        if index >= 0:
            self.field_layer_combo.setCurrentIndex(index)

    def _build_data_tab(self):
        return self._build_placeholder_tab(
            "Entrada de dados agronômicos.",
            "Esta aba pode receber mapas de produtividade, pontos de solo, imagens, grades e camadas vetoriais.",
        )

    def _build_analysis_tab(self):
        return self._build_placeholder_tab(
            "Análises e diagnósticos.",
            "Aqui entram estatísticas, interpolação, zonas de manejo e cruzamento de camadas.",
        )

    def _build_prescription_tab(self):
        return self._build_placeholder_tab(
            "Prescrição de aplicação.",
            "Esta etapa pode gerar recomendações por zona, fórmula, cultura ou atributo do mapa.",
        )

    def _build_export_tab(self):
        return self._build_placeholder_tab(
            "Exportação dos resultados.",
            "Aqui podemos preparar arquivos para máquinas, monitores, relatórios e pacotes do projeto.",
        )

    def _build_placeholder_tab(self, title, description):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignLeft)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        description_label = QLabel(description)
        description_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addStretch()
        return tab
