# settings.py
import os
import tomli
from appdirs import user_config_dir

class Section:
    """Represents a section of settings, allowing attribute access to values."""
    def __init__(self, data):
        self._data = data

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"No such setting: {name}")

class SectionRegistrar:
    """Helper class to register settings within a section."""
    def __init__(self, settings, section):
        self.settings = settings
        self.section = section

    def add(self, name, description, default, type_,options=None):
        """Register a setting in this section."""
        if self.section not in self.settings._registry:
            self.settings._registry[self.section] = {}
            self.settings._values[self.section] = {}
        self.settings._registry[self.section][name] = {
            'description': description,
            'default': default,
            'type': type_,
            'options':options
        }
        self.settings._values[self.section][name] = default

class Settings:
    """Manages all settings, including registration and TOML loading."""
    def __init__(self):
        self._registry = {}  # Stores setting metadata (description, default, type)
        self._values = {}    # Stores current values

    def section(self, name):
        """Return a registrar for adding settings to a section."""
        return SectionRegistrar(self, name)

    def load_from_toml(self, file_path):
        """Load settings from a TOML file, overriding defaults where applicable."""
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                toml_data = tomli.load(f)
            for section, settings in toml_data.items():
                if section in self._registry:
                    for name, value in settings.items():
                        if name in self._registry[section]:
                            expected_type = self._registry[section][name]['type']
                            if isinstance(value, expected_type):
                                self._values[section][name] = value
                            else:
                                print(f"Warning: Setting {section}.{name} has incorrect type. Expected {expected_type}, got {type(value)}")
                        else:
                            print(f"Warning: Unknown setting {section}.{name}")
                else:
                    print(f"Warning: Unknown section {section}")
        else:
            print(f"Config file {file_path} not found. Using default settings.")

    def __getattr__(self, section):
        """Enable dot-notation access to sections."""
        if section in self._values:
            return Section(self._values[section])
        raise AttributeError(f"No such section: {section}")