import sys
from PyQt5.QtWidgets import QApplication
from gcode_viewer.gui.main_screen import Main_Screen

class Application(QApplication):
    def __init__(self, file_path=None):
        super().__init__(sys.argv)
        
        main_screen = Main_Screen()
        
        if file_path:
            main_screen.central_widget.load_gcode_file(file_path)
            #main_screen.show()
            main_screen.showMaximized()
        else:
            main_screen.start()
            
        sys.exit(self.exec_())

