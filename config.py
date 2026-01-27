import configparser
import os

CONFIG_FILE = "config.ini"

class AppConfig:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config_path = os.path.join(os.path.dirname(__file__), CONFIG_FILE)
        self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_path):
            self.config.read(self.config_path)
        else:
            # Set up default values if config file doesn't exist
            self._set_defaults()
            self._save_config() # Create the file with defaults

    def _set_defaults(self):
        if 'General' not in self.config:
            self.config['General'] = {}
        if 'UI' not in self.config:
            self.config['UI'] = {}
        if 'GoogleCloud' not in self.config:
            self.config['GoogleCloud'] = {}

        self.config['General']['chat_region'] = "" # Stored as "x,y,width,height"
        self.config['UI']['font_family'] = "Segoe UI"
        self.config['UI']['font_size'] = "14"
        self.config['UI']['theme'] = "Light"
        self.config['General']['hotkey'] = "<f8>" # Default hotkey
        self.config['GoogleCloud']['project_id'] = ""

    def _save_config(self):
        with open(self.config_path, 'w') as configfile:
            self.config.write(configfile)

    def get(self, section, option, default=None):
        return self.config.get(section, option, fallback=default)

    def set(self, section, option, value):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][option] = str(value)
        self._save_config()

    # --- Specific getters/setters for convenience ---
    def get_chat_region(self):
        region_str = self.get('General', 'chat_region')
        if region_str:
            try:
                return tuple(map(int, region_str.split(',')))
            except ValueError:
                return None
        return None

    def set_chat_region(self, region):
        if region:
            self.set('General', 'chat_region', ','.join(map(str, region)))
        else:
            self.set('General', 'chat_region', "")

    def get_font_family(self):
        return self.get('UI', 'font_family', "Segoe UI")

    def set_font_family(self, family):
        self.set('UI', 'font_family', family)

    def get_font_size(self):
        try:
            return int(self.get('UI', 'font_size', "14"))
        except ValueError:
            return 14

    def set_font_size(self, size):
        self.set('UI', 'font_size', str(size))

    def get_theme(self):
        return self.get('UI', 'theme', "Light")

    def set_theme(self, theme):
        self.set('UI', 'theme', theme)

    def get_project_id(self):
        return self.get('GoogleCloud', 'project_id', "")

    def set_project_id(self, project_id):
        self.set('GoogleCloud', 'project_id', project_id)

    def get_hotkey(self):
        return self.get('General', 'hotkey', "<f8>")

    def set_hotkey(self, hotkey_str):
        self.set('General', 'hotkey', hotkey_str)


