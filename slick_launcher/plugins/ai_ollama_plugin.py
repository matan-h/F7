# plugins/ai_ollama_plugin.py
import importlib
import re
import os
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QTextEdit, QLabel
from .base_plugin import PluginInterface

# default sysprompt
SYSPROMPT ="""
You are a string tool. You'll get input as:
text:`<text>` request:`<operation>`
Reply with exactly the transformed string—nothing else, no code fences or explanations.
"""
# Lazy-load modules to reduce startup time
def _get_ollama_module():
    if not hasattr(_get_ollama_module, "_module"):
        _get_ollama_module._module = importlib.import_module('ollama')
    return _get_ollama_module._module

def _get_llama_cpp_module():
    if not hasattr(_get_llama_cpp_module, "_module"):
        _get_llama_cpp_module._module = importlib.import_module('llama_cpp')
    return _get_llama_cpp_module._module

class AIStreamWorker(QThread):
    """Worker thread for handling AI streaming with Ollama or llama_cpp."""
    chunk_received = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, msg, text, settings):
        super().__init__()
        self.msg = msg
        self.text = text
        self.settings = settings
        self._is_running = True
    @snoop

    def run(self):
        """Execute the appropriate backend based on settings."""
        backend = self.settings.backend
        full_response = ""
        in_block = False  # Inside ```...```
        in_declare = False  # Inside ```lang declaration

        if backend == "ollama":
            try:
                ollama = _get_ollama_module()
                options = {
                    k: v for k, v in {
                        "temperature": self.settings.temperature,
                        "top_p": self.settings.top_p,
                        "frequency_penalty": self.settings.frequency_penalty,
                        "presence_penalty": self.settings.presence_penalty,
                        "seed": self.settings.seed,
                        "stop": self.settings.stop_sequences,
                        "num_predict": self.settings.max_tokens,
                    }.items() if v is not None
                }
                messages = [{"role": "user", "content": f"text:```\n{self.text}\n```\nUser request:{self.msg}"}]
                if self.settings.system_prompt is not None:
                    messages.insert(0, {"role": "system", "content": self.settings.system_prompt})
                response = ollama.chat(
                    model=self.settings.ollama_model,
                    messages=messages,
                    stream=True,
                    options=options
                )
                for chunk in response:
                    if not self._is_running:
                        break
                    content = chunk.get('message', {}).get('content', '')
                    full_response += content
                    # Handle code block filtering
                    if content.strip().startswith("```"):
                        if not in_block:
                            in_declare = True
                        else:
                            in_block = False
                            continue
                    if in_declare:
                        if "\n" in content:
                            in_declare = False
                            in_block = True
                        continue
                    if in_block:
                        self.chunk_received.emit(content)
                if self._is_running:
                    self.finished_signal.emit(full_response)
            except Exception as e:
                self.error_occurred.emit(f"Ollama Error: {str(e)}")
        elif backend == "llama_cpp":
            if not os.path.exists(self.settings.llama_cpp_model):
                self.error_occurred.emit(f"Model file not found: {self.settings.llama_cpp_model}")
                return
            try:
                llama_cpp = _get_llama_cpp_module()
                llm = llama_cpp.Llama(model_path=self.settings.llama_cpp_model)
                prompt = f"USER: `{self.msg}`\ntext:```\n{self.text}\n```"
                if self.settings.system_prompt is not None:
                    prompt = f"{self.settings.system_prompt}\n{prompt}"
                options = {
                    k: v for k, v in {
                        "max_tokens": self.settings.max_tokens,
                        "temperature": self.settings.temperature,
                        "top_p": self.settings.top_p,
                        "frequency_penalty": self.settings.frequency_penalty,
                        "presence_penalty": self.settings.presence_penalty,
                        "stop": self.settings.stop_sequences,
                    }.items() if v is not None
                }
                response = llm.create_completion(
                    prompt,
                    stream=True,
                    **options
                )
                for chunk in response:
                    print("C:",chunk)
                    if not self._is_running:
                        break
                    content = chunk['choices'][0]['text']
                    full_response += content
                    # Handle code block filtering
                    if content.strip().startswith("```"):
                        if not in_block:
                            in_declare = True
                        else:
                            in_block = False
                            continue
                    if in_declare:
                        if "\n" in content:
                            in_declare = False
                            in_block = True
                        continue
                    if in_block:
                        self.chunk_received.emit(content)
                if self._is_running:
                    self.finished_signal.emit(full_response)
            except Exception as e:
                self.error_occurred.emit(f"llama_cpp Error: {str(e)}")
        else:
            self.error_occurred.emit("Invalid backend specified")

    def stop(self):
        """Signal the thread to stop processing."""
        self._is_running = False

