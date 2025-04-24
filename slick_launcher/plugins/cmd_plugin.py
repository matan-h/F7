# plugins/cmd_plugin.py
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import QTextEdit, QLabel
from .base_plugin import PluginInterface
import snoop

class CmdWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, cmd, input_text):
        super().__init__()
        self.cmd = cmd
        self.input_text = input_text
        self._stopped = False

    def run(self):
        try:
            proc = subprocess.Popen(
                self.cmd,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # Write input to stdin
            proc.stdin.write(self.input_text)
            # proc.stdin.close()

            # Process output while checking for cancellation
            # while proc.poll() is None:
            #     if self._stopped:
            #         proc.terminate()
            #         break
            #     self.msleep(100)

            # if self._stopped:
            #     self.error.emit("Command cancelled")
            #     return

            stdout, stderr = proc.communicate(input=self.input_text)

            if proc.returncode != 0:
                error_msg = f"Command failed ({proc.returncode}): {stderr.strip()}"
                self.error.emit(error_msg)
            else:
                output = stdout
                if stderr.strip():
                    output += f"\n[stderr]\n{stderr.strip()}"
                self.finished.emit(output)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(f"Execution error: {str(e)}")

    def stop(self):
        self._stopped = True

class CmdPlugin(PluginInterface):
    NAME = "CMD"
    PREFIX = "$"
    IS_DEFAULT = False
    PRIORITY = 10

    def __init__(self, launcher_instance):
        super().__init__(launcher_instance)
        self.worker = None
        self.current_cmd = ""
        self.auto_preview_mode = False

    def get_status_message(self) -> str:
        if self.auto_preview_mode:
            return '⚠️ CMD mode - Auto-preview active ($$ prefix) - Use with caution! '
        return "$CMD mode - Preview requires Ctrl+Enter or $$ prefix for autopreview"

    def update_preview(self, command: str, selected_text: str, preview_widget: QTextEdit, status_widget: QLabel, manual: bool) -> None:
        self.auto_preview_mode = command.startswith("$$")
        cmd_part = command[2:].strip() if self.auto_preview_mode else command[1:].strip()
        if not self.auto_preview_mode and not manual:
            self.launcher.resetStatus(self)
            preview_widget.hide()
            self._cleanup_worker()
            return

        if not cmd_part:
            self.launcher.resetStatus(self)
            preview_widget.hide()
            self._cleanup_worker()
            return

        # Check if command has changed
        if cmd_part == self.current_cmd:
            return

        self.current_cmd = cmd_part

        self._cleanup_worker()
        self.worker = CmdWorker(cmd_part, selected_text)
        self.worker.finished.connect(lambda out: self._update_preview(out, preview_widget, status_widget))
        self.worker.error.connect(lambda err: self._handle_error(err, preview_widget, status_widget))
        self.worker.start()

        preview_widget.setPlainText("Executing command...")
        preview_widget.show()
        status_widget.setText("⌛ Running command...")
        self.launcher.adjustHeight()

    def _update_preview(self, output, preview_widget, status_widget):
        preview_widget.setPlainText(output)
        status_widget.setText("✅ Command preview - Updates automatically")
        self.launcher.adjustHeight()

    def _handle_error(self, error, preview_widget, status_widget):
        preview_widget.setPlainText(error)
        status_widget.setText("❌ Command error")
        preview_widget.show()
        self.launcher.adjustHeight()
    @snoop
    def execute(self, command: str, selected_text: str) -> str | None:
        self.auto_preview_mode = command.startswith("$")
        cmd = command[1:].strip() if self.auto_preview_mode else command.strip()

        self._cleanup_worker()
        self.worker = CmdWorker(cmd, selected_text)
        self.worker.finished.connect(self._handle_execution)
        self.worker.error.connect(self._handle_execution_error)
        self.worker.start()

        self.launcher.status_bar.setText("⌛ Executing command...")
        return None

    def _handle_execution(self, output):
        self.launcher.copy(output)

    def _handle_execution_error(self, error):
        self.launcher.status_bar.setText(f"❌ {error}")

    def _cleanup_worker(self):
        if self.worker:
            if self.worker.isRunning():
                self.worker.stop()
                self.worker.quit()
                self.worker.wait()
            self.worker = None

    def cleanup(self) -> None:
        self._cleanup_worker()