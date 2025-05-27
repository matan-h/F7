import sys
import traceback

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

from . import workaround as _
from .singleInstance import send_socket_command  # For single instance check
from .window import F7Window


def cli(argv: list):
    # --- Single Instance Check ---
    # Attempt to send a "show" command to an existing instance.
    # If successful, it means another instance is running and has been activated.
    # The command sent should match one understood by process_socket_command in F7Window.
    if send_socket_command("show"):
        print(
            "Main: 'show' command sent to an existing instance. This instance will now exit.",
            file=sys.stderr,
        )
        sys.exit(0)

    # --- QApplication Setup ---
    app = QApplication(argv)

    # use 'Fira Code' if available, otherwise it uses the system font)
    default_font = QFont("Fira Code", 10)
    app.setFont(default_font)

    try:
        # --- Main Window Creation ---
        window = F7Window()  # This initializes CoreLogic, UI, etc.

        # --- Command-Line Argument Handling ---
        show_ui_on_startup = not window.core.settings.system.startInTray
        tray_icon_needed = window.core.settings.system.startInTray

        if "-notray" in argv:
            print(
                "Main: '-notray' argument specified. Tray icon will not be used, window will show."
            )
            window.core.settings.system.startInTray = False  # Override setting # FIXME: currently, if settings is opened with -notray it thinks thats a non-default
            tray_icon_needed = False
            show_ui_on_startup = True  # Ensure window shows if -notray is used

        if "show" in argv:
            print("Main: 'show' argument specified. Window will be shown.")
            show_ui_on_startup = True

        if "settings" in argv:
            print(
                "Main: 'settings' argument specified. Window will be shown and settings dialog opened."
            )
            show_ui_on_startup = (
                True  # Ensure main window is visible before opening modal settings
            )

        # --- Initialize Tray Icon or Show Window ---
        if tray_icon_needed:
            window.setup_tray_icon()  # Setup tray icon if configured

        if show_ui_on_startup:
            window.show_window_from_tray_or_socket()

        # If "settings" arg was passed, open the dialog now that the main window is potentially visible
        if "settings" in argv:
            window.open_settings_dialog()

        # --- Start Event Loop ---
        sys.exit(app.exec())

    except Exception as e:
        error_message = f"Main: Critical error during application startup: {e}"
        print(error_message, file=sys.stderr)
        traceback.print_exc()

        # Attempt to show a graphical error message if QApplication is available
        if QApplication.instance():
            QMessageBox.critical(
                None,
                "F7 - Critical Error",
                f"A critical error occurred during startup:\n\n{e}\n\n"
                "Please check the console output for more details.",
            )
        sys.exit(1)  # Exit with an error code


def main():
    ## called on python -m F7
    cli(sys.argv)


if __name__ == "__main__":
    main()
