# plugins/ai_ollama_plugin.py
import re
import os
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import QTextEdit, QLabel
from .base_plugin import PluginInterface
from ..utils import dotdict

SYSPROMPT = """You are a string tool. You'll get input as:
text:`<text>` request:`<operation>`
Reply with exactly the transformed string—nothing else, no code fences or explanations."""

class AIStreamWorker(QThread):
    chunk_received = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, msg, text, settings):
        super().__init__()
        self.msg = msg
        self.text = text
        self.settings = settings
        self._is_running = True

    def run(self):
        backend = self.settings.backend
        full_response = ""
        
        try:
            if backend == "ollama":
                import ollama
                messages = [{
                    "role": "user", 
                    "content": f"text:```\n{self.text}\n```\nUser request:{self.msg}"
                }]
                if self.settings.system_prompt:
                    messages.insert(0, {"role": "system", "content": self.settings.system_prompt})
                
                response = ollama.chat(
                    model=self.settings.ollama_model,
                    messages=messages,
                    stream=True,
                    options=self._get_ollama_options()
                )
                
                for chunk in response:
                    if not self._is_running:
                        break
                    content = chunk.get('message', {}).get('content', '')
                    full_response += content
                    self.chunk_received.emit(content)

            elif backend == "llama_cpp":
                if not os.path.exists(self.settings.llama_cpp_model):
                    raise FileNotFoundError(f"Model file not found: {self.settings.llama_cpp_model}")
                
                import llama_cpp
                llm = llama_cpp.Llama(
                    model_path=self.settings.llama_cpp_model,
                    verbose=False,
                    **self._get_llama_cpp_kwargs()
                )
                
                prompt = self._build_llama_prompt()
                response = llm.create_completion(
                    prompt,
                    stream=True,
                    **self._get_llama_options()
                )
                
                for chunk in response:
                    if not self._is_running:
                        break
                    content = chunk['choices'][0]['text']
                    full_response += content
                    self.chunk_received.emit(content)

            if self._is_running:
                self.finished_signal.emit(full_response)

        except Exception as e:
            self.error_occurred.emit(f"{backend} Error: {str(e)}")

    # Helper methods for backend configurations
    def _get_ollama_options(self):
        return {k: v for k, v in {
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "frequency_penalty": self.settings.frequency_penalty,
            "presence_penalty": self.settings.presence_penalty,
            "seed": self.settings.seed,
            "stop": self.settings.stop_sequences,
            "num_predict": self.settings.max_tokens,
        }.items() if v is not None}

    def _get_llama_cpp_kwargs(self):
        kwargs = dotdict()
        kwargs.n_threads = self.settings.llama_cpp_n_threads or (os.cpu_count() or 4)
        if self.settings.llama_cpp_use_GPU:
            kwargs.n_gpu_layers = -1
        return kwargs

    def _build_llama_prompt(self):
        base = f"USER: `{self.msg}`\ntext:```\n{self.text}\n```"
        return f"{self.settings.system_prompt}\n{base}" if self.settings.system_prompt else base

    def _get_llama_options(self):
        return {k: v for k, v in {
            "max_tokens": self.settings.max_tokens,
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "frequency_penalty": self.settings.frequency_penalty,
            "presence_penalty": self.settings.presence_penalty,
            "stop": self.settings.stop_sequences,
        }.items() if v is not None}

    def stop(self):
        self._is_running = False

