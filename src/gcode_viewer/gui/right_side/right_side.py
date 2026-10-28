from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt
from gcode_viewer.gcode.layer_parser import Layer_Parser
from gcode_viewer.gui.gcode_layer_viewer.gcode_layer_viewer_static import GCode_Layer_Viewer_Static

class Right_Side(QWidget):

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.gcode_loaded = False
        self.layer_list = None
        self.raw_lines = None
        self.initUI()

    def initUI(self):
        self.grid = QGridLayout()
        self.row_position = 0

        # Nagłówek sekcji aktywnego frezu
        self.tool_title_label = QLabel("Aktywne narzędzie i parametry CNC:")
        self.tool_title_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #444;")
        self.grid.addWidget(self.tool_title_label, self.row_position, 0)
        self.row_position += 1

        # Etykieta parametrów frezu
        self.tool_info_label = QLabel("Brak załadowanego pliku")
        self.tool_info_label.setStyleSheet("font-size: 13px; color: #0066cc; font-weight: bold; padding: 6px; background-color: #e6f2ff; border-radius: 4px;")
        self.grid.addWidget(self.tool_info_label, self.row_position, 0)
        self.row_position += 1

        # Sekcja inputu posuwu
        self.input_title_label = QLabel("Realny posuw roboczy [mm/min]:")
        self.input_title_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #444; margin-top: 5px;")
        self.grid.addWidget(self.input_title_label, self.row_position, 0)
        self.row_position += 1

        input_layout = QHBoxLayout()
        self.feedrate_input = QLineEdit()
        self.feedrate_input.setText("2000")
        self.feedrate_input.setStyleSheet("font-size: 13px; padding: 4px; border: 1px solid #ccc; border-radius: 4px;")
        input_layout.addWidget(self.feedrate_input)

        self.recalc_button = QPushButton("Przelicz")
        self.recalc_button.setStyleSheet("font-weight: bold; padding: 5px 10px; background-color: #0066cc; color: white; border: none; border-radius: 4px;")
        self.recalc_button.clicked.connect(self.recalculate_time)
        input_layout.addWidget(self.recalc_button)
        
        self.grid.addLayout(input_layout, self.row_position, 0)
        self.row_position += 1

        # Nagłówek sekcji czasu
        self.time_title_label = QLabel("Szacowany czas wycinania:")
        self.time_title_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #444; margin-top: 5px;")
        self.grid.addWidget(self.time_title_label, self.row_position, 0)
        self.row_position += 1

        # Etykieta czasu
        self.time_info_label = QLabel("--:--:--")
        self.time_info_label.setStyleSheet("font-size: 16px; color: #2e7d32; font-weight: bold; padding: 6px; background-color: #e8f5e9; border-radius: 4px;")
        self.grid.addWidget(self.time_info_label, self.row_position, 0)
        self.row_position += 1

        # --- NOWA SEKCJA: GŁĘBOKOŚĆ KROKU Z ---
        self.step_z_title_label = QLabel("Skok zagłębiania w materiale:")
        self.step_z_title_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #444; margin-top: 5px;")
        self.grid.addWidget(self.step_z_title_label, self.row_position, 0)
        self.row_position += 1

        # Etykieta wyświetlająca parametry kroków Z w żółtej ramce ochronnej
        self.step_z_info_label = QLabel("Krok Z: --")
        self.step_z_info_label.setStyleSheet("font-size: 13px; color: #b78103; font-weight: bold; padding: 6px; background-color: #fffde7; border-radius: 4px;")
        self.grid.addWidget(self.step_z_info_label, self.row_position, 0)
        self.row_position += 1
        # --------------------------------------

        # Odstęp pionowy
        self.grid.setRowMinimumHeight(self.row_position, 10)
        self.row_position += 1

        # Nagłówek sekcji przekroju 2D
        title_label = QLabel("Przekrój głębokości (Widok 2D)")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.grid.addWidget(title_label, self.row_position, 0)
        self.row_position += 1

        # Komponent wykresu 2D
        self.gcode_layer_viewer_static = GCode_Layer_Viewer_Static(self.settings)
        self.grid.addWidget(self.gcode_layer_viewer_static, self.row_position, 0)
        
        self.setLayout(self.grid)

    def load_new_gcode(self, layer_list):
        self.layer_list = layer_list
        self.gcode_layer_viewer_static.set_layer_list(layer_list)
        
        if layer_list and len(layer_list) > 0:
            first_layer = layer_list[0]
            if hasattr(first_layer, 'tool_info'):
                self.tool_info_label.setText(first_layer.tool_info)
            if hasattr(first_layer, 'time_estimation'):
                self.time_info_label.setText(first_layer.time_estimation)
            # Wyświetlamy pobraną z parsera wartość odległości między poziomami Z
            if hasattr(first_layer, 'step_z_info'):
                self.step_z_info_label.setText(first_layer.step_z_info)
        else:
            self.tool_info_label.setText("Nie wykryto parametrów frezu")
            self.time_info_label.setText("--:--:--")
            self.step_z_info_label.setText("Krok Z: --")

        self.refresh_gcode_viewer()

    def set_raw_lines(self, line_list):
        self.raw_lines = line_list

    def recalculate_time(self):
        if not self.raw_lines:
            return
            
        try:
            user_feedrate = float(self.feedrate_input.text().strip())
        except ValueError:
            self.time_info_label.setText("Błędny posuw!")
            return

        temp_parser = Layer_Parser()
        new_layers = temp_parser.parse_layer_list(self.raw_lines, override_feedrate=user_feedrate)
        
        if new_layers and len(new_layers) > 0:
            self.time_info_label.setText(new_layers[0].time_estimation)
            
            feedrate_mms = user_feedrate / 60.0
            current_text = self.tool_info_label.text().split('\n')
            frez_line = current_text[0] if len(current_text) > 0 else f"Frez: {temp_parser.tool_name}"
            obroty_line = current_text[1] if len(current_text) > 1 else ""
            
            updated_info = f"{frez_line}"
            if obroty_line:
                updated_info += f"\n{obroty_line}"
            updated_info += f"\nPosuw (Ręczny): {user_feedrate:.0f} mm/min ({feedrate_mms:.1f} mm/s)"
            
            self.tool_info_label.setText(updated_info)
            # Aktualizujemy również wartość kroku Z po przeliczeniu
            self.step_z_info_label.setText(new_layers[0].step_z_info)

    def refresh_gcode_viewer(self):
        self.gcode_layer_viewer_static.load_layer(0)


