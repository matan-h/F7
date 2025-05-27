from __future__ import annotations

import os
import re
import traceback
from typing import Optional

from PyQt6.QtCore import QTimer, pyqtSignal

from F7.utils import remove_none

from .base_plugin import PluginInterface, Thread

SYSPROMPT = """You are a string tool. You'll get input as:
text:`<text>` request:`<operation>`
Reply with exactly the transformed string—nothing else, no code fences or explanations."""


class AIStreamWorker(Thread):
    chunk_received = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, prompt: str, text: str, settings):
        super().__init__()
        self.prompt = prompt
        self.text = text
        self.settings = settings
        self._running = True

    def run(self):
        backend = self.settings.backend
        buffer = ""
        try:
            if backend == "ollama":
                import ollama

                messages = [
                    {
                        "role": "user",
                        "content": f"text:```\n{self.text}\n```\nUser request:{self.prompt}",
                    }
                ]
                if self.settings.system_prompt:
                    messages.insert(
                        0, {"role": "system", "content": self.settings.system_prompt}
                    )
                response = ollama.chat(
                    model=self.settings.ollama_model,
                    messages=messages,
                    stream=True,
                    options=self._ollama_opts(),
                )
                for chunk in response:
                    if not self._running:
                        break
                    content = chunk.get("message", {}).get("content", "")
                    buffer += content
                    self.chunk_received.emit(content)

            else:
                if not os.path.exists(self.settings.llama_cpp_model):
                    raise FileNotFoundError(
                        f"Model file not found: {self.settings.llama_cpp_model}"
                    )
                import llama_cpp

                llm = llama_cpp.Llama(
                    model_path=self.settings.llama_cpp_model,
                    verbose=False,
                    **self._get_llama_cpp_kwargs(),
                )
                prompt_text = self._build_prompt()
                response = llm.create_completion(
                    prompt_text, stream=True, **self._llama_cpp_opts()
                )
                for chunk in response:
                    if not self._running:
                        break
                    content = chunk["choices"][0]["text"]
                    buffer += content
                    self.chunk_received.emit(content)

            if self._running:
                self.finished_signal.emit(buffer)
        except Exception as e:
            self.error_occurred.emit(traceback.format_exc() + str(e))

    def stop(self):
        self._running = False

    @remove_none
    def _ollama_opts(self):
        opts = {
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "frequency_penalty": self.settings.frequency_penalty,
            "presence_penalty": self.settings.presence_penalty,
            "seed": self.settings.seed,
            "stop": self.settings.stop_sequences,
            "num_predict": self.settings.max_tokens,
        }
        return opts

    @remove_none
    def _llama_cpp_opts(self):
        opts = {
            "max_tokens": self.settings.max_tokens,
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "frequency_penalty": self.settings.frequency_penalty,
            "presence_penalty": self.settings.presence_penalty,
            "stop": self.settings.stop_sequences,
        }

        return opts

    @remove_none
    def _get_llama_cpp_kwargs(self):
        return {
            "n_threads": self.settings.llama_cpp_n_threads or (os.cpu_count() or 4),
            "n_gpu_layers": -1 if self.settings.llama_cpp_use_GPU else None,
        }

    def _build_prompt(self):
        base = f"USER: `{self.prompt}`\ntext:```\n{self.text}\n```"
        return (
            f"{self.settings.system_prompt}\n{base}"
            if self.settings.system_prompt
            else base
        )


