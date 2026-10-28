import sys
from gcode_viewer.application import Application

if __name__ == "__main__":
    file_argument = sys.argv[1] if len(sys.argv) > 1 else None
    
    application = Application(file_path=file_argument)

