# settings.py
import os
import tomli,tomli_w
class Color(str):
    pass

class HotKeyType(str):
    pass

class Section:
    """Represents a section of settings, allowing attribute access to values."""
    def __init__(self, data:dict):
        self._data = data

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"No such setting: {name}")
    
    def __setattr__(self, name, value):
        # always let us set _data (and any other private attrs) normally
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            # store into the backing dict
            self._data[name] = value

class SectionRegistrar:
    """Helper class to register settings within a section."""
    def __init__(self, settings, section):
        self.settings = settings
        self.section = section

    def add(self, name, description, default, type_, options=None, nullable=False):
        """Register a setting in this section."""
        if default is None: nullable = True

        if self.section not in self.settings._registry:
            self.settings._registry[self.section] = {}
            self.settings._values[self.section] = {}
        self.settings._registry[self.section][name] = {
            'description': description,
            'default': default,
            'type': type_,
            'options': options,
            'nullable': nullable
        }
        self.settings._values[self.section][name] = default

class Settings:
    Color = Color
    HotKeyType = HotKeyType
    
    """Manages all settings, including registration and TOML loading."""
    def __init__(self):
        self._registry = {}  # Stores setting metadata
        self._values = {}    # Stores current values
        self.config_path = None  # To store the TOML file path

    def section(self, name):
        """Return a registrar for adding settings to a section."""
        return SectionRegistrar(self, name)

    def load_from_toml(self, file_path):
        """Load settings from a TOML file, overriding defaults where applicable."""
        self.config_path = file_path
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                toml_data = tomli.load(f)
            for section, settings in toml_data.items():
                if section in self._registry:
                    for name, value in settings.items():
                        if name in self._registry[section]:
                            expected_type = self._registry[section][name]['type']
                            nullable = self._registry[section][name]['nullable']
                            if value is None and not nullable:
                                print(f"Warning: Setting {section}.{name} cannot be None")
                                continue
                            if value is None or isinstance(value, expected_type) or issubclass(expected_type,type(value)): # allow reverse
                                self._values[section][name] = value
                            else:
                                # breakpoint()
                                print(f"Warning: Setting {section}.{name} has incorrect type. Expected {expected_type}, got {type(value)}")
                        else:
                            print(f"Warning: Unknown setting {section}.{name}")
                else:
                    print(f"Warning: Unknown section {section}")
        else:
            print(f"Config file {file_path} not found. Using default settings.")

    def save_to_toml(self):
        """Save current settings back to the TOML file at self.config_path,
        omitting any values that match their defaults (or are None).
        this mean, that by design None can only be default.
        """
        path = self.config_path

        data = {}
        for section, settings in self._values.items():
            if section not in self._registry:
                continue

            section_data = {}
            reg_section = self._registry[section]
            for name, value in settings.items():
                # only save registered keys
                if name not in reg_section:
                    continue

                default = reg_section[name]['default']
                # skip None or unchanged-from-default
                if value is None or value == default:
                    continue
                # breakpoint()

                section_data[name] = value

            if section_data:
                data[section] = section_data

        # serialize and write
        toml_bytes = tomli_w.dumps(data).encode("utf-8")
        with open(path, "wb") as f:
            f.write(toml_bytes)

        print(f"Settings saved to {path}")

    def __getattr__(self, section):
        """Enable dot-notation access to sections."""
        if section in self._values:
            return Section(self._values[section])
        raise AttributeError(f"No such section: {section}")
