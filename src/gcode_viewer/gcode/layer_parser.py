import math
from gcode_viewer.gcode.layer import Layer

class Layer_Parser():

    def __init__(self):
        pass

    def parse_layer_list(self, string_list, override_feedrate=None):
        self.last_z_value = 0
        self.from_x = 0.0
        self.from_y = 0.0
        self.from_z = 0.0

        self.to_x = 0.0
        self.to_y = 0.0
        self.to_z = 0.0

        self.min_x = 1000000000000000000000000
        self.max_x = 0
        self.min_y = 1000000000000000000000000
        self.max_y = 0

        self.tool_name = "Default Tool"
        self.max_spindle = 0
        self.max_feedrate = 0
        
        # Zmienne do wyliczenia estymacji czasu obróbki
        total_cutting_time_seconds = 0.0
        total_rapid_time_seconds = 0.0
        
        current_feedrate = float(override_feedrate) if override_feedrate is not None else 1000.0
        rapid_feedrate = 600.0    # Skorygowany posuw dla przejazdów jałowych G0 (mm/min)

        s_x, s_y, s_z = 0.0, 0.0, 0.0
        unique_z_levels = set()

        for line in string_list:
            line_strip = line.strip()
            if not line_strip:
                continue
            
            # Wyciąganie nazwy frezu
            if line_strip.startswith('(') and ("TC:" in line_strip or "Endmill" in line_strip or "Tool" in line_strip):
                text_clean = line_strip.replace("(", "").replace(")", "").replace("Begin operation:", "").replace("Finish operation:", "").replace("Path:", "").replace("TC:", "").strip()
                if text_clean:
                    if "Default Tool" in text_clean:
                        text_clean = text_clean.replace("Default Tool", "Tool ")
                    self.tool_name = text_clean

            # Analiza parametrów technologicznych i dystansów
            if not line_strip.startswith('(') and not line_strip.startswith(';'):
                words = line_strip.split()
                if not words:
                    continue
                
                for word in words:
                    if word.startswith("S"):
                        try:
                            s_val = int(float(word[1:]))
                            if s_val > self.max_spindle: self.max_spindle = s_val
                        except ValueError: pass
                    elif word.startswith("F"):
                        try:
                            f_val = float(word[1:])
                            if f_val > 10000.0:
                                f_val = f_val / 60.0
                            f_val_int = int(f_val)
                            if f_val_int > self.max_feedrate: self.max_feedrate = f_val_int
                            if override_feedrate is None:
                                current_feedrate = float(f_val_int)
                        except ValueError: pass

                cmd = words[0]
                if cmd in ["G0", "G1", "G2", "G3"]:
                    next_x, next_y, next_z = s_x, s_y, s_z
                    
                    for word in words:
                        if word.startswith("X"):
                            try: next_x = float(word[1:])
                            except ValueError: pass
                        elif word.startswith("Y"):
                            try: next_y = float(word[1:])
                            except ValueError: pass
                        elif word.startswith("Z"):
                            try: 
                                next_z = float(word[1:])
                                if cmd in ["G1", "G2", "G3"] and next_z <= 0.0:
                                    unique_z_levels.add(next_z)
                            except ValueError: pass

                    distance = math.sqrt((next_x - s_x)**2 + (next_y - s_y)**2 + (next_z - s_z)**2)
                    
                    if distance > 0:
                        if cmd == "G0":
                            total_rapid_time_seconds += (distance / rapid_feedrate) * 60.0
                        else:
                            total_cutting_time_seconds += (distance / current_feedrate) * 60.0

                    s_x, s_y, s_z = next_x, next_y, next_z

        # Wyliczanie statystyk procentowych dla kroków roboczych Z
        step_lines = []
        if len(unique_z_levels) > 1:
            sorted_z = sorted(list(unique_z_levels), reverse=True)
            step_counts = {}
            total_steps = 0
            
            for i in range(len(sorted_z) - 1):
                step = round(abs(sorted_z[i] - sorted_z[i+1]), 3)
                if step > 0.001:
                    step_counts[step] = step_counts.get(step, 0) + 1
                    total_steps += 1
            
            if total_steps > 0:
                for step in sorted(step_counts.keys(), reverse=True):
                    count = step_counts[step]
                    percentage = (count / total_steps) * 100.0
                    step_lines.append(f"Krok {step:.3f}mm: {percentage:.1f}%")
        
        if step_lines:
            self.step_z_info_str = "\n".join(step_lines)
        else:
            self.step_z_info_str = "Krok Z: Jedna warstwa robocza"

        total_time_seconds = total_cutting_time_seconds + total_rapid_time_seconds
        hours = int(total_time_seconds // 3600)
        minutes = int((total_time_seconds % 3600) // 60)
        seconds = int(total_time_seconds % 60)
        self.time_estimation_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        self.tool_info = f"Frez: {self.tool_name}"
        if self.max_spindle > 0:
            self.tool_info += f"\nObroty: {self.max_spindle} RPM"
        if self.max_feedrate > 0:
            feedrate_mms = self.max_feedrate / 60.0
            self.tool_info += f"\nPosuw: {self.max_feedrate} mm/min ({feedrate_mms:.1f} mm/s)"

        split_into_layers_list = self.split_into_layers(string_list)
        parsed_layer_list = []

        for index, layer_lines in enumerate(split_into_layers_list):
            layerobj = self.parse_single_layer(layer_lines)
            layerobj.number = index
            layerobj.tool_info = self.tool_info
            layerobj.time_estimation = self.time_estimation_str
            layerobj.step_z_info = self.step_z_info_str
            parsed_layer_list.append(layerobj)

        return parsed_layer_list

    def split_into_layers(self, list_to_split):
        result_list = []
        current_layer = []
        last_seen_z = None

        for line in list_to_split:
            line_strip = line.strip()
            if not line_strip:
                continue
            
            if line_strip.startswith('(') or line_strip.startswith(';'):
                current_layer.append(line)
                continue

            split_line = line_strip.split()
            if split_line and split_line[0] in ["G0", "G1", "G2", "G3"]:
                for word in split_line:
                    if word.startswith("Z"):
                        try:
                            current_z = float(word[1:])
                            if last_seen_z is not None and current_z != last_seen_z:
                                if current_layer:
                                    result_list.append(current_layer)
                                current_layer = []
                            last_seen_z = current_z
                        except ValueError:
                            pass
            
            current_layer.append(line)

        if current_layer:
            result_list.append(current_layer)

        return result_list

    def parse_single_layer(self, string_to_be_parsed):
        layer = Layer()
        layer.layer_as_string = string_to_be_parsed

        movement_commands = ["G0", "G1", "G2", "G3", "G5"]
        largest_extrusion_value = 0

        for line in string_to_be_parsed:
            line_strip = line.strip()
            if not line_strip:
                continue

            if line_strip.startswith('(') or line_strip.startswith(';'):
                continue
            
            split_line = line_strip.split()
            if not split_line:
                continue

            cmd = split_line[0]
            if cmd in movement_commands:
                if cmd == "G0":
                    current_pg_color = (1.0, 0.3, 0.3, 0.8)
                    current_mp_color = "r"
                else:
                    current_pg_color = (0.0, 1.0, 0.5, 1.0)
                    current_mp_color = "g"

                target_x, target_y, target_z = self.to_x, self.to_y, self.to_z
                i_val, j_val = 0.0, 0.0

                for word in split_line:
                    if word.startswith("X"):
                        try: target_x = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("Y"):
                        try: target_y = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("Z"):
                        try: target_z = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("I"):
                        try: i_val = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("J"):
                        try: j_val = float(word[1:])
                        except ValueError: pass

                self.from_x, self.from_y, self.from_z = self.to_x, self.to_y, self.to_z

                if cmd in ["G2", "G3"]:
                    center_x = self.from_x + i_val
                    center_y = self.from_y + j_val

                    r_start = math.hypot(self.from_x - center_x, self.from_y - center_y)
                    r_end = math.hypot(target_x - center_x, target_y - center_y)
                    radius = (r_start + r_end) / 2.0

                    angle_start = math.atan2(self.from_y - center_y, self.from_x - center_x)
                    angle_end = math.atan2(target_y - center_y, target_x - center_x)

                    if cmd == "G2":
                        if angle_end >= angle_start:
                            angle_end -= 2.0 * math.pi
                    else:
                        if angle_end <= angle_start:
                            angle_end += 2.0 * math.pi

                    angle_diff = angle_end - angle_start

                    arc_length = abs(angle_diff) * radius
                    segments = max(4, min(32, int(arc_length * 2.0)))

                    last_inter_x = self.from_x
                    last_inter_y = self.from_y
                    last_inter_z = self.from_z

                    for step in range(1, segments + 1):
                        t = step / float(segments)
                        curr_angle = angle_start + angle_diff * t
                        
                        inter_x = center_x + radius * math.cos(curr_angle)
                        inter_y = center_y + radius * math.sin(curr_angle)
                        inter_z = self.from_z + (target_z - self.from_z) * t

                        layer.x_data.append((last_inter_x, inter_x))
                        layer.y_data.append((last_inter_y, inter_y))
                        layer.z_data.append((last_inter_z, inter_z))
                        layer.pyqtgraph_color.append(current_pg_color)
                        layer.matplot_color.append(current_mp_color)
                        layer.move_data.append(line)

                        last_inter_x, last_inter_y, last_inter_z = inter_x, inter_y, inter_z
                    
                    self.to_x, self.to_y, self.to_z = target_x, target_y, target_z
                else:
                    self.to_x, self.to_y, self.to_z = target_x, target_y, target_z

                    layer.x_data.append((self.from_x, self.to_x))
                    layer.y_data.append((self.from_y, self.to_y))
                    layer.z_data.append((self.from_z, self.to_z))
                    layer.pyqtgraph_color.append(current_pg_color)
                    layer.matplot_color.append(current_mp_color)
                    layer.move_data.append(line)

                self.update_min_max()
            else:
                layer.x_data.append((self.to_x, self.to_x))
                layer.y_data.append((self.to_y, self.to_y))
                layer.z_data.append((self.to_z, self.to_z))
                layer.pyqtgraph_color.append((0.5, 0.5, 0.5, 0.5))
                layer.matplot_color.append("k")
                layer.move_data.append(line)

        layer.min_x = self.min_x - 2.5
        layer.max_x = self.max_x + 2.5
        layer.min_y = self.min_y - 2.5
        layer.max_y = self.max_y + 2.5

        self.min_x = 1000000000000000000000000
        self.max_x = 0
        self.min_y = 1000000000000000000000000
        self.max_y = 0

        layer.largest_extrusion_value = largest_extrusion_value
        return layer

    def update_min_max(self):
      larger_x = self.to_x if self.to_x > self.from_x else self.from_x
      smaller_x = self.from_x if self.to_x > self.from_x else self.to_x
      if larger_x > self.max_x: self.max_x = larger_x
      if smaller_x < self.min_x: self.min_x = smaller_x
      larger_y = self.to_y if self.to_y > self.from_y else self.from_y
      smaller_y = self.from_y if self.to_y > self.from_y else self.to_y
      if larger_y > self.max_y: self.max_y = larger_y
      if smaller_y < self.min_y: self.min_y = smaller_y

'''
import math
from gcode_viewer.gcode.layer import Layer

class Layer_Parser():

    def __init__(self):
        pass

    """
    def parse_layer_list(self, string_list, override_feedrate=None):
        self.last_z_value = 0
        self.from_x = 0.0
        self.from_y = 0.0
        self.from_z = 0.0

        self.to_x = 0.0
        self.to_y = 0.0
        self.to_z = 0.0

        self.min_x = 1000000000000000000000000
        self.max_x = 0
        self.min_y = 1000000000000000000000000
        self.max_y = 0

        self.tool_name = "Default Tool"
        self.max_spindle = 0
        self.max_feedrate = 0
        
        # Zmienne do wyliczenia estymacji czasu obróbki
        total_cutting_time_seconds = 0.0
        total_rapid_time_seconds = 0.0
        
        # Jeśli użytkownik podał własny posuw, używamy go, w przeciwnym razie domyślnie 1000 lub z pliku
        current_feedrate = float(override_feedrate) if override_feedrate is not None else 1000.0
        rapid_feedrate = 2000.0    # Posuw jałowy G0 (mm/min)

        # Temp zmienne pozycji do śledzenia odległości
        s_x, s_y, s_z = 0.0, 0.0, 0.0

        for line in string_list:
            line_strip = line.strip()
            if not line_strip:
                continue
            
            # Wyciąganie nazwy frezu
            if line_strip.startswith('(') and ("TC:" in line_strip or "Endmill" in line_strip or "Tool" in line_strip):
                text_clean = line_strip.replace("(", "").replace(")", "").replace("Begin operation:", "").replace("Finish operation:", "").replace("Path:", "").replace("TC:", "").strip()
                if text_clean:
                    if "Default Tool" in text_clean:
                        text_clean = text_clean.replace("Default Tool", "Tool ")
                    self.tool_name = text_clean

            # Analiza parametrów technologicznych i dystansów
            if not line_strip.startswith('(') and not line_strip.startswith(';'):
                words = line_strip.split()
                if not words:
                    continue
                
                for word in words:
                    if word.startswith("S"):
                        try:
                            s_val = int(float(word[1:]))
                            if s_val > self.max_spindle: self.max_spindle = s_val
                        except ValueError: pass
                    elif word.startswith("F"):
                        try:
                            f_val = float(word[1:])
                            
                            # --- INTELIGENTNE PARSOWANIE BŁĘDU FREECAD ---
                            # Jeśli posuw w pliku wynosi 120000 lub 180000, 
                            # oznacza to, że FreeCAD zapisał go w mm/godzinę lub pomnożył przez 100.
                            # Przeliczamy to automatycznie do standardowego formatu mm/min:
                            if f_val > 10000.0:
                                f_val = f_val / 60.0  # Konwersja mm/godz -> mm/min (120000 -> 2000 mm/min)
                            
                            f_val_int = int(f_val)
                            if f_val_int > self.max_feedrate: 
                                self.max_feedrate = f_val_int
                            
                            if override_feedrate is None:
                                current_feedrate = float(f_val_int)
                        except ValueError: pass
                    #elif word.startswith("F"):
                    #    try:
                    #        f_val = int(float(word[1:]))
                    #        if f_val > self.max_feedrate: self.max_feedrate = f_val
                    #        # Jeśli NIE mamy nadpisania ręcznego, bierzemy posuw z pliku G-code
                    #        if override_feedrate is None:
                    #            current_feedrate = float(f_val)
                    #    except ValueError: pass


                cmd = words[0]
                if cmd in ["G0", "G1", "G2", "G3"]:
                    next_x, next_y, next_z = s_x, s_y, s_z
                    
                    for word in words:
                        if word.startswith("X"):
                            try: next_x = float(word[1:])
                            except ValueError: pass
                        elif word.startswith("Y"):
                            try: next_y = float(word[1:])
                            except ValueError: pass
                        elif word.startswith("Z"):
                            try: next_z = float(word[1:])
                            except ValueError: pass

                    # Obliczanie odległości wektora 3D Euklidesowej pomiędzy punktami
                    distance = math.sqrt((next_x - s_x)**2 + (next_y - s_y)**2 + (next_z - s_z)**2)
                    
                    if distance > 0:
                        if cmd == "G0":
                            total_rapid_time_seconds += (distance / rapid_feedrate) * 60.0
                        else:
                            total_cutting_time_seconds += (distance / current_feedrate) * 60.0

                    s_x, s_y, s_z = next_x, next_y, next_z

        # Łączny szacowany czas wykonania projektu CNC
        total_time_seconds = total_cutting_time_seconds + total_rapid_time_seconds
        
        # Formatowanie sekund do postaci HH:MM:SS
        hours = int(total_time_seconds // 3600)
        minutes = int((total_time_seconds % 3600) // 60)
        seconds = int(total_time_seconds % 60)
        self.time_estimation_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # Składanie informacji zbiorczej do wyświetlenia
        self.tool_info = f"Frez: {self.tool_name}"
        if self.max_spindle > 0:
            self.tool_info += f"\nObroty: {self.max_spindle} RPM"
        if self.max_feedrate > 0:
            feedrate_mms = self.max_feedrate / 60.0
            self.tool_info += f"\nPosuw: {self.max_feedrate} mm/min ({feedrate_mms:.1f} mm/s)"

        split_into_layers_list = self.split_into_layers(string_list)
        parsed_layer_list = []

        for index, layer_lines in enumerate(split_into_layers_list):
            layerobj = self.parse_single_layer(layer_lines)
            layerobj.number = index
            layerobj.tool_info = self.tool_info
            layerobj.time_estimation = self.time_estimation_str
            parsed_layer_list.append(layerobj)

        return parsed_layer_list
    """

    def parse_layer_list(self, string_list, override_feedrate=None):
        self.last_z_value = 0
        self.from_x = 0.0
        self.from_y = 0.0
        self.from_z = 0.0

        self.to_x = 0.0
        self.to_y = 0.0
        self.to_z = 0.0

        self.min_x = 1000000000000000000000000
        self.max_x = 0
        self.min_y = 1000000000000000000000000
        self.max_y = 0

        self.tool_name = "Default Tool"
        self.max_spindle = 0
        self.max_feedrate = 0
        
        total_cutting_time_seconds = 0.0
        total_rapid_time_seconds = 0.0
        
        current_feedrate = float(override_feedrate) if override_feedrate is not None else 1000.0
        rapid_feedrate = 2000.0    # Posuw jałowy G0 (mm/min)

        s_x, s_y, s_z = 0.0, 0.0, 0.0
        
        # Zbiór do gromadzenia wszystkich unikalnych wysokości roboczych Z
        unique_z_levels = set()

        for line in string_list:
            line_strip = line.strip()
            if not line_strip:
                continue
            
            if line_strip.startswith('(') and ("TC:" in line_strip or "Endmill" in line_strip or "Tool" in line_strip):
                text_clean = line_strip.replace("(", "").replace(")", "").replace("Begin operation:", "").replace("Finish operation:", "").replace("Path:", "").replace("TC:", "").strip()
                if text_clean:
                    if "Default Tool" in text_clean:
                        text_clean = text_clean.replace("Default Tool", "Tool ")
                    self.tool_name = text_clean

            if not line_strip.startswith('(') and not line_strip.startswith(';'):
                words = line_strip.split()
                if not words:
                    continue
                
                for word in words:
                    if word.startswith("S"):
                        try:
                            s_val = int(float(word[1:]))
                            if s_val > self.max_spindle: self.max_spindle = s_val
                        except ValueError: pass
                    elif word.startswith("F"):
                        try:
                            f_val = float(word[1:])
                            if f_val > 10000.0:
                                f_val = f_val / 60.0
                            f_val_int = int(f_val)
                            if f_val_int > self.max_feedrate: self.max_feedrate = f_val_int
                            if override_feedrate is None:
                                current_feedrate = float(f_val_int)
                        except ValueError: pass

                cmd = words[0]
                if cmd in ["G0", "G1", "G2", "G3"]:
                    next_x, next_y, next_z = s_x, s_y, s_z
                    
                    for word in words:
                        if word.startswith("X"):
                            try: next_x = float(word[1:])
                            except ValueError: pass
                        elif word.startswith("Y"):
                            try: next_y = float(word[1:])
                            except ValueError: pass
                        elif word.startswith("Z"):
                            try: 
                                next_z = float(word[1:])
                                # Zapisujemy poziomy Z dla ruchów roboczych (frezowania) poniżej bezpiecznego Z
                                if cmd in ["G1", "G2", "G3"] and next_z <= 0.0:
                                    unique_z_levels.add(next_z)
                            except ValueError: pass

                    distance = math.sqrt((next_x - s_x)**2 + (next_y - s_y)**2 + (next_z - s_z)**2)
                    
                    if distance > 0:
                        if cmd == "G0":
                            total_rapid_time_seconds += (distance / rapid_feedrate) * 60.0
                        else:
                            total_cutting_time_seconds += (distance / current_feedrate) * 60.0

                    s_x, s_y, s_z = next_x, next_y, next_z

        # Obliczanie skoków (kroków) w osi Z
        min_step_z = 0.0
        max_step_z = 0.0
        if len(unique_z_levels) > 1:
            # Sortujemy poziomy od najwyższego (bliskiego 0) do najniższego (najgłębszego)
            sorted_z = sorted(list(unique_z_levels), reverse=True)
            steps = []
            for i in range(len(sorted_z) - 1):
                # Różnica głębokości między kolejnymi warstwami roboczymi
                step = abs(sorted_z[i] - sorted_z[i+1])
                if step > 0.001:  # Ignorujemy błędy zaokrągleń zmiennoprzecinkowych
                    steps.append(step)
            
            if steps:
                min_step_z = min(steps)
                max_step_z = max(steps)

        # Składanie ciągu tekstowego informacji o krokach Z
        if min_step_z > 0 and max_step_z > 0:
            if abs(min_step_z - max_step_z) < 0.01:
                self.step_z_info_str = f"Krok Z (stały): {min_step_z:.3f} mm"
            else:
                self.step_z_info_str = f"Krok Z min: {min_step_z:.3f} mm\nKrok Z max: {max_step_z:.3f} mm"
        else:
            self.step_z_info_str = "Krok Z: Jedna warstwa robocza"

        total_time_seconds = total_cutting_time_seconds + total_rapid_time_seconds
        hours = int(total_time_seconds // 3600)
        minutes = int((total_time_seconds % 3600) // 60)
        seconds = int(total_time_seconds % 60)
        self.time_estimation_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        self.tool_info = f"Frez: {self.tool_name}"
        if self.max_spindle > 0:
            self.tool_info += f"\nObroty: {self.max_spindle} RPM"
        if self.max_feedrate > 0:
            feedrate_mms = self.max_feedrate / 60.0
            self.tool_info += f"\nPosuw: {self.max_feedrate} mm/min ({feedrate_mms:.1f} mm/s)"

        split_into_layers_list = self.split_into_layers(string_list)
        parsed_layer_list = []

        for index, layer_lines in enumerate(split_into_layers_list):
            layerobj = self.parse_single_layer(layer_lines)
            layerobj.number = index
            layerobj.tool_info = self.tool_info
            layerobj.time_estimation = self.time_estimation_str
            # Przekazujemy nową informację tekstową o krokach Z do obiektu listy
            layerobj.step_z_info = self.step_z_info_str
            parsed_layer_list.append(layerobj)

        return parsed_layer_list


    def split_into_layers(self, list_to_split):
        result_list = []
        current_layer = []
        last_seen_z = None

        for line in list_to_split:
            line_strip = line.strip()
            if not line_strip:
                continue
            
            if line_strip.startswith('(') or line_strip.startswith(';'):
                current_layer.append(line)
                continue

            split_line = line_strip.split()
            if split_line and split_line[0] in ["G0", "G1", "G2", "G3"]:
                for word in split_line:
                    if word.startswith("Z"):
                        try:
                            current_z = float(word[1:])
                            if last_seen_z is not None and current_z != last_seen_z:
                                if current_layer:
                                    result_list.append(current_layer)
                                current_layer = []
                            last_seen_z = current_z
                        except ValueError:
                            pass
            
            current_layer.append(line)

        if current_layer:
            result_list.append(current_layer)

        return result_list

    def parse_single_layer(self, string_to_be_parsed):
        layer = Layer()
        layer.layer_as_string = string_to_be_parsed

        movement_commands = ["G0", "G1", "G2", "G3", "G5"]
        largest_extrusion_value = 0

        for line in string_to_be_parsed:
            line_strip = line.strip()
            if not line_strip:
                continue

            if line_strip.startswith('(') or line_strip.startswith(';'):
                continue
            
            split_line = line_strip.split()
            if not split_line:
                continue

            cmd = split_line[0]
            if cmd in movement_commands:
                if cmd == "G0":
                    current_pg_color = (1.0, 0.3, 0.3, 0.8)
                    current_mp_color = "r"
                else:
                    current_pg_color = (0.0, 1.0, 0.5, 1.0)
                    current_mp_color = "g"

                target_x, target_y, target_z = self.to_x, self.to_y, self.to_z
                i_val, j_val = 0.0, 0.0

                for word in split_line:
                    if word.startswith("X"):
                        try: target_x = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("Y"):
                        try: target_y = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("Z"):
                        try: target_z = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("I"):
                        try: i_val = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("J"):
                        try: j_val = float(word[1:])
                        except ValueError: pass

                self.from_x, self.from_y, self.from_z = self.to_x, self.to_y, self.to_z

                if cmd in ["G2", "G3"]:
                    center_x = self.from_x + i_val
                    center_y = self.from_y + j_val

                    r_start = math.hypot(self.from_x - center_x, self.from_y - center_y)
                    r_end = math.hypot(target_x - center_x, target_y - center_y)
                    radius = (r_start + r_end) / 2.0

                    angle_start = math.atan2(self.from_y - center_y, self.from_x - center_x)
                    angle_end = math.atan2(target_y - center_y, target_x - center_x)

                    if cmd == "G2":
                        if angle_end >= angle_start:
                            angle_end -= 2.0 * math.pi
                    else:
                        if angle_end <= angle_start:
                            angle_end += 2.0 * math.pi

                    angle_diff = angle_end - angle_start

                    arc_length = abs(angle_diff) * radius
                    segments = max(4, min(32, int(arc_length * 2.0)))

                    last_inter_x = self.from_x
                    last_inter_y = self.from_y
                    last_inter_z = self.from_z

                    for step in range(1, segments + 1):
                        t = step / float(segments)
                        curr_angle = angle_start + angle_diff * t
                        
                        inter_x = center_x + radius * math.cos(curr_angle)
                        inter_y = center_y + radius * math.sin(curr_angle)
                        inter_z = self.from_z + (target_z - self.from_z) * t

                        layer.x_data.append((last_inter_x, inter_x))
                        layer.y_data.append((last_inter_y, inter_y))
                        layer.z_data.append((last_inter_z, inter_z))
                        layer.pyqtgraph_color.append(current_pg_color)
                        layer.matplot_color.append(current_mp_color)
                        layer.move_data.append(line)

                        last_inter_x, last_inter_y, last_inter_z = inter_x, inter_y, inter_z
                    
                    self.to_x, self.to_y, self.to_z = target_x, target_y, target_z
                else:
                    self.to_x, self.to_y, self.to_z = target_x, target_y, target_z

                    layer.x_data.append((self.from_x, self.to_x))
                    layer.y_data.append((self.from_y, self.to_y))
                    layer.z_data.append((self.from_z, self.to_z))
                    layer.pyqtgraph_color.append(current_pg_color)
                    layer.matplot_color.append(current_mp_color)
                    layer.move_data.append(line)

                self.update_min_max()
            else:
                layer.x_data.append((self.to_x, self.to_x))
                layer.y_data.append((self.to_y, self.to_y))
                layer.z_data.append((self.to_z, self.to_z))
                layer.pyqtgraph_color.append((0.5, 0.5, 0.5, 0.5))
                layer.matplot_color.append("k")
                layer.move_data.append(line)

        layer.min_x = self.min_x - 2.5
        layer.max_x = self.max_x + 2.5
        layer.min_y = self.min_y - 2.5
        layer.max_y = self.max_y + 2.5

        self.min_x = 1000000000000000000000000
        self.max_x = 0
        self.min_y = 1000000000000000000000000
        self.max_y = 0

        layer.largest_extrusion_value = largest_extrusion_value
        return layer

    def update_min_max(self):
        larger_x = self.to_x if self.to_x > self.from_x else self.from_x
        smaller_x = self.from_x if self.to_x > self.from_x else self.to_x
        if larger_x > self.max_x: self.max_x = larger_x
        if smaller_x < self.min_x: self.min_x = smaller_x

        larger_y = self.to_y if self.to_y > self.from_y else self.from_y
        smaller_y = self.from_y if self.to_y > self.from_y else self.to_y
        if larger_y > self.max_y: self.max_y = larger_y
'''



"""
import math
from gcode_viewer.gcode.layer import Layer

class Layer_Parser():

    def __init__(self):
        pass

    def parse_layer_list(self, string_list):
        self.last_z_value = 0
        self.from_x = 0.0
        self.from_y = 0.0
        self.from_z = 0.0

        self.to_x = 0.0
        self.to_y = 0.0
        self.to_z = 0.0

        self.min_x = 1000000000000000000000000
        self.max_x = 0
        self.min_y = 1000000000000000000000000
        self.max_y = 0

        self.tool_name = "Default Tool"
        self.max_spindle = 0
        self.max_feedrate = 0

        # Skanowanie surowego pliku w poszukiwaniu nazwy narzędzia, obrotów (S) i posuwu (F)
        for line in string_list:
            line_strip = line.strip()
            
            # Wyciąganie nazwy frezu z komentarzy FreeCAD
            if line_strip.startswith('(') and ("TC:" in line_strip or "Endmill" in line_strip or "Tool" in line_strip):
                text_clean = line_strip.replace("(", "").replace(")", "").replace("Begin operation:", "").replace("Finish operation:", "").replace("Path:", "").replace("TC:", "").strip()
                if text_clean:
                    # Skracamy "Default Tool003" do ładniejszego "Tool 003"
                    if "Default Tool" in text_clean:
                        text_clean = text_clean.replace("Default Tool", "Tool ")
                    self.tool_name = text_clean

            # Szukanie parametrów S (Spindle RPM) oraz F (Feedrate) w liniach kodu
            if not line_strip.startswith('(') and not line_strip.startswith(';'):
                words = line_strip.split()
                for word in words:
                    if word.startswith("S"):
                        try:
                            s_val = int(float(word[1:]))
                            if s_val > self.max_spindle: self.max_spindle = s_val
                        except ValueError: pass
                    elif word.startswith("F"):
                        try:
                            f_val = int(float(word[1:]))
                            if f_val > self.max_feedrate: self.max_feedrate = f_val
                        except ValueError: pass

        # Składanie czytelnej informacji zbiorczej parametrów CNC
        self.tool_info = f"Frez: {self.tool_name}"
        if self.max_spindle > 0:
            self.tool_info += f"\nObroty: {self.max_spindle} RPM"
        if self.max_feedrate > 0:
            feedrate_mms = self.max_feedrate / 60.0
            self.tool_info += f"\nPosuw: {self.max_feedrate} mm/min ({feedrate_mms:.1f} mm/s)"

        split_into_layers_list = self.split_into_layers(string_list)
        parsed_layer_list = []

        for index, layer_lines in enumerate(split_into_layers_list):
            layerobj = self.parse_single_layer(layer_lines)
            layerobj.number = index
            layerobj.tool_info = self.tool_info
            parsed_layer_list.append(layerobj)

        return parsed_layer_list

    def split_into_layers(self, list_to_split):
        result_list = []
        current_layer = []
        last_seen_z = None

        for line in list_to_split:
            line_strip = line.strip()
            if not line_strip:
                continue
            
            if line_strip.startswith('(') or line_strip.startswith(';'):
                current_layer.append(line)
                continue

            split_line = line_strip.split()
            if split_line and split_line[0] in ["G0", "G1", "G2", "G3"]:
                for word in split_line:
                    if word.startswith("Z"):
                        try:
                            current_z = float(word[1:])
                            if last_seen_z is not None and current_z != last_seen_z:
                                if current_layer:
                                    result_list.append(current_layer)
                                current_layer = []
                            last_seen_z = current_z
                        except ValueError:
                            pass
            
            current_layer.append(line)

        if current_layer:
            result_list.append(current_layer)

        return result_list

    def parse_single_layer(self, string_to_be_parsed):
        layer = Layer()
        layer.layer_as_string = string_to_be_parsed

        movement_commands = ["G0", "G1", "G2", "G3", "G5"]
        largest_extrusion_value = 0

        for line in string_to_be_parsed:
            line_strip = line.strip()
            if not line_strip:
                continue

            if line_strip.startswith('(') or line_strip.startswith(';'):
                continue
            
            split_line = line_strip.split()
            if not split_line:
                continue

            cmd = split_line[0]
            if cmd in movement_commands:
                if cmd == "G0":
                    current_pg_color = (1.0, 0.3, 0.3, 0.8)
                    current_mp_color = "r"
                else:
                    current_pg_color = (0.0, 1.0, 0.5, 1.0)
                    current_mp_color = "g"

                target_x, target_y, target_z = self.to_x, self.to_y, self.to_z
                i_val, j_val = 0.0, 0.0

                for word in split_line:
                    if word.startswith("X"):
                        try: target_x = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("Y"):
                        try: target_y = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("Z"):
                        try: target_z = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("I"):
                        try: i_val = float(word[1:])
                        except ValueError: pass
                    elif word.startswith("J"):
                        try: j_val = float(word[1:])
                        except ValueError: pass

                self.from_x, self.from_y, self.from_z = self.to_x, self.to_y, self.to_z

                if cmd in ["G2", "G3"]:
                    center_x = self.from_x + i_val
                    center_y = self.from_y + j_val

                    r_start = math.hypot(self.from_x - center_x, self.from_y - center_y)
                    r_end = math.hypot(target_x - center_x, target_y - center_y)
                    radius = (r_start + r_end) / 2.0

                    angle_start = math.atan2(self.from_y - center_y, self.from_x - center_x)
                    angle_end = math.atan2(target_y - center_y, target_x - center_x)

                    if cmd == "G2":
                        if angle_end >= angle_start:
                            angle_end -= 2.0 * math.pi
                    else:
                        if angle_end <= angle_start:
                            angle_end += 2.0 * math.pi

                    angle_diff = angle_end - angle_start

                    arc_length = abs(angle_diff) * radius
                    segments = max(4, min(32, int(arc_length * 2.0)))

                    last_inter_x = self.from_x
                    last_inter_y = self.from_y
                    last_inter_z = self.from_z

                    for step in range(1, segments + 1):
                        t = step / float(segments)
                        curr_angle = angle_start + angle_diff * t
                        
                        inter_x = center_x + radius * math.cos(curr_angle)
                        inter_y = center_y + radius * math.sin(curr_angle)
                        inter_z = self.from_z + (target_z - self.from_z) * t

                        layer.x_data.append((last_inter_x, inter_x))
                        layer.y_data.append((last_inter_y, inter_y))
                        layer.z_data.append((last_inter_z, inter_z))
                        layer.pyqtgraph_color.append(current_pg_color)
                        layer.matplot_color.append(current_mp_color)
                        layer.move_data.append(line)

                        last_inter_x, last_inter_y, last_inter_z = inter_x, inter_y, inter_z
                    
                    self.to_x, self.to_y, self.to_z = target_x, target_y, target_z
                else:
                    self.to_x, self.to_y, self.to_z = target_x, target_y, target_z

                    layer.x_data.append((self.from_x, self.to_x))
                    layer.y_data.append((self.from_y, self.to_y))
                    layer.z_data.append((self.from_z, self.to_z))
                    layer.pyqtgraph_color.append(current_pg_color)
                    layer.matplot_color.append(current_mp_color)
                    layer.move_data.append(line)

                self.update_min_max()
            else:
                layer.x_data.append((self.to_x, self.to_x))
                layer.y_data.append((self.to_y, self.to_y))
                layer.z_data.append((self.to_z, self.to_z))
                layer.pyqtgraph_color.append((0.5, 0.5, 0.5, 0.5))
                layer.matplot_color.append("k")
                layer.move_data.append(line)

        layer.min_x = self.min_x - 2.5
        layer.max_x = self.max_x + 2.5
        layer.min_y = self.min_y - 2.5
        layer.max_y = self.max_y + 2.5

        self.min_x = 1000000000000000000000000
        self.max_x = 0
        self.min_y = 1000000000000000000000000
        self.max_y = 0

        layer.largest_extrusion_value = largest_extrusion_value
        return layer

    def update_min_max(self):
        larger_x = self.to_x if self.to_x > self.from_x else self.from_x
        smaller_x = self.from_x if self.to_x > self.from_x else self.to_x
        if larger_x > self.max_x: self.max_x = larger_x
        if smaller_x < self.min_x: self.min_x = smaller_x

        larger_y = self.to_y if self.to_y > self.from_y else self.from_y
        smaller_y = self.from_y if self.to_y > self.from_y else self.to_y
        if larger_y > self.max_y: self.max_y = larger_y
"""