class AiOllamaPlugin(PluginInterface):
    NAME = "Ollama AI"
    PREFIX = "!"
    SUFFIX = "!"
    PRIORITY = 10

    def __init__(self, api, settings):
        super().__init__(api, settings)
        self.current_worker: AIStreamWorker | None = None
        self._preview_buffer = ""
        self._preview_cmd = None
        self._last_preview = None

    def register_settings(self, settings):
        sec = settings.section("ai_ollama")
        sec.add("backend", "AI backend", "ollama", str, options=["ollama", "llama_cpp"])
        sec.add("ollama_model", "Ollama model", "phi3", str)
        sec.add("llama_cpp_model", "Llama.cpp model path", "", str)
        sec.add(
            "llama_cpp_n_threads",
            "Number of threads to use for generation (default: os.cpu_count)",
            None,
            int,
        )
        sec.add("llama_cpp_use_GPU", "Use GPU", False, bool)
        sec.add("system_prompt", "System prompt", SYSPROMPT, str)
        sec.add("max_tokens", "Max tokens", 100, int)
        sec.add("temperature", "Temperature", None, float)
        sec.add("top_p", "Top-p", None, float)
        sec.add("frequency_penalty", "Freq penalty", None, float)
        sec.add("presence_penalty", "Presence penalty", None, float)
        sec.add("timeout", "Timeout sec", 30, int)
        sec.add("seed", "Random seed", None, int)
        sec.add("stop_sequences", "Stop seqs", None, list)

    def get_status_message(self) -> str:
        cfg = self.settings.ai_ollama
        model = (
            cfg.ollama_model
            if cfg.backend == "ollama"
            else os.path.basename(cfg.llama_cpp_model)
        )
        return f"🤖 {cfg.backend} ({model}) - Ctrl+Enter: preview, Enter: run"

    def extract_code(self, txt: str) -> str:
        m = re.search(r"```(?:[\w\-\+]+)?\n(.*)", txt, re.DOTALL)
        if not m:
            return txt.strip()
        body = m.group(1)
        end = re.search(r"\n```", body)
        return body[: end.start()].strip() if end else body.strip()

    def _start(self, prompt: str, text: str, is_preview: bool):
        # Stop existing worker
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.stop()
            self.current_worker.quit()
            self.current_worker.wait(500)

        if is_preview:
            self._preview_buffer = ""
        self.api.update_preview_content("")  # hide the preview.
        self.api.set_status("⏳ Contacting AI...")

        worker = AIStreamWorker(prompt, text, self.settings.ai_ollama)
        self.current_worker = worker
        self.active_workers.append(worker)

        worker.chunk_received.connect(lambda c: self._on_chunk(c, is_preview))
        worker.finished_signal.connect(lambda full: self._on_done(full, is_preview))
        worker.error_occurred.connect(lambda err: self._on_error(err))

        worker.start()
        timeout = self.settings.ai_ollama.timeout
        if timeout and timeout > 0:
            QTimer.singleShot(timeout * 1000, worker.stop)

    def _on_chunk(self, chunk: str, is_preview: bool):
        print(chunk, end="")
        self._preview_buffer += chunk
        processed = self.extract_code(self._preview_buffer)
        self.api.update_preview_content(f"AI: {processed}")

    def _on_done(self, full: str, is_preview: bool):
        result = self.extract_code(full)
        if is_preview:
            self._last_preview = result
            self.api.set_status("✅ Preview ready")
        else:
            self.api.close(copy_and_close_text=result)

    def _on_error(self, msg: str):
        print("AI error:", msg)
        self.api.update_preview_content(msg)
        self.api.set_status(f"❌ Error: {msg}")

    def update_preview(self, command: str, selected_text: str, manual: bool) -> None:
        if not manual:
            return
        cmd = command.lstrip(self.PREFIX).rstrip(self.SUFFIX)

        if not cmd:
            return
        if cmd != self._preview_cmd:
            self._preview_cmd = cmd
            self._preview_buffer = ""
        self._start(cmd, selected_text, True)

    def execute(self, command: str, selected_text: str) -> Optional[str]:
        cmd = command.lstrip(self.PREFIX).rstrip(self.SUFFIX)
        if cmd == self._preview_cmd and self._last_preview:
            return self._last_preview
        self._start(cmd, selected_text, False)
        return None

    def cleanup(self) -> None:
        super().cleanup()
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.stop()
            self.current_worker.quit()
            self.current_worker.wait()
