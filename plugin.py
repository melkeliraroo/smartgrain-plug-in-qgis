from pathlib import Path

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .ui.main_dialog import MainDialog


class SmartGrainPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction("SmartGrain", self.iface.mainWindow())
        icon_path = self._logo_path()

        if icon_path.exists():
            self.action.setIcon(QIcon(str(icon_path)))

        self.action.triggered.connect(self.run)

        self.iface.addPluginToMenu("SmartGrain", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginMenu("SmartGrain", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        if self.dialog is None:
            self.dialog = MainDialog(self.iface.mainWindow())

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _logo_path(self):
        return Path(__file__).resolve().parent / "assets" / "logo.png"
