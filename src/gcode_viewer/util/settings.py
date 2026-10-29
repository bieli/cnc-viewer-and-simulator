class Settings():
    def __init__(self, environment):
        self.environment = environment

class Environment():
    def __init__(self, printer):
        self.printer = printer

class Printer():
    def __init__(self, bed_width_x, bed_depth_y, height_z):
        self.bed_width_x = bed_width_x
        self.bed_depth_y = bed_depth_y
        self.height_z = height_z

