import argparse
import sys
import traceback

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

from . import workaround as _
from .singleInstance import send_socket_command


# This helper function is used to lazy-load register_os only when the 'register' action is called.
# This avoids importing it unnecessarily for other command-line actions.
def _import_register_os():
    """Dynamically imports and returns the register_os function."""
    from .register_os import register_os

    return register_os


def cli(argv: list):
    # TODO: Implement logging to a file for better error tracking in production.
    # This will help capture errors that might occur when the GUI isn't available.

    parser = argparse.ArgumentParser(
        description="F7 Application - A powerful tool for your daily needs."
    )
    parser.add_argument(
        "-notray",
        action="store_true",
        help="Do not use the system tray icon; show the main window on startup.",
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=["show", "settings", "register", "unregister"],
        help="Specify an action to perform on startup. 'show' displays the main window. 'settings' opens the settings dialog. 'register' integrates the application with the operating system. 'unregister' reverse 'register'.",
    )

    args = parser.parse_args(argv[1:])
    # --- Handle 'register' action early as it does not require a QApplication ---
    if args.action in ["register", "unregister"]:
        register_os = _import_register_os()
        unregister = args.action == "unregister"
        register_os(unregister)
        sys.exit(0)

    # --- Single Instance Check ---
    # Attempt to send a "show" command to an existing instance.
    # If successful, another instance is running and has been activated.
    if send_socket_command("show"):
        print(
            "Main: 'show' command sent to an existing instance. This instance will now exit.",
            file=sys.stderr,
        )
        sys.exit(0)

    # --- QApplication Setup ---
    app = QApplication(argv)

    # Use 'Fira Code' if available, otherwise it defaults to the system font.
    default_font = QFont("Fira Code", 10)
    app.setFont(default_font)

    try:
        # --- Main Window Creation ---
        from .window import F7Window

        window = F7Window()

        # --- Command-Line Argument Handling ---
        show_ui_on_startup = not window.core.settings.system.startInTray
        tray_icon_needed = window.core.settings.system.startInTray

        if args.notray:
            print(
                "Main: '-notray' argument specified. Tray icon will not be used, window will show."
            )
            # If '-notray' is used, the tray icon should not be active.
            # FIXME: Currently, if settings are opened with -notray, it might incorrectly perceive this as a non-default setting.
            window.core.settings.system.startInTray = False
            tray_icon_needed = False
            show_ui_on_startup = True

        if args.action == "show":
            print("Main: 'show' argument specified. Window will be shown.")
            show_ui_on_startup = True

        if args.action == "settings":
            print(
                "Main: 'settings' argument specified. Window will be shown and settings dialog opened."
            )
            # Ensure the main window is visible before attempting to open the modal settings dialog.
            show_ui_on_startup = True

        # --- Initialize Tray Icon or Show Window ---
        if tray_icon_needed:
            window.setup_tray_icon()

        if show_ui_on_startup:
            window.show_window_from_tray_or_socket()

        # If "settings" arg was passed, open the dialog now that the main window is potentially visible
        if args.action == "settings":
            window.open_settings_dialog()

        # --- Start Event Loop ---
        sys.exit(app.exec())

    except Exception as e:
        error_message = f"Main: Critical error during application startup: {e}"
        print(error_message, file=sys.stderr)
        traceback.print_exc()

        # Attempt to show a graphical error message if QApplication has been successfully initialized.
        if QApplication.instance():
            QMessageBox.critical(
                None,
                "F7 - Critical Error",
                f"A critical error occurred during startup:\n\n{e}\n\n"
                "Please check the console output for more details.",
            )
        sys.exit(1)


def main():
    """
    Entry point for the application when run as a module (python -m F7).
    """
    cli(sys.argv)


if __name__ == "__main__":
    main()
