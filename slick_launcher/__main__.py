# main.py
try:
    import snoop

    snoop.install()
except ModuleNotFoundError:
    pass

import sys
import traceback

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

# Local imports from your project structure
from . import workaround
from .singleInstance import send_socket_command  # For single instance check
from .window import SlickLauncherWindow

# from . import workaround as _ # If you have a workaround module


def cli(argv: list):
    """
    Main entry point for the Slick Launcher application.
    Handles single instance checking, QApplication setup,
    window creation, and command-line argument parsing.

    Args:
        argv (list): Command-line arguments passed to the application.
    """
    # --- Single Instance Check ---
    # Attempt to send a "show" command to an existing instance.
    # If successful, it means another instance is running and has been activated.
    # The command sent should match one understood by process_socket_command in SlickLauncherWindow.
    if send_socket_command(
        "show"
    ):  # "show" is a common command to bring window to front
        print(
            "Main: 'show' command sent to an existing instance. This instance will now exit.",
            file=sys.stderr,
        )
        sys.exit(0)  # Exit successfully as the other instance will handle the request

    # --- QApplication Setup ---
    app = QApplication(argv)
    # Ensure app exits when the last window is closed, unless explicitly managed by tray icon logic
    app.setQuitOnLastWindowClosed(
        True
    )  # Though SlickLauncherWindow manages this via closeEvent for tray

    # Set a default application font. Consider making this configurable.
    # Ensure 'Fira Code' (or your preferred font) is installed on the system.
    default_font = QFont("Fira Code", 10)
    # You could add a check here if Fira Code is available using QFontDatabase
    # from PyQt6.QtGui import QFontDatabase
    # if "Fira Code" not in QFontDatabase.families():
    #     print("Warning: 'Fira Code' font not found. Using system default.", file=sys.stderr)
    app.setFont(default_font)

    try:
        # --- Main Window Creation ---
        launcher_window = SlickLauncherWindow()  # This initializes CoreLogic, UI, etc.

        # --- Command-Line Argument Handling ---
        # Default behavior: show window unless 'startInTray' is true and no overriding args.
        show_ui_on_startup = not launcher_window.core.settings.system.startInTray
        tray_icon_needed = launcher_window.core.settings.system.startInTray

        if "-notray" in argv:
            print(
                "Main: '-notray' argument specified. Tray icon will not be used, window will show."
            )
            launcher_window.core.settings.system.startInTray = False  # Override setting
            tray_icon_needed = False
            show_ui_on_startup = True  # Ensure window shows if -notray is used

        if "show" in argv:
            print("Main: 'show' argument specified. Window will be shown.")
            show_ui_on_startup = True
            # If 'startInTray' was true, this overrides it for this launch.
            # The tray icon might still be created if tray_icon_needed is true,
            # but the window will also show.

        if "settings" in argv:
            print(
                "Main: 'settings' argument specified. Window will be shown and settings dialog opened."
            )
            show_ui_on_startup = (
                True  # Ensure main window is visible before opening modal settings
            )

        # --- Initialize Tray Icon or Show Window ---
        if tray_icon_needed:
            launcher_window.setup_tray_icon()  # Setup tray icon if configured

        if show_ui_on_startup:
            # Use the method designed for showing from tray/socket to ensure consistent state
            launcher_window.show_window_from_tray_or_socket()
        elif tray_icon_needed and launcher_window.tray_icon:
            # If starting in tray and not showing window, can show a tray notification if desired
            # launcher_window.tray_icon.showMessage("Slick Launcher", "Started in tray.", QSystemTrayIcon.MessageIcon.Information, 2000)
            pass  # Already started in tray, window is hidden by default if setup_tray_icon was called and show_ui_on_startup is false.

        # If "settings" arg was passed, open the dialog now that the main window is potentially visible
        if "settings" in argv:
            launcher_window.open_settings_dialog()

        # --- Start Event Loop ---
        sys.exit(app.exec())

    except Exception as e:
        # Critical error during application startup
        error_message = f"Main: Critical error during application startup: {e}"
        print(error_message, file=sys.stderr)
        traceback.print_exc()

        # Attempt to show a graphical error message if QApplication is available
        if QApplication.instance():
            QMessageBox.critical(
                None,
                "Slick Launcher - Critical Error",
                f"A critical error occurred during startup:\n\n{e}\n\n"
                "Please check the console output for more details.",
            )
        sys.exit(1)  # Exit with an error code


def main():
    # To run: python -m your_package_name.main (if part of a package)
    # Or: python main.py (if running directly from the directory containing these files)
    #
    # Example command-line arguments for testing:
    # python main.py show
    # python main.py settings
    # python main.py -notray
    cli(sys.argv)


if __name__ == "__main__":
    main()
