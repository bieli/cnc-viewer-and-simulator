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

        self.tool_title_label = QLabel("Active tool and CNC properties:")
        self.tool_title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #444;")
        self.grid.addWidget(self.tool_title_label, self.row_position, 0)
        self.row_position += 1

        self.tool_info_label = QLabel("No tool loaded!")
        self.tool_info_label.setStyleSheet("font-size: 15px; color: #0066cc; font-weight: bold; padding: 6px; background-color: #e6f2ff; border-radius: 4px;")
        self.grid.addWidget(self.tool_info_label, self.row_position, 0)
        self.row_position += 1

        self.input_title_label = QLabel("Check new working feed rate [mm/min]:")
        self.input_title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #444; margin-top: 5px;")
        self.grid.addWidget(self.input_title_label, self.row_position, 0)
        self.row_position += 1

        input_layout = QHBoxLayout()
        self.feedrate_input = QLineEdit()
        self.feedrate_input.setText("2000")
        self.feedrate_input.setFixedWidth(200)
        self.feedrate_input.setStyleSheet("font-size: 15px; padding: 4px; border: 1px solid #ccc; border-radius: 4px;")
        input_layout.addWidget(self.feedrate_input)

        self.recalc_button = QPushButton("Recalculate")
        self.recalc_button.setStyleSheet("font-weight: bold; padding: 5px 10px; background-color: #0066cc; color: white; border: none; border-radius: 4px;")
        self.recalc_button.clicked.connect(self.recalculate_time)
        input_layout.addWidget(self.recalc_button)
        
        self.grid.addLayout(input_layout, self.row_position, 0)
        self.row_position += 1

        self.time_title_label = QLabel("Estimated machining/cutting time:")
        self.time_title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #444; margin-top: 5px;")
        self.grid.addWidget(self.time_title_label, self.row_position, 0)
        self.row_position += 1

        self.time_info_label = QLabel("--:--:--")
        self.time_info_label.setStyleSheet("font-size: 22px; color: #2e7d32; font-weight: bold; padding: 6px; background-color: #e8f5e9; border-radius: 4px;")
        self.grid.addWidget(self.time_info_label, self.row_position, 0)
        self.row_position += 1

        self.step_z_title_label = QLabel("Depth steps in material:")
        self.step_z_title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #444; margin-top: 5px;")
        self.grid.addWidget(self.step_z_title_label, self.row_position, 0)
        self.row_position += 1

        self.step_z_info_label = QLabel("Step Z: --")
        self.step_z_info_label.setStyleSheet("font-size: 15px; color: #b78103; font-weight: bold; padding: 6px; background-color: #fffde7; border-radius: 4px;")
        self.grid.addWidget(self.step_z_info_label, self.row_position, 0)
        self.row_position += 1

        self.grid.setRowMinimumHeight(self.row_position, 10)
        self.row_position += 1

        title_label = QLabel("Depth cross-section (2D view)")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        self.grid.addWidget(title_label, self.row_position, 0)
        self.row_position += 1

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
            if hasattr(first_layer, 'step_z_info'):
                self.step_z_info_label.setText(first_layer.step_z_info)
        else:
            self.tool_info_label.setText("Cutter parameters not detected")
            self.time_info_label.setText("--:--:--")
            self.step_z_info_label.setText("Step Z: --")

        self.refresh_gcode_viewer()

    def set_raw_lines(self, line_list):
        self.raw_lines = line_list

    def recalculate_time(self):
        if not self.raw_lines:
            return
            
        try:
            user_feedrate = float(self.feedrate_input.text().strip())
        except ValueError:
            self.time_info_label.setText("Incorrect feed!")
            return

        temp_parser = Layer_Parser()
        new_layers = temp_parser.parse_layer_list(self.raw_lines, override_feedrate=user_feedrate)
        
        if new_layers and len(new_layers) > 0:
            self.time_info_label.setText(new_layers[0].time_estimation)
            
            feedrate_mms = user_feedrate / 60.0
            current_text = self.tool_info_label.text().split('\n')
            tool_line = current_text[0] if len(current_text) > 0 else f"Tool: {temp_parser.tool_name}"
            feedrate_line = current_text[1] if len(current_text) > 1 else ""
            
            updated_info = f"{tool_line}"
            if feedrate_line:
                updated_info += f"\n{feedrate_line}"
            updated_info += f"\nFeedrate (manual): {user_feedrate:.0f} mm/min ({feedrate_mms:.1f} mm/s)"
            
            self.tool_info_label.setText(updated_info)
            self.step_z_info_label.setText(new_layers[0].step_z_info)

    def refresh_gcode_viewer(self):
        self.gcode_layer_viewer_static.load_layer(0)

