import ctypes

from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QMainWindow

from gcode_viewer.gui.central_widget import Central_Widget
from gcode_viewer.gui.customization.load_font import load_font
from gcode_viewer.gui.startup_window.startup_window import Startup_Window
from gcode_viewer.util.file_handler import File_Handler


class Main_Screen(QMainWindow):

    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.file_handler = File_Handler()

        program_name = "CNC GCode Viewer "
        program_version = "1.0"

        self.setWindowTitle(program_name + program_version)

        self.setWindowIcon(QIcon(str(self.file_handler.icon_png_path)))

        load_font(self.file_handler.used_font_path)
        self.setFont(QFont("Eurostile LT Std", 18))
        heading_font = QFont("Eurostile LT Std", 18, weight=QFont.Bold)

        myappid = program_name + program_version
        if hasattr(ctypes, 'windll'):
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        self.setGeometry(180, 180, 1480, 720)

        self.central_widget = Central_Widget()
        self.setCentralWidget(self.central_widget)

    def start(self):
        start_up_window = Startup_Window()
        file_path = start_up_window.get_initial_file_path()
        if len(file_path) > 0:
            self.central_widget.load_gcode_file(file_path)
        else:
            self.close()
