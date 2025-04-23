# plugins/python_eval_plugin.py
import sys
from PyQt6.QtWidgets import QTextEdit, QLabel
from .base_plugin import PluginInterface

class PythonEvalPlugin(PluginInterface):
    NAME = "Python Evaluator"
    PREFIX = None
    SUFFIX = None
    IS_DEFAULT = True # This handles input if no other plugin matches
    PRIORITY = 90     # Lower than AI prefix plugin

    def __init__(self, launcher_instance):
        super().__init__(launcher_instance)

    def get_status_message(self) -> str:
        return "🐍 Python mode"

    def _evaluate(self, command: str, selected_text: str) -> tuple[str | None, str | None]:
        """Internal helper to evaluate, returning result and error."""
        if not command:
            return None, None # No command, no result or error

        try:
            lines = selected_text.splitlines() # Use splitlines to handle different line endings

            # security:ignore. this eval command is the intent use of this plugin.
            result = eval(command) # TODO: better eval.

            result_str = (
                '\n'.join(map(str, result))
                if isinstance(result, (list, tuple, set))
                else str(result)
            )
            return result_str, None
        except Exception as e:
            return None, f"🚨 Error: {str(e)}"

    def update_preview(self, command: str, selected_text: str, preview_widget: QTextEdit, _status_widget: QLabel,_manual:bool) -> None:
        result_str, error_str = self._evaluate(command, selected_text)

        if error_str:
            preview_widget.setPlainText(error_str)
            preview_widget.show()
        elif result_str is not None:
            preview_widget.setPlainText(result_str)
            preview_widget.show()
        else:
            # No command or valid result (e.g., command is empty)
            preview_widget.hide()

        # Important: Adjust height must be called by the main launcher after preview update
        # self.launcher.adjustHeight() # Don't call directly from plugin

    def execute(self, command: str, selected_text: str) -> str | None:
        result_str, error_str = self._evaluate(command, selected_text)

        if error_str:
            # Optionally display error briefly before quitting?
            # For now, just print and return None (launcher won't copy error)
            print(f"Execution Error: {error_str}", file=sys.stderr)
            self.launcher.status_bar.setText(f"💥 Error (not copied)") # Update status bar directly
            return None # Indicate error or no clipboard action needed
        elif result_str is not None:
            return result_str # Return the result string for the launcher to copy
        else:
            return None # No command entered