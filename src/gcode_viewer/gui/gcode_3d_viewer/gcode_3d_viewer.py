import math

import pyqtgraph as pg
import pyqtgraph.opengl as gl

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import numpy as np

class GCode_3D_Viewer(QWidget):

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.viewer = gl.GLViewWidget()
        layout.addWidget(self.viewer, 1)

        self.viewer.setWindowTitle('Viewer')
        self.viewer.setCameraPosition(distance=250)

        g = gl.GLGridItem()
        g.setSize(200, 200)
        g.setSpacing(5, 5)
        self.viewer.addItem(g)

    def show_gcode(self, filename):

        points, faces = self.loadSTL(filename)
        meshdata = gl.MeshData(vertexes=points, faces=faces)
        mesh = gl.GLMeshItem(meshdata=meshdata, smooth=True, drawFaces=False, drawEdges=True, edgeColor=(0, 1, 0, 1))
        self.viewer.addItem(mesh)

        self.currentSTL = mesh


    def load_gcode(self, layer_list):
        import numpy as np
        import pyqtgraph.opengl as gl
        from PyQt5.QtGui import QVector3D
        import math
        
        target_view = self
        if not hasattr(self, 'addItem'):
            for attr_name in dir(self):
                attr = getattr(self, attr_name, None)
                if isinstance(attr, gl.GLViewWidget):
                    target_view = attr
                    break
        try:
            for item in list(target_view.items):
                target_view.removeItem(item)
            target_view.clear()
        except Exception:
            pass
            
        try:
            bed_x = float(self.settings.environment.printer.bed_width_x)
            bed_y = float(self.settings.environment.printer.bed_depth_y)
        except Exception:
            bed_x, bed_y = 200.0, 200.0

        g = gl.GLGridItem()
        g.setSize(bed_x, bed_y, 1.0)
        
        grid_spacing = 50.0 if bed_x > 400.0 else 10.0
        g.setSpacing(grid_spacing, grid_spacing, 1.0)
        
        g.resetTransform()
        g.translate(bed_x / 2.0, bed_y / 2.0, 0.0)
        
        g.setColor((200, 200, 200, 60))
        target_view.addItem(g)

        all_x, all_y = [], []
        for layer in layer_list:
            if layer.x_data:
                for segment in layer.x_data:
                    all_x.extend([segment[0], segment[1]])
                for segment in layer.y_data:
                    all_y.extend([segment[0], segment[1]])

        if not all_x or not all_y:
            return

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        offset_x = -min_x
        offset_y = -min_y

        for layer in layer_list:
            if not layer.x_data:
                continue
                
            points = []
            colors = []
            
            for i in range(len(layer.x_data)):
                x_start = float(layer.x_data[i][0])
                x_end   = float(layer.x_data[i][1])
                y_start = float(layer.y_data[i][0])
                y_end   = float(layer.y_data[i][1])
                z_start = float(layer.z_data[i][0])
                z_end   = float(layer.z_data[i][1])

                points.append([x_start + offset_x, y_start + offset_y, z_start])
                points.append([x_end + offset_x, y_end + offset_y, z_end])
                
                color = layer.pyqtgraph_color[i] if i < len(layer.pyqtgraph_color) else (0.0, 1.0, 0.5, 1.0)
                colors.append(color)
                colors.append(color)
                
            if points:
                pts_array = np.array(points)
                clr_array = np.array(colors)
                line_item = gl.GLLinePlotItem(pos=pts_array, color=clr_array, width=2.0, mode='lines')
                target_view.addItem(line_item)

        final_max_x = max_x + offset_x
        final_max_y = max_y + offset_y
        
        center_obj_x = final_max_x / 2.0
        center_obj_y = final_max_y / 2.0
        
        max_dimension = max(final_max_x, final_max_y)
        optimal_distance = max_dimension * 1.5

        target_view.setCameraPosition(
            pos=QVector3D(center_obj_x, center_obj_y, 0.0),
            distance=optimal_distance,
            elevation=45,
            azimuth=-45
        )
        
        try:
            start_x, start_y, start_z = None, None, None
            
            for layer in layer_list:
                if layer.x_data and len(layer.x_data) > 0:
                    first_x_seg = layer.x_data[0]
                    first_y_seg = layer.y_data[0]
                    first_z_seg = layer.z_data[0]

                    start_x = float(first_x_seg[0] if isinstance(first_x_seg, (tuple, list)) else first_x_seg) + offset_x
                    start_y = float(first_y_seg[0] if isinstance(first_y_seg, (tuple, list)) else first_y_seg) + offset_y
                    start_z = float(first_z_seg[0] if isinstance(first_z_seg, (tuple, list)) else first_z_seg)
                    break

            if start_x is not None:
                r = 1.5
                h_cyl = 12.0
                h_cone = 4.0
                sides = 16
                
                verts = []
                faces = []
                
                verts.append([0.0, 0.0, 0.0])
                
                for i in range(sides):
                    ang = 2.0 * math.pi * i / sides
                    verts.append([r * math.cos(ang), r * math.sin(ang), h_cone])
                    
                for i in range(sides):
                    ang = 2.0 * math.pi * i / sides
                    verts.append([r * math.cos(ang), r * math.sin(ang), h_cone + h_cyl])
                    
                verts.append([0.0, 0.0, h_cone + h_cyl])
                
                for i in range(sides):
                    next_i = (i + 1) % sides
                    faces.append([0, i + 1, next_i + 1])
                    
                for i in range(sides):
                    next_i = (i + 1) % sides
                    p1 = i + 1
                    p2 = next_i + 1
                    p3 = i + 1 + sides
                    p4 = next_i + 1 + sides
                    faces.append([p1, p2, p3])
                    faces.append([p2, p4, p3])
                    
                top_center_idx = len(verts) - 1
                for i in range(sides):
                    next_i = (i + 1) % sides
                    faces.append([top_center_idx, i + 1 + sides, next_i + 1 + sides])
                
                verts_np = np.array(verts)
                faces_np = np.array(faces, dtype=int)
                tool_md = gl.MeshData(vertexes=verts_np, faces=faces_np)
                
                tool_mesh = gl.GLMeshItem(meshdata=tool_md, smooth=True, color=(1.0, 0.65, 0.1, 1.0), shader='flat')
                
                tool_mesh.translate(start_x, start_y, start_z)
                target_view.addItem(tool_mesh)
                
                print(f"Pomyślnie wyrenderowano frez z kolcem na pozycji startu: X={start_x:.2f}, Y={start_y:.2f}, Z={start_z:.2f}")
        except Exception as e:
            print(f"Ostrzeżenie: Nie udało się wygenerować znacznika frezu: {e}")




    """
    def load_gcode(self, layer_list):
        import numpy as np
        import pyqtgraph.opengl as gl
        from PyQt5.QtGui import QVector3D
        
        # 1. Czyszczenie starego widoku
        target_view = self
        if not hasattr(self, 'addItem'):
            for attr_name in dir(self):
                attr = getattr(self, attr_name, None)
                if isinstance(attr, gl.GLViewWidget):
                    target_view = attr
                    break
        try:
            for item in list(target_view.items):
                target_view.removeItem(item)
            target_view.clear()
        except Exception:
            pass
            
        # 2. Dodanie siatki stołu CNC
        g = gl.GLGridItem()
        g.setSize(200, 200)
        g.setSpacing(10, 10)
        target_view.addItem(g)

        # 3. Wyznaczenie globalnego punktu skrajnego dla poprawnego pozycjonowania bazy
        all_x, all_y = [], []
        for layer in layer_list:
            if layer.x_data:
                for segment in layer.x_data:
                    all_x.extend([segment[0], segment[1]])
                for segment in layer.y_data:
                    all_y.extend([segment[0], segment[1]])

        if not all_x or not all_y:
            return

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        # Centrowanie bazy do lewego dolnego rogu stołu roboczego (0,0) dokładnie tak jak w Candle
        offset_x = -min_x
        offset_y = -min_y

        # 4. Iteracja po warstwach i precyzyjne rysowanie linii wektorowych
        for layer in layer_list:
            if not layer.x_data:
                continue
                
            points = []
            colors = []
            
            for i in range(len(layer.x_data)):
                # Bezpieczne pobieranie punktów początkowych i końcowych z krotek
                x_start = float(layer.x_data[i][0])
                x_end   = float(layer.x_data[i][1])
                y_start = float(layer.y_data[i][0])
                y_end   = float(layer.y_data[i][1])
                z_start = float(layer.z_data[i][0])
                z_end   = float(layer.z_data[i][1])

                # Czarna magia: Zachowujemy czysty układ XYZ (brak zamiany osi w punktach)
                points.append([x_start + offset_x, y_start + offset_y, z_start])
                points.append([x_end + offset_x, y_end + offset_y, z_end])
                
                color = layer.pyqtgraph_color[i] if i < len(layer.pyqtgraph_color) else (0.0, 1.0, 0.5, 1.0)
                colors.append(color)
                colors.append(color)
                
            if points:
                pts_array = np.array(points)
                clr_array = np.array(colors)
                line_item = gl.GLLinePlotItem(pos=pts_array, color=clr_array, width=2.0, mode='lines')
                target_view.addItem(line_item)

        # 5. AUTOMATYCZNE I INTELIGENTNE USTAWIANIE ORAZ OBRACANIE KAMERY (STYL CANDLE)
        # Obliczamy środek i wymiary przesuniętego detalu
        final_max_x = max_x + offset_x
        final_max_y = max_y + offset_y
        
        center_obj_x = final_max_x / 2.0
        center_obj_y = final_max_y / 2.0
        
        max_dimension = max(final_max_x, final_max_y)
        optimal_distance = max_dimension * 1.4  # Margines Zoomu ustawiony na stabilne 75% okna

        # Pozycjonujemy kamerę: obrót wokół własnej osi (azimuth=225) oraz kąt pochylenia (elevation=45)
        # dopasowuje rzut izometryczny pyqtgraph 1:1 do perspektywy programu Candle
        target_view.setCameraPosition(
            pos=QVector3D(center_obj_x, center_obj_y, 0.0),
            distance=optimal_distance,
            elevation=45,
            azimuth=-45
        )
        # ====================================================================
        # --- NOWY KOD: TRÓJWYMIAROWY FREZ (WALEC Z KOLCEM) STYL CANDLE ---
        # ====================================================================
        try:
            start_x, start_y, start_z = None, None, None
            
            # Przeszukujemy warstwy, aby znaleźć pierwszy fizyczny punkt
            for layer in layer_list:
                if layer.x_data and len(layer.x_data) > 0:
                    first_x_seg = layer.x_data[0]
                    first_y_seg = layer.y_data[0]
                    first_z_seg = layer.z_data[0]

                    # Bezpiecznie pobieramy pierwszą wartość z krotki segmentu
                    start_x = float(first_x_seg[0] if isinstance(first_x_seg, (tuple, list)) else first_x_seg) + offset_x
                    start_y = float(first_y_seg[0] if isinstance(first_y_seg, (tuple, list)) else first_y_seg) + offset_y
                    start_z = float(first_z_seg[0] if isinstance(first_z_seg, (tuple, list)) else first_z_seg)
                    break

            if start_x is not None:
                # Parametry wymiarowe wirtualnego frezu
                r = 1.5       # Promień frezu (szerokość)
                h_cyl = 12.0  # Wysokość części walcowej
                h_cone = 4.0  # Wysokość kolca (ostrza)
                sides = 16    # Gęstość siatki okręgu
                
                verts = []
                faces = []
                
                # --- GENEROWANIE WIERZCHOŁKÓW (Vertices) ---
                # 0: Czubek ostrza (kolec dotyka start_z)
                verts.append([0.0, 0.0, 0.0])
                
                # 1..sides: Dolna krawędź walca (przejście stożka w walec na wysokości h_cone)
                for i in range(sides):
                    ang = 2.0 * math.pi * i / sides
                    verts.append([r * math.cos(ang), r * math.sin(ang), h_cone])
                    
                # sides+1..2*sides: Górna krawędź walca (na wysokości h_cone + h_cyl)
                for i in range(sides):
                    ang = 2.0 * math.pi * i / sides
                    verts.append([r * math.cos(ang), r * math.sin(ang), h_cone + h_cyl])
                    
                # Ostatni: Środek górnego dekla walca
                verts.append([0.0, 0.0, h_cone + h_cyl])
                
                # --- GENEROWANIE ŚCIAN (Faces - Trójkąty) ---
                # 1. Ściany boczne stożka (kolec)
                for i in range(sides):
                    next_i = (i + 1) % sides
                    faces.append([0, i + 1, next_i + 1])
                    
                # 2. Ściany boczne walca (podział na czworoboki składające się z 2 trójkątów)
                for i in range(sides):
                    next_i = (i + 1) % sides
                    p1 = i + 1
                    p2 = next_i + 1
                    p3 = i + 1 + sides
                    p4 = next_i + 1 + sides
                    faces.append([p1, p2, p3])
                    faces.append([p2, p4, p3])
                    
                # 3. Górny dekiel walca (zamknięcie bryły)
                top_center_idx = len(verts) - 1
                for i in range(sides):
                    next_i = (i + 1) % sides
                    faces.append([top_center_idx, i + 1 + sides, next_i + 1 + sides])
                
                # Tworzenie obiektu MeshData z wyliczonej matematycznie siatki geometrii
                verts_np = np.array(verts)
                faces_np = np.array(faces, dtype=int)
                tool_md = gl.MeshData(vertexes=verts_np, faces=faces_np)
                
                # Budowanie elementu wizualnego 3D (Jaskrawy pomarańczowy, cieniowany)
                tool_mesh = gl.GLMeshItem(meshdata=tool_md, smooth=True, color=(1.0, 0.65, 0.1, 1.0), shader='shaded')
                
                # Przesuwamy cały wygenerowany frez na pozycję startową
                tool_mesh.translate(start_x, start_y, start_z)
                target_view.addItem(tool_mesh)
                
                print(f"Pomyślnie wyrenderowano frez z kolcem na pozycji startu: X={start_x:.2f}, Y={start_y:.2f}, Z={start_z:.2f}")
        except Exception as e:
            print(f"Ostrzeżenie: Nie udało się wygenerować bryły frezu: {e}")
    """

    """
    def load_gcode(self, layer_list):
        import numpy as np
        import pyqtgraph.opengl as gl
        
        ALIGN_TO_BOTTOM_LEFT = True
        CENTER_OBJECT = False

        # 1. Pełne i bezpieczne czyszczenie ekranu 3D ze wszystkich starych elementów
        target_view = self
        if not hasattr(self, 'addItem'):
            for attr_name in dir(self):
                attr = getattr(self, attr_name, None)
                if isinstance(attr, gl.GLViewWidget):
                    target_view = attr
                    break
        
        try:
            # Usuwamy wszystkie obiekty ze sceny 3D, aby projekty się nie nakładały
            for item in list(target_view.items):
                target_view.removeItem(item)
            target_view.clear()
        except Exception:
            pass
            
        # 2. Dodanie świeżej siatki stołu CNC
        g = gl.GLGridItem()
        g.setSize(200, 200)
        g.setSpacing(10, 10)

        try:
            target_view.addItem(g)
        except AttributeError:
            print("Krytyczny błąd: Nie udało się odnaleźć kontenera GLViewWidget w strukturze klasy.")
            return

        # 3. Wyznaczenie globalnych skrajnych punktów (Bounding Box) dla całego detalu
        all_x, all_y = [], []
        for layer in layer_list:
            if layer.x_data:
                for segment in layer.x_data:
                    all_x.extend([segment[0], segment[1]])
                for segment in layer.y_data:
                    all_y.extend([segment[0], segment[1]])

        if not all_x or not all_y:
            print("Brak danych geometrycznych do wyśrodkowania.")
            return

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        # 4. Obliczenie przesunięć (Offsets) na podstawie wybranego trybu
        offset_x, offset_y = 0.0, 0.0

        if ALIGN_TO_BOTTOM_LEFT:
            offset_x = -min_x
            offset_y = -min_y
        elif CENTER_OBJECT:
            offset_x = -(min_x + max_x) / 2.0
            offset_y = -(min_y + max_y) / 2.0

        # 5. Iteracja po warstwach i rysowanie linii wektorowych
        '''
        for layer in layer_list:
            if not layer.x_data:
                continue
                
            points = []
            colors = []
            
            for i in range(len(layer.x_data)):
                # Poprawne wyciąganie danych segmentu ze struktur warstwy
                x_start, x_end = layer.x_data[i][0], layer.x_data[i][1]
                y_start, y_end = layer.y_data[i][0], layer.y_data[i][1]
                z_start, z_end = layer.z_data[i][0], layer.z_data[i][1]

                # Zastosowanie obliczonego przesunięcia
                points.append([x_start + offset_x, y_start + offset_y, z_start])
                points.append([x_end + offset_x, y_end + offset_y, z_end])
                
                # Pobranie koloru z parsera lub domyślny zielony
                color = layer.pyqtgraph_color[i] if i < len(layer.pyqtgraph_color) else (0.0, 1.0, 0.5, 1.0)
                colors.append(color)
                colors.append(color)
                
            if points:
                pts_array = np.array(points)
                clr_array = np.array(colors)
                
                line_item = gl.GLLinePlotItem(pos=pts_array, color=clr_array, width=2.0, mode='lines')
                target_view.addItem(line_item)
        '''
                # [ ... tutaj znajduje się sekcja 5: Iteracja po warstwach i rysowanie linii ... ]
                # 5. Iteracja po warstwach i rysowanie linii wektorowych
        # 5. Iteracja po warstwach i rysowanie linii wektorowych
        for layer in layer_list:
            if not layer.x_data:
                continue
                
            points = []
            colors = []
            
            for i in range(len(layer.x_data)):
                # Poprawne rozpakowanie wartości liczbowych float z krotek
                try:
                    x_start = float(layer.x_data[i][0])
                    x_end   = float(layer.x_data[i][1])
                    
                    y_start = float(layer.y_data[i][0])
                    y_end   = float(layer.y_data[i][1])
                    
                    z_start = float(layer.z_data[i][0])
                    z_end   = float(layer.z_data[i][1])
                except (IndexError, TypeError, ValueError):
                    # Zabezpieczenie na wypadek, gdyby dane były płaską strukturą liczbową
                    try:
                        x_start = x_end = float(layer.x_data[i])
                        y_start = y_end = float(layer.y_data[i])
                        z_start = z_end = float(layer.z_data[i])
                    except (TypeError, ValueError):
                        continue

                # ZMIANA: Dodajemy MINUS przed (y_start + offset_y) oraz (y_end + offset_y)
                # To fizycznie odwróci lustrzane odbicie kamery OpenGL i zsynchronizuje widok z układem CNC
                #points.append([x_start + offset_x, -(y_start + offset_y), z_start])
                #points.append([x_end + offset_x, -(y_end + offset_y), z_end])

                # Precyzyjne nanoszenie przesunięcia (detal trafi na początek stołu CNC)
                points.append([x_start + offset_x, y_start + offset_y, z_start])
                points.append([x_end + offset_x, y_end + offset_y, z_end])
                
                color = layer.pyqtgraph_color[i] if i < len(layer.pyqtgraph_color) else (0.0, 1.0, 0.5, 1.0)
                colors.append(color)
                colors.append(color)
                
            if points:
                pts_array = np.array(points)
                clr_array = np.array(colors)
                line_item = gl.GLLinePlotItem(pos=pts_array, color=clr_array, width=2.0, mode='lines')
                target_view.addItem(line_item)


        # ====================================================================
        # --- NOWY KOD: AUTOMATYCZNE DOPASOWANIE KAMERY (ZOOM 90% DETALU) ---
        # ====================================================================
        try:
            # Obliczamy skrajne punkty JUŻ PRZESUNIĘTEGO detalu na scenie 3D
            offset_all_x = [x + offset_x for x in all_x]
            offset_all_y = [y + offset_y for y in all_y]
            
            final_min_x, final_max_x = min(offset_all_x), max(offset_all_x)
            final_min_y, final_max_y = min(offset_all_y), max(offset_all_y)
            
            # 1. Środek geometryczny obiektu (tutaj kierujemy wzrok kamery)
            center_obj_x = (final_min_x + final_max_x) / 2.0
            center_obj_y = (final_min_y + final_max_y) / 2.0
            center_obj_z = 0.0  # Poziom stołu

            # 2. Obliczenie rozmiaru (gabarytu bocznego) detalu
            size_x = final_max_x - final_min_x
            size_y = final_max_y - final_min_y
            max_dimension = max(size_x, size_y)

            # 3. Wyznaczenie optymalnej odległości kamery (Zoom) dla zajętości ~90% okna
            # Kąt widzenia kamery (FOV) w pyqtgraph to ok. 60 stopni, stąd współczynnik matematyczny ok. 1.15
            #optimal_distance = max_dimension * 1.15
            optimal_distance = max_dimension * 1.4
            
            # Zabezpieczenie przed zbyt bliskim zoomem dla mikro-obiektów
            if optimal_distance < 20.0: 
                optimal_distance = 40.0

            # 4. Zastosowanie pozycji kamery i domyślnego rzutu izometrycznego (kąty 45st)
            target_view.setCameraPosition(
                pos=QVector3D(center_obj_x, center_obj_y, center_obj_z),
                distance=optimal_distance,
                elevation=30,  # Kąt pochylenia nad stołem
                azimuth=45     # Obrót wokół stołu
            )
        except Exception as e:
            print(f"Ostrzeżenie: Nie udało się automatycznie wykadrować kamery 3D: {e}")
        # ====================================================================
    """

