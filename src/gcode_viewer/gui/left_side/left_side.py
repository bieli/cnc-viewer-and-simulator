from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QLabel,  QWidget,  QPushButton

from gcode_viewer.gui.gcode_3d_viewer.gcode_3d_viewer import GCode_3D_Viewer


class Left_Side(QWidget):

    def __init__(self):
        super().__init__()

        self.gcode_loaded = False
        self.initUI()

    def initUI(self):

        self.grid = QGridLayout()

        self.gcode_3d_viewer = GCode_3D_Viewer()
        self.grid.addWidget(self.gcode_3d_viewer, 1, 0)

        self.setLayout(self.grid)
