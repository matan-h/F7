import subprocess
from typing import Optional

from ..types import pyqtSignal
from .base_plugin import PluginInterface, Thread


class CmdWorker(Thread):  # Inherit from the aliased BaseThread
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, cmd, input_text):
        super().__init__()
        self.cmd = cmd
        self.input_text = input_text
        self._stopped = False

    def run(self):
        try:
            # Ensure shell=True is used cautiously. Consider alternatives if possible.
            proc = subprocess.Popen(
                self.cmd,
                shell=True,  # SECURITY WARNING: Ensure cmd is trusted or sanitized
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # Input text can be None or empty string, handle appropriately
            input_to_send = self.input_text if self.input_text is not None else ""

            # Communicate handles sending stdin data and waiting for process completion
            stdout, stderr = proc.communicate(input=input_to_send)

            if self._stopped:  # Check if stopped during communicate
                self.error.emit("Command cancelled by plugin")
                # Try to terminate if process might still be running after communicate attempt
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=1)  # Give it a moment to terminate
                    if proc.poll() is None:
                        proc.kill()  # Force kill if terminate didn't work
                return

            if proc.returncode != 0:
                error_msg = f"Command failed (exit code {proc.returncode})"
                if stderr and stderr.strip():
                    error_msg += f": {stderr.strip()}"
                elif stdout and stdout.strip():  # Sometimes errors go to stdout
                    error_msg += f": {stdout.strip()}"
                self.error.emit(error_msg)
            else:
                output = stdout if stdout else ""
                if (
                    stderr and stderr.strip()
                ):  # Include stderr even on success if it has content
                    output += f"\n[stderr]\n{stderr.strip()}"
                self.finished.emit(output.strip())
        except FileNotFoundError:
            self.error.emit(
                f"Execution error: Command or shell not found for '{self.cmd.split()[0]}'. Ensure it's in your PATH."
            )
        except Exception as e:
            import traceback

            # traceback.print_exc() # For debugging, consider logging instead of printing directly
            self.error.emit(f"Execution error: {str(e)}")

    def stop(self):
        self._stopped = True
        # Note: Stopping a running subprocess from another thread is complex.
        # Popen.terminate() or Popen.kill() would typically be called here if
        # the process object (`proc`) was accessible.
        # Since `run` handles the process, this flag is mostly for `communicate`.


