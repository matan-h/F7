import os
import subprocess
import sys
from typing import Optional

from f7.custom_types import pyqtSignal

from .base_plugin import PluginInterface, Thread


def get_default_shell() -> list[str]:
    """Return the default shell executable and argument based on the current OS."""
    if sys.platform == "win32":
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c"]
    else:
        return [os.environ.get("SHELL", "/bin/sh"), "-c"]


def _build_process(cmd: str, shell_exec: str, flag: str):
    # Build a subprocess invocation using explicit shell executable
    return subprocess.Popen(
        [shell_exec, flag, cmd],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _communicate(
    proc: subprocess.Popen, input_text: Optional[str], timeout: Optional[int] = None
):
    try:
        return proc.communicate(input=input_text or "", timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise


class CmdWorker(Thread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, cmd: str, input_text: Optional[str], shell_exec: str, flag: str):
        super().__init__()
        self.cmd = cmd
        self.input_text = input_text
        self.shell_exec = shell_exec
        self.shell_flag = flag
        self._stopped = False

    def run(self):
        try:
            proc = _build_process(self.cmd, self.shell_exec, self.shell_flag)
            stdout, stderr = _communicate(proc, self.input_text)

            if self._stopped:
                self.error.emit("Command cancelled by plugin")
                if proc.poll() is None:
                    proc.terminate()
                return

            if proc.returncode != 0:
                msg = f"Exit {proc.returncode}: {stderr.strip() or stdout.strip() or 'Unknown error'}"
                self.error.emit(msg)
            else:
                out = stdout.strip()
                if stderr.strip():
                    out += f"\n[stderr]\n{stderr.strip()}"
                self.finished.emit(out)
        except Exception as e:
            self.error.emit(f"Execution error: {e}")

    def stop(self):
        self._stopped = True


class CmdPlugin(PluginInterface):
    NAME = "CMD"
    PREFIX = "$"
    IS_DEFAULT = False
    PRIORITY = 10

    def __init__(self, api_instance, settings):  # Corrected type hint
        super().__init__(api_instance, settings)
        self.worker: Optional[CmdWorker] = None
        self.current_preview = ""
        self.auto_preview = False

    def get_status_message(self) -> str:
        if self.auto_preview:
            return "CMD Auto-Preview Active ($$). Use with caution!"
        return "CMD Mode: Use '$' (preview with Ctrl+Enter) or '$$' (auto-preview)."

    def update_preview(self, command: str, selected_text: str, manual: bool) -> None:
        self.auto_preview = command.startswith("$$")
        if self.auto_preview:  # $$
            cmd = command[2:].strip()
        else:
            cmd = command[1:].strip()
        if not (manual or self.auto_preview):
            if cmd != self.current_preview:
                self.api.update_preview_content("")
            self.api.reset_status()
            return

        if not cmd:
            self.api.update_preview_content("")
            self.api.set_status("Enter a command after '$'", self.NAME)
            self._cleanup_worker()
            self.current_preview = ""
            return

        # Avoid re-running the same preview command unnecessarily unless forced manually
        if (
            cmd == self.current_preview
            and not manual
            and self.worker
            and self.worker.isRunning()
        ):
            return

        self.current_preview = cmd
        self._cleanup_worker()  # Stop previous worker if any

        self.api.update_preview_content("Executing command for preview...")
        self.api.set_status("⏳ Running command for preview...", self.NAME)

        shell = self.settings.cmd_plugin.shell_executable
        flag = self.settings.cmd_plugin.shell_flag
        timeout = self.settings.cmd_plugin.timeout  # TODO

        self.worker = CmdWorker(cmd, selected_text, shell, flag)
        self.worker.finished.connect(lambda out: self.api.update_preview_content(out))
        self.worker.finished.connect(
            lambda: self.api.set_status("✅ Preview updated.", self.NAME)
        )
        self.worker.error.connect(
            lambda err_msg: self.api.update_preview_content(err_msg)
        )
        self.worker.error.connect(
            lambda err_msg: self.api.set_status(
                f"❌ Preview error: {err_msg[:30]}...", self.NAME
            )
        )
        self.worker.start()

    def execute(self, command: str, selected_text: str) -> Optional[str]:
        cmd = command.lstrip("$").strip()
        if not cmd:
            self.api.set_status("No command to execute", self.NAME)
            return None

        self._cleanup_worker()
        self.api.set_status(f"⌛ Executing...", self.NAME)

        timeout = self.settings.cmd_plugin.timeout
        shell = self.settings.cmd_plugin.shell_executable
        flag = self.settings.cmd_plugin.shell_flag

        try:
            proc = _build_process(cmd, shell, flag)
            stdout, stderr = _communicate(
                proc, selected_text, self.settings.cmd_plugin.timeout
            )
            if proc.returncode != 0:
                err = stderr.strip() or stdout.strip()
                msg = f"Error ({proc.returncode}): {err}"
                self.api.update_preview_content(msg)
                self.api.set_status(msg, self.NAME)
                return None
            result = stdout.strip()
            if stderr.strip():
                result += f"\n[stderr]\n{stderr.strip()}"
            return result
        except subprocess.TimeoutExpired:
            msg = f"Timeout ({timeout}s)"
            self.api.update_preview_content(msg)
            self.api.set_status(msg, self.NAME)
            return None
        except FileNotFoundError:
            msg = f"Shell not found: {shell}"
            self.api.update_preview_content(msg)
            self.api.set_status(msg, self.NAME)
            return None
        except Exception as e:
            import traceback

            traceback.print_exc()
            msg = f"Execution failed: {e}"
            self.api.update_preview_content(msg)
            self.api.set_status(msg, self.NAME)
            return None

    def _cleanup_worker(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.quit()
            if not self.worker.wait(500):
                self.worker.terminate()
                self.worker.wait()
        self.worker = None

    def cleanup(self):
        self._cleanup_worker()
        super().cleanup()

    def register_settings(self, settings_manager):
        section = settings_manager.section("cmd_plugin")
        dshell, dflag = get_default_shell()

        section.add(
            name="timeout",
            default=15,
            type_=int,
            description="Timeout in seconds for execute preview",
        )
        section.add(
            name="shell_executable",
            default=dshell,
            type_=str,
            description="Shell to run commands (uses '-c')",
        )
        section.add(
            name="shell_flag",
            default=dflag,
            type_=str,
            description="Flag to pass a command to the shell (e.g., -c for bash, /c for cmd)",
        )


# TODO: get default shell with default arguments (on windows, no way for "cmd -c 'command'"). make the argument configerable too.