class AiOllamaPlugin(PluginInterface):
    NAME = "Ollama AI"
    PREFIX = "!"
    SUFFIX = "!"
    IS_DEFAULT = False
    PRIORITY = 10

    def __init__(self, launcher_instance):
        super().__init__(launcher_instance)
        self.current_stream = None
        self.preview_state = {
            'buffer': '',
            'last_command': None,
            'last_result': None,
            'current_visible': ''
        }
        self.execution_state = {
            'buffer': '',
            'current_visible': '',
            'active': False
        }

    def register_settings(self, settings):
        """Register plugin settings with the launcher."""
        ai_section = settings.section("ai_ollama")
        ai_section.add("backend", "AI backend to use", "ollama", str, options=["ollama", "llama_cpp"])
        ai_section.add("ollama_model", "Model name for Ollama", "phi3", str)
        ai_section.add("llama_cpp_model", "Path to model file for llama_cpp", "", str)
        ai_section.add("llama_cpp_n_threads", "Number of threads to use for generation (default: os.cpu_count) ", None, int)
        ai_section.add("llama_cpp_use_GPU", "enable n_gpu_layers=-1 so llama.cpp would use the GPU ", False, bool)

        ai_section.add("system_prompt", "System prompt for the AI", SYSPROMPT, str)
        ai_section.add("max_tokens", "Maximum number of tokens to generate", 100, int)
        ai_section.add("temperature", "Sampling temperature", None, float)
        ai_section.add("top_p", "Top-p sampling parameter", None, float)
        ai_section.add("frequency_penalty", "Frequency penalty", None, float)
        ai_section.add("presence_penalty", "Presence penalty", None, float)
        ai_section.add("timeout", "Timeout for AI response in seconds", 30, int)
        ai_section.add("seed", "Random seed for reproducibility", None, int)
        ai_section.add("stop_sequences", "Sequences to stop generation", None, list)

        # ... (settings registration remains same) ...

    def extract_code_block(self, text: str) -> str:
        """Improved code block extraction with partial matching support"""
        open_match = re.search(r'```(?:[\w\-\+]+)?\n(.*)', text, re.DOTALL)
        if not open_match:
            return text.strip()
        
        content = open_match.group(1)
        close_match = re.search(r'\n```', content)
        return content[:close_match.start()].strip() if close_match else content.strip()

    def get_status_message(self) -> str:
        backend = self.launcher.settings.ai_ollama.backend
        model = (self.launcher.settings.ai_ollama.ollama_model if backend == "ollama"
                 else os.path.basename(self.launcher.settings.ai_ollama.llama_cpp_model))
        return f"🤖 {backend} ({model}) - Ctrl+Enter: preview, Enter: execute"

    def _start_stream(self, command: str, selected_text: str, is_preview: bool):
        """Common method to start both preview and execution streams"""
        self._cleanup_worker()
        
        # Reset state
        if is_preview:
            self.preview_state = {
                'buffer': '',
                'last_command': command,
                'last_result': None,
                'current_visible': ''
            }
        else:
            self.execution_state = {'buffer': '', 'current_visible': '','active': True}

        # UI setup
        preview_widget = self.launcher.preview_output
        status_widget = self.launcher.status_bar
        
        preview_widget.setPlainText("AI: Generating...")
        preview_widget.show()
        status_widget.setText("⏳ Contacting AI..." if is_preview else "⏳ Processing...")
        self.launcher.adjustHeight()

        # Create worker
        self.current_stream = AIStreamWorker(
            command, selected_text, self.launcher.settings.ai_ollama
        )
        self.active_workers.append(self.current_stream)

        # Connect common signals
        self.current_stream.chunk_received.connect(
            lambda c: self._handle_chunk(c, is_preview)
        )
        self.current_stream.error_occurred.connect(
            lambda e: self._handle_error(e, is_preview)
        )
        self.current_stream.finished_signal.connect(
            lambda r: self._handle_completion(r, is_preview)
        )

        # Start processing
        self.current_stream.start()
        if self.launcher.settings.ai_ollama.timeout > 0:
            QTimer.singleShot(
                self.launcher.settings.ai_ollama.timeout * 1000,
                self.current_stream.stop
            )

    def _handle_chunk(self, chunk: str, is_preview: bool):
        """Process incoming chunks for both preview and execution"""
        target_state = self.preview_state if is_preview else self.execution_state
        print(chunk,end='')
        target_state['buffer'] += chunk
        
        processed = self.extract_code_block(target_state['buffer'])
        widget = self.launcher.preview_output
        
        if processed != target_state['current_visible']:
            widget.setPlainText(f"AI: {processed}")
            target_state['current_visible'] = processed
            self.launcher.adjustHeight()

    def _handle_completion(self, full_response: str, is_preview: bool):
        """Final processing after stream completes"""
        if is_preview:
            # Store both raw and processed result
            self.preview_state['last_result'] = self.extract_code_block(full_response)
            self.preview_state['buffer'] = full_response
            self.launcher.status_bar.setText("✅ Preview ready - Ctrl+Enter to refresh")
        else:
            # Use the accumulated buffer rather than full_response for consistency
            result = self.extract_code_block(self.execution_state['buffer'])
            print("copy",repr(result),"exacted from",repr(self.execution_state['buffer']))
            self.launcher.copy(result)

    def _handle_error(self, error_msg: str, is_preview: bool):
        """Error handling for both modes"""
        widget = self.launcher.preview_output
        widget.setPlainText(error_msg)
        widget.show()
        
        status = self.launcher.status_bar
        status.setText("❌ Error: " + ("preview failed" if is_preview else "execution failed"))

    def update_preview(self, command: str, selected_text: str, 
                      preview_widget: QTextEdit, status_widget: QLabel, manual: bool):
        if not manual:
            preview_widget.hide()
            self._cleanup_worker()
            return
            
        ai_command = command.lstrip(self.PREFIX)
        if not ai_command:
            preview_widget.hide()
            self._cleanup_worker()
            return
            
        # Always reset preview state when starting new preview
        if ai_command != self.preview_state.get('last_command'):
            self.preview_state = {
                'buffer': '',
                'last_command': ai_command,
                'last_result': None,
                'current_visible': ''
            }
            
        self._start_stream(ai_command, selected_text, is_preview=True)

    def execute(self, command: str, selected_text: str) -> str | None:
        ai_command = command.lstrip(self.PREFIX)
        
        if ai_command == self.preview_state.get('last_command') and self.preview_state.get('last_result'):
            self.launcher.copy(self.preview_state['last_result'])
            return None
            
        # Reset execution state before starting
        self.execution_state = {
            'buffer': '',
            'current_visible': '',
            'active': True
        }
        self._start_stream(ai_command, selected_text, is_preview=False)
        return None

    def _cleanup_worker(self):
        if self.current_stream and self.current_stream.isRunning():
            self.current_stream.stop()
            self.current_stream.quit()
            self.current_stream.wait(1000)
            if self.current_stream.isRunning():
                self.current_stream.terminate()
            self.current_stream = None

    def cleanup(self):
        super().cleanup()
        self._cleanup_worker()