class AiOllamaPlugin(PluginInterface):
    NAME = "Ollama AI"
    PREFIX = "!"
    SUFFIX = "!"
    IS_DEFAULT = False
    PRIORITY = 10

    def __init__(self, launcher_instance):
        super().__init__(launcher_instance)
        self.ai_worker = None
        self.is_first_chunk = True
        self.accumulated_result = ""
        self.last_preview_command = None
        self.last_preview_result = None

    def register_settings(self, settings):
        """Register plugin settings with the launcher."""
        ai_section = settings.section("ai_ollama")
        ai_section.add("backend", "AI backend to use", "ollama", str, options=["ollama", "llama_cpp"])
        ai_section.add("ollama_model", "Model name for Ollama", "phi3", str)
        ai_section.add("llama_cpp_model", "Path to model file for llama_cpp", "", str)
        ai_section.add("system_prompt", "System prompt for the AI", SYSPROMPT, str)
        ai_section.add("max_tokens", "Maximum number of tokens to generate", 100, int)
        ai_section.add("temperature", "Sampling temperature", None, float)
        ai_section.add("top_p", "Top-p sampling parameter", None, float)
        ai_section.add("frequency_penalty", "Frequency penalty", None, float)
        ai_section.add("presence_penalty", "Presence penalty", None, float)
        ai_section.add("timeout", "Timeout for AI response in seconds", 30, int)
        ai_section.add("seed", "Random seed for reproducibility", None, int)
        ai_section.add("stop_sequences", "Sequences to stop generation", None, list)

    def extract_code_block(self, text: str) -> str:
        """Extract content from the first code block, if present."""
        match = re.search(r'```(?:\w+)?\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def get_status_message(self) -> str:
        """Display the current backend and model in the status bar."""
        backend = self.launcher.settings.ai_ollama.backend
        model = (self.launcher.settings.ai_ollama.ollama_model if backend == "ollama"
                 else self.launcher.settings.ai_ollama.llama_cpp_model)
        return f"🤖 AI mode ({backend}: {model}) - Ctrl+Enter to preview, Enter to execute"

    def _start_ai_stream(self, command: str, selected_text: str, preview_widget: QTextEdit, status_widget: QLabel, for_preview: bool):
        """Start or restart the AI worker thread with the configured settings."""
        self._cleanup_worker()
        self.is_first_chunk = True
        preview_widget.setPlainText("AI: Generating...")
        preview_widget.show()
        status_widget.setText("⏳ Contacting AI...")
        self.launcher.adjustHeight()

        self.ai_worker = AIStreamWorker(command, selected_text, self.launcher.settings.ai_ollama)
        if for_preview:
            self.ai_worker.chunk_received.connect(lambda chunk: self._update_preview_text(chunk, preview_widget))
            self.ai_worker.finished_signal.connect(lambda fr: self._handle_preview_finished(fr, status_widget))
            self.ai_worker.error_occurred.connect(lambda err: self._handle_ai_error(err, preview_widget, status_widget))
        else:
            self.accumulated_result = ""
            self.ai_worker.chunk_received.connect(self._accumulate_ai_result)
            self.ai_worker.finished_signal.connect(self._finalize_ai_command)
            self.ai_worker.error_occurred.connect(lambda err: self._handle_ai_error(err, preview_widget, status_widget, is_final_error=True))
        self.ai_worker.start()
        # Apply timeout
        if self.launcher.settings.ai_ollama.timeout > 0:
            QTimer.singleShot(self.launcher.settings.ai_ollama.timeout * 1000, self.ai_worker.stop)

    def update_preview(self, command: str, selected_text: str, preview_widget: QTextEdit, status_widget: QLabel, manual: bool) -> None:
        """Handle preview generation on Ctrl+Enter."""
        if not manual:
            preview_widget.hide()
            self._cleanup_worker()
            return
        ai_command = command.lstrip(self.PREFIX)
        if not ai_command:
            preview_widget.hide()
            self._cleanup_worker()
            return
        self.last_preview_command = ai_command
        self._start_ai_stream(ai_command, selected_text, preview_widget, status_widget, for_preview=True)

    def _update_preview_text(self, chunk: str, preview_widget: QTextEdit):
        """Update the preview widget with streaming chunks."""
        if self.is_first_chunk:
            preview_widget.setPlainText("AI: ")
            self.is_first_chunk = False
        cursor = preview_widget.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        preview_widget.ensureCursorVisible()
        self.launcher.adjustHeight()

    def _handle_preview_finished(self, full_response: str, status_widget: QLabel):
        """Update status and store result when preview streaming completes."""
        self.last_preview_result = self.extract_code_block(full_response)
        status_widget.setText("✅ AI preview complete - Ctrl+Enter to re-gen")
        self.launcher.adjustHeight()

    def _handle_ai_error(self, error_msg: str, preview_widget: QTextEdit, status_widget: QLabel, is_final_error: bool = False):
        """Display errors in the UI."""
        preview_widget.setPlainText(error_msg)
        preview_widget.show()
        status_widget.setText("❌ AI Error occurred")
        self.launcher.adjustHeight()
        if is_final_error:
            QTimer.singleShot(3000, self.launcher.quit)

    def execute(self, command: str, selected_text: str) -> str | None:
        """Handle final execution on Enter."""
        status_widget = self.launcher.status_bar
        preview_widget = self.launcher.preview_output
        ai_command = command.lstrip(self.PREFIX)
        if self.last_preview_command and ai_command == self.last_preview_command and self.last_preview_result is not None:
            self.launcher.copy(self.last_preview_result)
            return None
        status_widget.setText("⏳ Processing AI command...")
        self.launcher.hide_preview()
        self._start_ai_stream(ai_command, selected_text, preview_widget, status_widget, for_preview=False)
        return None

    def _accumulate_ai_result(self, chunk: str):
        """Accumulate chunks for the final result."""
        self.accumulated_result += chunk

    def _finalize_ai_command(self, full_result: str):
        """Copy the final result to the clipboard and clean up."""
        cleaned_result = self.extract_code_block(full_result)
        self.launcher.copy(cleaned_result)

    def _cleanup_worker(self):
        """Stop and clean up the AI worker thread."""
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.stop()
            self.ai_worker.quit()
            self.ai_worker.wait(1000)
            if self.ai_worker.isRunning():
                self.ai_worker.terminate()
                self.ai_worker.wait()
        self.ai_worker = None

    def cleanup(self) -> None:
        """Ensure cleanup when the launcher quits."""
        self._cleanup_worker()