"""
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt
from gcode_viewer.gcode.layer_parser import Layer_Parser
from gcode_viewer.gui.gcode_layer_viewer.gcode_layer_viewer_static import GCode_Layer_Viewer_Static

class Right_Side(QWidget):

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.gcode_loaded = False
        self.layer_list = None
        self.raw_lines = None  # Przechowuje surowe linie pliku do przeliczania
        self.initUI()

    def initUI(self):
        self.grid = QGridLayout()
        self.row_position = 0

        # Nagłówek sekcji aktywnego frezu
        self.tool_title_label = QLabel("Aktywne narzędzie i parametry CNC:")
        self.tool_title_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #444;")
        self.grid.addWidget(self.tool_title_label, self.row_position, 0)
        self.row_position += 1

        # Etykieta parametrów frezu
        self.tool_info_label = QLabel("Brak załadowanego pliku")
        self.tool_info_label.setStyleSheet("font-size: 13px; color: #0066cc; font-weight: bold; padding: 6px; background-color: #e6f2ff; border-radius: 4px;")
        self.grid.addWidget(self.tool_info_label, self.row_position, 0)
        self.row_position += 1

        # --- NOWA SEKCJA: INPUT POSUWU ROBOCZEGO ---
        self.input_title_label = QLabel("Realny posuw roboczy [mm/min]:")
        self.input_title_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #444; margin-top: 5px;")
        self.grid.addWidget(self.input_title_label, self.row_position, 0)
        self.row_position += 1

        input_layout = QHBoxLayout()
        self.feedrate_input = QLineEdit()
        self.feedrate_input.setText("2000") # Domyślna wartość żądana przez Ciebie
        self.feedrate_input.setStyleSheet("font-size: 13px; padding: 4px; border: 1px solid #ccc; border-radius: 4px;")
        input_layout.addWidget(self.feedrate_input)

        self.recalc_button = QPushButton("Przelicz")
        self.recalc_button.setStyleSheet("font-weight: bold; padding: 5px 10px; background-color: #0066cc; color: white; border: none; border-radius: 4px;")
        self.recalc_button.clicked.connect(self.recalculate_time)
        input_layout.addWidget(self.recalc_button)
        
        self.grid.addLayout(input_layout, self.row_position, 0)
        self.row_position += 1
        # --------------------------------------------

        # Nagłówek sekcji czasu
        self.time_title_label = QLabel("Szacowany czas wycinania:")
        self.time_title_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #444;")
        self.grid.addWidget(self.time_title_label, self.row_position, 0)
        self.row_position += 1

        # Etykieta czasu
        self.time_info_label = QLabel("--:--:--")
        self.time_info_label.setStyleSheet("font-size: 16px; color: #2e7d32; font-weight: bold; padding: 6px; background-color: #e8f5e9; border-radius: 4px;")
        self.grid.addWidget(self.time_info_label, self.row_position, 0)
        self.row_position += 1

        # Odstęp pionowy
        self.grid.setRowMinimumHeight(self.row_position, 10)
        self.row_position += 1

        # Nagłówek sekcji przekroju 2D
        title_label = QLabel("Przekrój głębokości (Widok 2D)")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.grid.addWidget(title_label, self.row_position, 0)
        self.row_position += 1

        # Komponent wykresu 2D
        self.gcode_layer_viewer_static = GCode_Layer_Viewer_Static(self.settings)
        self.grid.addWidget(self.gcode_layer_viewer_static, self.row_position, 0)
        
        self.setLayout(self.grid)

    def load_new_gcode(self, layer_list):
        self.layer_list = layer_list
        self.gcode_layer_viewer_static.set_layer_list(layer_list)
        
        if layer_list and len(layer_list) > 0:
            first_layer = layer_list[0]
            if hasattr(first_layer, 'tool_info'):
                self.tool_info_label.setText(first_layer.tool_info)
            if hasattr(first_layer, 'time_estimation'):
                self.time_info_label.setText(first_layer.time_estimation)
        else:
            self.tool_info_label.setText("Nie wykryto parametrów frezu")
            self.time_info_label.setText("--:--:--")

        self.refresh_gcode_viewer()

    def set_raw_lines(self, line_list):
        # Zapamiętujemy surowe linie, aby móc wywołać ponowne parsowanie czasu
        self.raw_lines = line_list

    def recalculate_time(self):
        if not self.raw_lines:
            return
            
        try:
            # Pobieramy wartość posuwu wpisaną przez użytkownika
            user_feedrate = float(self.feedrate_input.text().strip())
        except ValueError:
            self.time_info_label.setText("Błędny posuw!")
            return

        # Uruchamiamy parser ponownie z nadpisaniem wartości posuwu roboczego
        temp_parser = Layer_Parser()
        new_layers = temp_parser.parse_layer_list(self.raw_lines, override_feedrate=user_feedrate)
        
        if new_layers and len(new_layers) > 0:
            # Aktualizujemy wyłącznie etykietę czasu w UI
            self.time_info_label.setText(new_layers[0].time_estimation)

    def refresh_gcode_viewer(self):
        self.gcode_layer_viewer_static.load_layer(0)


"""

