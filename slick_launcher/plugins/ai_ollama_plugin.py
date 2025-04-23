# plugins/ai_ollama_plugin.py
import importlib
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QTextEdit, QLabel
from .base_plugin import PluginInterface

# import ollama # Make sure ollama is installed. TODO: only load when needed.
def _get_ollama_module():
    # just "import ollama take 200ms. openai take 500ms. so I lazy load them."
    if not hasattr(_get_ollama_module, "_module"):
        _get_ollama_module._module = importlib.import_module('ollama')
    return _get_ollama_module._module

# --- Configuration ---
# Consider moving these to a config file or environment variables
AI_MODEL_NAME = "phi3"  # Or "qwen2.5-coder:1.5b", etc.
SYSTEM_PROMPT = """
You are a smart text-processing program. For each request, perform the operation on the given text and output **exactly** the result, nothing more. Put the final answer in a code block if appropriate for the content.
"""
# --- End Configuration ---

class AIStreamWorker(QThread):
    """ Worker thread for handling Ollama streaming API calls. """
    chunk_received = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, msg, text):
        super().__init__()
        self.msg = msg
        self.text = text
        self._is_running = True

    def run(self):
        full_response = ""
        try:
            response = _get_ollama_module().chat(
                model=AI_MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{self.msg}\ntext:```\n{self.text}\n```"}
                ],
                stream=True
            )
            for chunk in response:
                if not self._is_running: # Check if termination requested
                    break
                content = chunk.get('message', {}).get('content')
                if content:
                    self.chunk_received.emit(content)
                    full_response += content
            if self._is_running:
                self.finished_signal.emit(full_response)
        except Exception as e:
            # traceback.print_exc() # For debugging
            self.error_occurred.emit(f"AI Error: {str(e)}")

    def stop(self):
        self._is_running = False


class AiOllamaPlugin(PluginInterface):
    NAME = "Ollama AI"
    PREFIX = "!"
    SUFFIX = "!"
    IS_DEFAULT = False
    PRIORITY = 10 # High priority because of specific prefix/suffix

    def __init__(self, launcher_instance):
        super().__init__(launcher_instance)
        self.ai_worker = None
        self.is_first_chunk = True
        self.accumulated_result = ""

    def get_status_message(self) -> str:
        return f"🤖 AI mode ({AI_MODEL_NAME}) - Ctrl+Enter to preview, Enter to execute"

    def _start_ai_stream(self, command: str, selected_text: str, preview_widget: QTextEdit, status_widget: QLabel, for_preview: bool):
        """Starts or restarts the AI worker thread."""
        self._cleanup_worker() # Stop existing worker if any

        self.is_first_chunk = True
        preview_widget.setPlainText("AI: Generating...")
        preview_widget.show()
        status_widget.setText("⏳ Contacting AI...")
        self.launcher.adjustHeight() # Adjust height for "Generating..." message

        self.ai_worker = AIStreamWorker(command, selected_text)

        if for_preview:
            # Connect signals for preview updates
            self.ai_worker.chunk_received.connect(lambda chunk: self._update_preview_text(chunk, preview_widget))
            self.ai_worker.finished_signal.connect(lambda fr: self._handle_preview_finished(fr, status_widget))
            self.ai_worker.error_occurred.connect(lambda err: self._handle_ai_error(err, preview_widget, status_widget))
        else:
            # Connect signals for final execution
            self.accumulated_result = "" # Reset result for execution
            self.ai_worker.chunk_received.connect(self._accumulate_ai_result)
            self.ai_worker.finished_signal.connect(self._finalize_ai_command)
            self.ai_worker.error_occurred.connect(lambda err: self._handle_ai_error(err, preview_widget, status_widget, is_final_error=True))

        self.ai_worker.start()

    def update_preview(self, command: str, selected_text: str, preview_widget: QTextEdit, status_widget: QLabel,manual:bool) -> None:
        """Handles Ctrl+Enter preview generation."""
        if not manual:return;
        # Command here includes the prefix, strip it for the AI prompt
        ai_command = command.lstrip(self.PREFIX)
        if not ai_command:
            preview_widget.hide()
            self._cleanup_worker() # Stop worker if command becomes empty
            return

        # Start streaming for preview
        self._start_ai_stream(ai_command, selected_text, preview_widget, status_widget, for_preview=True)

    def _update_preview_text(self, chunk: str, preview_widget: QTextEdit):
        """Appends chunk to the preview widget during streaming."""
        if self.is_first_chunk:
            preview_widget.setPlainText("AI: ") # Clear "Generating..."
            self.is_first_chunk = False

        cursor = preview_widget.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        preview_widget.ensureCursorVisible()
        # Adjust height dynamically during preview streaming might be jittery.
        # Consider adjusting only at the end or periodically.
        # self.launcher.adjustHeight()

    def _handle_preview_finished(self, full_response: str, status_widget: QLabel):
        status_widget.setText("✅ AI preview complete - Ctrl+Enter to re-gen")
        self.launcher.adjustHeight() # Adjust height once preview is done

    def _handle_ai_error(self, error_msg: str, preview_widget: QTextEdit, status_widget: QLabel, is_final_error: bool = False):
        """Displays AI errors."""
        preview_widget.setPlainText(error_msg)
        preview_widget.show()
        status_widget.setText("❌ AI Error occurred")
        self.launcher.adjustHeight()
        if is_final_error:
             # Quit after showing the error if it happened during final execution
             QTimer.singleShot(3000, self.launcher.quit)


    def execute(self, command: str, selected_text: str) -> str | None:
        """Handles Enter execution - runs AI and copies result."""
        # Command here is already stripped of the prefix by the launcher
        status_widget = self.launcher.status_bar # Need status widget access
        preview_widget = self.launcher.preview_output # Need preview widget access for errors
        status_widget.setText("⏳ Processing AI command...")
        self.launcher.hide_preview() # Hide preview during final execution maybe?

        # Start streaming for final result accumulation
        self._start_ai_stream(command, selected_text, preview_widget, status_widget, for_preview=False)

        # IMPORTANT: Since the actual result processing (_finalize_ai_command)
        # happens asynchronously via signals, execute() returns None.
        # The plugin itself will handle copying and quitting via the connected slots.
        return None

    def _accumulate_ai_result(self, chunk: str):
        """Collects chunks for the final result."""
        self.accumulated_result += chunk

    def _finalize_ai_command(self, full_result: str):
        """Called when AI stream finishes during execute."""
        clipboard = self.launcher.get_clipboard() # Use launcher's method
        if clipboard:
             clipboard.setText(full_result)
             self.launcher.status_bar.setText(f"📋 AI result copied ({len(full_result)} chars)")
             QTimer.singleShot(1500, self.launcher.quit) # Quit after a short delay
        else:
             self.launcher.status_bar.setText("Error: Could not access clipboard")
             QTimer.singleShot(2000, self.launcher.quit)


    def _cleanup_worker(self):
        """Stops and cleans up the AI worker thread."""
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.stop()
            self.ai_worker.quit() # Ask event loop to quit
            self.ai_worker.wait(1000) # Wait a bit for clean exit
            if self.ai_worker.isRunning(): # Force terminate if still running
                 self.ai_worker.terminate()
                 self.ai_worker.wait() # Wait after terminate
        self.ai_worker = None

    def cleanup(self) -> None:
        """Ensure worker thread is stopped when launcher quits."""
        self._cleanup_worker()