# settings_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QFormLayout, QLabel,
    QCheckBox, QLineEdit, QComboBox, QSpinBox,
    QDialogButtonBox, QMessageBox, QVBoxLayout,QDoubleSpinBox,QPushButton,QColorDialog,QApplication
)

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QScreen

from PyQt6.QtCore import pyqtSignal
from .settings import Settings,Color
class SettingsDialog(QDialog):
    settingsApplied = pyqtSignal()  # Signal to notify the main app of changes

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.widget_map = {}  # Maps (section, name) to (enabled_widget, value_widget)

        self.setWindowTitle("Slick Launcher Settings")
        
        # Set size to ~80% of screen size, capped at 800x600
        screen = QScreen.availableGeometry(QApplication.primaryScreen())
        width = min(int(screen.width() * 0.8), 800)
        height = min(int(screen.height() * 0.8), 600)
        self.resize(width, height)

        # Create tab widget for sections
        self.tab_widget = QTabWidget()

        # Generate tabs and widgets
        for section in settings._registry:
            print(section)
            tab = QWidget()
            layout = QFormLayout()
            layout.setVerticalSpacing(10)
            for name, meta in settings._registry[section].items():
                # Main label
                label = QLabel(name.replace('_', ' ').title())
                label.setStyleSheet("font-weight: bold; font-size: 14px;")
                
                # Description label
                desc_label = QLabel(meta['description'])
                desc_label.setStyleSheet("color: #7f8c8d; font-size: 12px; margin-left: 20px;")
                desc_label.setWordWrap(True)

                value = settings._values[section][name]
                enabled_widget = None
                value_widget = None

                # Handle nullable settings with a checkbox
                if meta['nullable']:
                    enabled_widget = QCheckBox("Enable")
                    enabled_widget.setChecked(value is not None)

                # Choose widget based on type
                if meta['type'] == bool:
                    value_widget = QCheckBox()
                    value_widget.setChecked(value if value is not None else False)
                elif meta['type'] == str and meta['options']:
                    value_widget = QComboBox()
                    value_widget.addItems(meta['options'])
                    value_widget.setCurrentText(value if value is not None else meta['options'][0])
                elif meta['type'] == str:
                    value_widget = QLineEdit()
                    value_widget.setText(value if value is not None else "")
                elif meta['type'] == int:
                    value_widget = QSpinBox()
                    value_widget.setMinimum(-10000)
                    value_widget.setMaximum(10000)
                    value_widget.setValue(value if value is not None else meta['default'] or 0)
                    if enabled_widget:
                        value_widget.setEnabled(value is not None)
                elif meta['type'] == float:
                    value_widget = QDoubleSpinBox()
                    value_widget.setMinimum(-10000.0)
                    value_widget.setMaximum(10000.0)
                    value_widget.setValue(value if value is not None else meta['default'] or 0.0)
                    if enabled_widget:
                        value_widget.setEnabled(value is not None)
                elif meta['type'] == Color:
                    value_widget = QPushButton()
                    color = QColor(value if value is not None else "#ffffff")
                    value_widget.setStyleSheet(f"background-color: {color.name()}; border-radius: 4px; padding: 8px;")
                    value_widget.clicked.connect(lambda checked, w=value_widget, s=section, n=name: self.open_color_dialog(w, s, n))
                else:
                    print("WARN: unknown type in settings", section,meta)
                    continue

                # Connect enabled checkbox to value widget
                if enabled_widget:
                    enabled_widget.toggled.connect(value_widget.setEnabled)

                # Add to layout
                widget_layout = QVBoxLayout()
                if enabled_widget:
                    widget_layout.addWidget(enabled_widget)
                widget_layout.addWidget(value_widget)
                widget_layout.addStretch()

                form_widget = QWidget()
                form_widget.setLayout(widget_layout)
                layout.addRow(label, form_widget)
                layout.addRow("", desc_label)  # Description below
                self.widget_map[(section, name)] = (enabled_widget, value_widget)

                tab.setLayout(layout)
                self.tab_widget.addTab(tab, section.capitalize())

        # Add dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )

        # Connect standard signals
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)


        # Set up main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tab_widget)
        main_layout.addWidget(button_box)
        self.setLayout(main_layout)

        # Apply modern, high-contrast styling
        self.setStyleSheet("""
            QDialog {
                background: #2c313a;
                color: #d4d4d4;
                border-radius: 8px;
            }
            QTabWidget::pane {
                border: 1px solid #4b5263;
                background: #22252d;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #22252d;
                color: #d4d4d4;
                padding: 10px 20px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 14px;
            }
            QTabBar::tab:selected {
                background: #2c313a;
                border-bottom: 2px solid #61afef;
                color: #ffffff;
            }
            QLabel {
                color: #d4d4d4;
                font-size: 14px;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background: #22252d;
                color: #d4d4d4;
                border: 1px solid #4b5263;
                border-radius: 4px;
                padding: 6px;
                font-size: 14px;
            }
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background: #4b5263;
                border: none;
                width: 20px;
                height: 20px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover,
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background: #61afef;
            }
            QSpinBox::up-arrow, QSpinBox::down-arrow,
            QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {
                width: 10px;
                height: 10px;
                image: none;
            }
            QSpinBox::up-button::text, QDoubleSpinBox::up-button::text {
                color: #d4d4d4;
                font-size: 14px;
                subcontrol-origin: content;
                subcontrol-position: center;
            }
            QSpinBox::down-button::text, QDoubleSpinBox::down-button::text {
                color: #d4d4d4;
                font-size: 14px;
                subcontrol-origin: content;
                subcontrol-position: center;
            }
            QCheckBox {
                color: #d4d4d4;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                background: #22252d;
                border: 1px solid #4b5263;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background: #61afef;
                border: 1px solid #61afef;
            }
            QPushButton {
                background: #22252d;
                color: #d4d4d4;
                border: 1px solid #4b5263;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #61afef;
                color: #ffffff;
                border: 1px solid #61afef;
            }
            QDialogButtonBox QPushButton {
                background: #22252d;
                color: #d4d4d4;
                border: 1px solid #4b5263;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QDialogButtonBox QPushButton:hover {
                background: #61afef;
                color: #ffffff;
                border: 1px solid #61afef;
            }
            QToolTip {
                background: #32363e;
                color: #d4d4d4;
                border: 1px solid #4b5263;
                border-radius: 4px;
                padding: 4px;
            }
        """)

    def open_color_dialog(self, button, section, name):
        """Open a color dialog and update the button's color."""
        current_color = QColor(self.settings._values[section][name] or "#ffffff")
        color = QColorDialog.getColor(current_color, self)
        if color.isValid():
            self.settings._values[section][name] = color.name()
            button.setStyleSheet(f"background-color: {color.name()}; border-radius: 4px; padding: 8px;")

    def save_settings(self):
        try:
            self.settings.save_to_toml()
            self.settingsApplied.emit()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    def accept(self):
        self.save_settings()
        super().accept()