'''
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel
from PyQt5.QtCore import Qt
from gcode_viewer.gui.gcode_layer_viewer.gcode_layer_viewer_static import GCode_Layer_Viewer_Static

class Right_Side(QWidget):

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.gcode_loaded = False
        self.layer_list = None
        self.initUI()

    def initUI(self):
        self.grid = QGridLayout()
        self.row_position = 0

        # Nagłówek sekcji aktywnego frezu
        self.tool_title_label = QLabel("Aktywne narzędzie i parametry CNC:")
        self.tool_title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #444;")
        self.grid.addWidget(self.tool_title_label, self.row_position, 0)
        self.row_position += 1

        # Etykieta parametrów frezu
        self.tool_info_label = QLabel("Brak załadowanego pliku")
        self.tool_info_label.setStyleSheet("font-size: 13px; color: #0066cc; font-weight: bold; padding: 6px; background-color: #e6f2ff; border-radius: 4px;")
        self.grid.addWidget(self.tool_info_label, self.row_position, 0)
        self.row_position += 1

        # Nagłówek sekcji czasu
        self.time_title_label = QLabel("Szacowany czas wycinania:")
        self.time_title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #444; margin-top: 5px;")
        self.grid.addWidget(self.time_title_label, self.row_position, 0)
        self.row_position += 1

        # Etykieta wyświetlająca estymowany czas obróbki w zielonej ramce
        self.time_info_label = QLabel("--:--:--")
        self.time_info_label.setStyleSheet("font-size: 16px; color: #2e7d32; font-weight: bold; padding: 6px; background-color: #e8f5e9; border-radius: 4px;")
        self.grid.addWidget(self.time_info_label, self.row_position, 0)
        self.row_position += 1

        # Odstęp pionowy
        self.grid.setRowMinimumHeight(self.row_position, 10)
        self.row_position += 1

        # Nagłówek sekcji przekroju 2D
        title_label = QLabel("Przekrój głębokości (Widok 2D)")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.grid.addWidget(title_label, self.row_position, 0)
        self.row_position += 1

        # Komponent wykresu 2D
        self.gcode_layer_viewer_static = GCode_Layer_Viewer_Static(self.settings)
        self.grid.addWidget(self.gcode_layer_viewer_static, self.row_position, 0)
        
        self.setLayout(self.grid)

    def load_new_gcode(self, layer_list):
        self.layer_list = layer_list
        self.gcode_layer_viewer_static.set_layer_list(layer_list)
        
        # Pobieranie informacji o narzędziu i czasie z pierwszej warstwy detalu
        if layer_list and len(layer_list) > 0:
            first_layer = layer_list[0]
            if hasattr(first_layer, 'tool_info'):
                self.tool_info_label.setText(first_layer.tool_info)
            if hasattr(first_layer, 'time_estimation'):
                self.time_info_label.setText(first_layer.time_estimation)
        else:
            self.tool_info_label.setText("Nie wykryto parametrów frezu")
            self.time_info_label.setText("--:--:--")

        self.refresh_gcode_viewer()

    def refresh_gcode_viewer(self):
        self.gcode_layer_viewer_static.load_layer(0)
'''