class CmdPlugin(PluginInterface):
    NAME = "CMD"
    PREFIX = "$"
    IS_DEFAULT = False
    PRIORITY = 10
    # HAS_AUTOCOMPLETE = False # Default from base, explicitly set if needed

    def __init__(self, api_instance, settings):  # Corrected type hint
        super().__init__(api_instance, settings)
        self.worker: Optional[CmdWorker] = None
        self.current_cmd_for_preview = (
            ""  # To avoid re-running identical preview commands
        )
        self.auto_preview_mode = False  # Determined by '$$'

    def get_status_message(self) -> str:
        if self.auto_preview_mode:
            return "CMD Auto-Preview Active ($$). Use with caution!"
        return "CMD Mode: Use '$' (preview with Ctrl+Enter) or '$$' (auto-preview)."

    def update_preview(self, command: str, selected_text: str, manual: bool) -> None:
        self.auto_preview_mode = command.startswith("$$")

        # Determine the actual command part, stripping one or two '$'
        if self.auto_preview_mode:  # $$
            cmd_part = command[2:].strip()
        elif command.startswith("$"):  # $
            cmd_part = command[1:].strip()

        # Conditions to update preview:
        # 1. Manual trigger (Ctrl+Enter)
        # 2. Auto-preview mode is on
        should_run_preview = manual or self.auto_preview_mode

        if not should_run_preview:
            # If not auto-previewing and not manual, clear preview if command changed
            # or if there's no command part.
            if not cmd_part or cmd_part != self.current_cmd_for_preview:
                self.api.update_preview_content("")  # Clear and hide
                self._cleanup_worker()  # Stop any ongoing preview worker
                self.current_cmd_for_preview = cmd_part  # Update even if not running
            self.api.reset_status()  # Reset to default CMD status
            return

        if not cmd_part:  # No actual command to run
            self.api.update_preview_content("")  # Clear and hide
            self.api.set_status("Enter a command after '$' or '$$'", self.NAME)
            self._cleanup_worker()
            self.current_cmd_for_preview = ""
            return

        # Avoid re-running the same preview command unnecessarily unless forced manually
        if (
            cmd_part == self.current_cmd_for_preview
            and not manual
            and self.worker
            and self.worker.isRunning()
        ):
            return  # Already running or just finished for this command

        self.current_cmd_for_preview = cmd_part
        self._cleanup_worker()  # Stop previous worker if any

        self.api.update_preview_content("Executing command for preview...")
        self.api.set_status("⏳ Running command for preview...", self.NAME)

        self.worker = CmdWorker(cmd_part, selected_text)
        # Connect signals to lambda functions that call API methods
        self.worker.finished.connect(
            lambda output: self.api.update_preview_content(output)
        )
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
        # Command here is already stripped of the initial '$' or '$$' by the core logic
        # if PREFIX matching is used. If not, we might need to strip it here.
        # Assuming 'command' is the part after the prefix.
        actual_command_to_run = command.strip()
        if not actual_command_to_run:
            self.api.set_status("No command to execute.", self.NAME)
            return None  # Nothing to execute

        self._cleanup_worker()  # Ensure any preview worker is stopped

        self.api.set_status(f"⌛ Executing: {actual_command_to_run[:30]}...", self.NAME)

        # For execute, we typically want a synchronous result if possible,
        # or the plugin handles closing. CmdWorker is async.
        # If we want to return the string directly for the API to handle copy & close:
        try:
            proc = subprocess.Popen(
                actual_command_to_run,
                shell=True,  # SECURITY: Be very careful with shell=True
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            input_to_send = selected_text if selected_text is not None else ""
            stdout, stderr = proc.communicate(
                input=input_to_send, timeout=15
            )  # Added timeout

            if proc.returncode != 0:
                error_message = f"CMD Error (code {proc.returncode})"
                if stderr and stderr.strip():
                    error_message += f": {stderr.strip()}"
                elif stdout and stdout.strip():
                    error_message += f": {stdout.strip()}"  # Error might be on stdout
                self.api.set_status(error_message, self.NAME)
                # Show error in preview as well, then launcher stays open
                self.api.update_preview_content(error_message)
                return None  # Stay open to show error
            else:
                result_output = stdout.strip()
                if stderr and stderr.strip():  # Append stderr if any, even on success
                    result_output += f"\n\n[stderr output:]\n{stderr.strip()}"
                # API will copy this result and close the launcher
                return result_output

        except subprocess.TimeoutExpired:
            self.api.set_status(
                f"Timeout executing: {actual_command_to_run}", self.NAME
            )
            self.api.update_preview_content(
                f"Error: Command '{actual_command_to_run}' timed out after 15 seconds."
            )
            return None  # Stay open
        except FileNotFoundError:
            err_fnf = f"Execution error: Command or shell not found for '{actual_command_to_run.split()[0]}'. Ensure it's in your PATH."
            self.api.set_status(err_fnf, self.NAME)
            self.api.update_preview_content(err_fnf)
            return None
        except Exception as e:
            self.api.set_status(f"Failed to run CMD: {e}", self.NAME)
            self.api.update_preview_content(f"Error executing command:\n{str(e)}")
            return None  # Stay open to show error

    def _cleanup_worker(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()  # Signal the worker to stop
            self.worker.quit()  # Politely ask QThread to finish
            if not self.worker.wait(500):  # Wait a bit
                # print(f"{self.NAME} Plugin: Worker thread did not stop gracefully, terminating.")
                self.worker.terminate()  # Forcefully terminate
                self.worker.wait()  # Wait for termination to complete
        self.worker = None

    def cleanup(self) -> None:
        """Called when the application is shutting down or plugin is unloaded."""
        self._cleanup_worker()
        super().cleanup()  # Call base class cleanup if it does anything

    def register_settings(self, settings_manager) -> None:
        """Register CMD plugin specific settings if any."""
        # Example:
        # settings_manager.add_setting(
        #     key="cmd_plugin_default_timeout",
        #     default_value=15,
        #     value_type=int,
        #     description="Default timeout in seconds for CMD plugin commands.",
        #     category="Plugins" # Optional: categorize settings
        # )
        # TODO: add default shell exe settings (bash -c, fish -c,etc.)
        pass  # No specific settings for CMD plugin in this example
