from PyQt5.QtWidgets import QWidget, QGridLayout
from matplotlib.collections import LineCollection
from gcode_viewer.gui.gcode_layer_viewer.gcode_canvas import GCode_Canvas

class GCode_Layer_Viewer_Static(QWidget):

    def __init__(self, settings):
        super().__init__()

        self.layer_list = None
        self.layer = None
        self.zoomed_in = False
        self.settings = settings

        self.initUI()

    def set_layer_list(self, layer_list):
        self.layer_list = layer_list

    def load_layer(self, index):
        if not self.layer_list:
            return
        self.start_showing_static()

    def initUI(self):
        self.grid = QGridLayout()
        self.canvas = GCode_Canvas(self, width=5, height=4, dpi=100)
        self.grid.addWidget(self.canvas, 0, 0)
        self.setLayout(self.grid)

    def start_showing_static(self):
        self.canvas.axes.cla()

        # Czyszczenie starych kolekcji linii z pamięci wykresu
        while self.canvas.axes.collections:
            self.canvas.axes.collections.pop()

        # Konfiguracja podpisów osi
        self.canvas.axes.set_xlabel("Object width X [mm]")
        self.canvas.axes.set_ylabel("Milling depth Z [mm]")
        self.canvas.axes.grid(True, linestyle="--", alpha=0.5)

        global_min_z = 0.0
        global_max_z = 0.0
        global_min_x = 0.0
        global_max_x = float(self.settings.environment.printer.bed_width_x)

        segments = []
        colors = []
        all_x_coords = []

        # 1. Agregacja danych - zbieramy wektory zamiast rysować je na bieżąco
        for layer in self.layer_list:
            if not layer.x_data:
                continue

            for i in range(len(layer.x_data)):
                x_seg = layer.x_data[i]
                z_seg = layer.z_data[i]
                color = layer.matplot_color[i] if i < len(layer.matplot_color) else "g"

                # Mapowanie kolorów z formatu tekstowego na standard Matplotlib
                if color == "g":
                    plot_color = (0.0, 1.0, 0.5, 1.0)  # Jasnozielony roboczy (Candle)
                elif color == "b":
                    plot_color = (0.2, 0.2, 1.0, 1.0)  # Ruchy pomocnicze
                elif color == "r":
                    plot_color = (1.0, 0.3, 0.3, 0.8)  # Jasnoczerwony jałowy (G0)
                else:
                    plot_color = (0.5, 0.5, 0.5, 0.5)

                # Segment w przestrzeni 2D X-Z: ((x_start, z_start), (x_end, z_end))
                segments.append(((x_seg[0], z_seg[0]), (x_seg[1], z_seg[1])))
                colors.append(plot_color)

                all_x_coords.extend([x_seg[0], x_seg[1]])
                
                # Monitorowanie skrajnych wartości Z
                if z_seg[0] < global_min_z: global_min_z = z_seg[0]
                if z_seg[1] < global_min_z: global_min_z = z_seg[1]
                if z_seg[0] > global_max_z: global_max_z = z_seg[0]
                if z_seg[1] > global_max_z: global_max_z = z_seg[1]

        '''
        # 2. Rysowanie grupowe (Niezwykle szybkie, optymalizacja pamięci)
        if segments:
            line_segments = LineCollection(segments, colors=colors, linewidths=1.5)
            self.canvas.axes.add_collection(line_segments)

        # 3. Dynamiczne pozycjonowanie kamery / limitów wykresu
        if all_x_coords:
            global_min_x = min(all_x_coords)
            global_max_x = max(all_x_coords)

        padding_x = max(5.0, (global_max_x - global_min_x) * 0.1)
        padding_z = max(2.0, (global_max_z - global_min_z) * 0.2)

        if self.zoomed_in:
            self.canvas.axes.set_xlim(global_min_x - padding_x, global_max_x + padding_x)
        else:
            self.canvas.axes.set_xlim(0, float(self.settings.environment.printer.bed_width_x))

        self.canvas.axes.set_ylim(global_min_z - padding_z, global_max_z + padding_z)

        self.canvas.draw()
        self.show()
        '''


        # 2. Rysowanie grupowe (Niezwykle szybkie, optymalizacja pamięci)
        if segments:
            line_segments = LineCollection(segments, colors=colors, linewidths=1.5)
            self.canvas.axes.add_collection(line_segments)

            # --- NOWY KOD: Dodanie linii i wartości tekstowych dla Min i Max Z ---
            # Linia pozioma dla minimalnej głębokości (najgłębsze frezowanie)
            self.canvas.axes.axhline(y=global_min_z, color='darkgreen', linestyle=':', linewidth=1.2, alpha=0.8)
            # Tekstowa etykieta dla wartości minimalnej po lewej stronie wykresu
            self.canvas.axes.text(0.02, global_min_z, f" Min Z: {global_min_z:.2f} mm", 
                                  transform=self.canvas.axes.get_yaxis_transform(),
                                  color='darkgreen', weight='bold', va='bottom', ha='left', fontsize=14,
                                  bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))

            # Linia pozioma dla maksymalnej wysokości (poziom bezpieczny / góra materiału)
            self.canvas.axes.axhline(y=global_max_z, color='darkred', linestyle=':', linewidth=1.2, alpha=0.8)
            # Tekstowa etykieta dla wartości maksymalnej po lewej stronie wykresu
            self.canvas.axes.text(0.02, global_max_z, f" Max Z: {global_max_z:.2f} mm", 
                                  transform=self.canvas.axes.get_yaxis_transform(),
                                  color='darkred', weight='bold', va='bottom', ha='left', fontsize=14,
                                  bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))

        # 3. Dynamiczne pozycjonowanie kamery / limitów wykresu
        if all_x_coords:
            global_min_x = min(all_x_coords)
            global_max_x = max(all_x_coords)

        padding_x = max(5.0, (global_max_x - global_min_x) * 0.1)
        padding_z = max(2.0, (global_max_z - global_min_z) * 0.2)

        if self.zoomed_in:
            self.canvas.axes.set_xlim(global_min_x - padding_x, global_max_x + padding_x)
        else:
            self.canvas.axes.set_xlim(0, float(self.settings.environment.printer.bed_width_x))

        # Odwrócenie osi Y na wykresie: góra to najwyższy punkt Z, dół to najgłębsze frezowanie
        #self.canvas.axes.set_ylim(global_max_z + padding_z, global_min_z - padding_z)
        self.canvas.axes.set_ylim(global_min_z - padding_z, global_max_z + padding_z)

        self.canvas.draw()
        self.show()