"""
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel
from PyQt5.QtCore import Qt
from gcode_viewer.gui.gcode_layer_viewer.gcode_layer_viewer_static import GCode_Layer_Viewer_Static

class Right_Side(QWidget):

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.gcode_loaded = False
        self.layer_list = None
        self.initUI()

    def initUI(self):
        self.grid = QGridLayout()
        self.row_position = 0

        # Nagłówek sekcji aktywnego frezu
        self.tool_title_label = QLabel("Aktywne narzędzie CNC:")
        self.tool_title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #444;")
        self.grid.addWidget(self.tool_title_label, self.row_position, 0)
        self.row_position += 1

        # Definicja i stylizacja etykiety dla frezu (wcześniej mogło tu braknąć dopisku self.)
        self.tool_info_label = QLabel("Brak załadowanego pliku")
        self.tool_info_label.setStyleSheet("font-size: 14px; color: #0066cc; font-weight: bold; padding: 5px; background-color: #e6f2ff; border-radius: 4px;")
        self.grid.addWidget(self.tool_info_label, self.row_position, 0)
        self.row_position += 1

        # Odstęp pionowy
        self.grid.setRowMinimumHeight(self.row_position, 15)
        self.row_position += 1

        # Nagłówek sekcji przekroju 2D
        title_label = QLabel("Przekrój głębokości (Widok 2D)")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.grid.addWidget(title_label, self.row_position, 0)
        self.row_position += 1

        # Komponent wykresu 2D
        self.gcode_layer_viewer_static = GCode_Layer_Viewer_Static(self.settings)
        self.grid.addWidget(self.gcode_layer_viewer_static, self.row_position, 0)
        
        self.setLayout(self.grid)

    def load_new_gcode(self, layer_list):
        self.layer_list = layer_list
        self.gcode_layer_viewer_static.set_layer_list(layer_list)
        
        # Bezpieczne pobieranie informacji o parametrach frezu z pierwszej warstwy detalu
        if layer_list and len(layer_list) > 0 and hasattr(layer_list[0], 'tool_info'):
            self.tool_info_label.setText(layer_list[0].tool_info)
        else:
            self.tool_info_label.setText("Nie wykryto parametrów frezu")

        self.refresh_gcode_viewer()

    def refresh_gcode_viewer(self):
        self.gcode_layer_viewer_static.load_layer(0)
"""
