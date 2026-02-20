from PySide6.QtCore import QSettings

class SettingsManager:
    def __init__(self):
        self.settings = QSettings("NazToolkit", "NazAndroidToolkit")

    def get_last_dir(self, key="last_image_dir"):
        return self.settings.value(key, "")

    def set_last_dir(self, path, key="last_image_dir"):
        self.settings.setValue(key, path)

    def save_window_state(self, geometry):
        self.settings.setValue("geometry", geometry)

    def load_window_state(self):
        return self.settings.value("geometry")
