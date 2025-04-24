# plugins/python_eval_plugin.py
import contextlib
import io
import sys
import builtins
import rlcompleter
import re

from PyQt6.QtWidgets import QTextEdit, QLabel
from .base_plugin import PluginInterface
from ..python_utils import dotdict,smart_eval,repr_as_json,PyUtils,auto_parse,redirect_stdin
from ..utils import WORD_BOUNDARY_RE


class PythonEvalPlugin(PluginInterface):
    NAME = "Python Evaluator"
    PREFIX = None
    SUFFIX = None
    IS_DEFAULT = True # This handles input if no other plugin matches
    PRIORITY = 90     # Lower than AI prefix plugin
    
    HAS_AUTOCOMPLETE = True # Signal that this plugin provides completions

    def __init__(self, launcher_instance):
        self.eval_context = self._create_context()
        super().__init__(launcher_instance)
    
    def get_status_message(self) -> str:
        return "🐍 Python mode"

    def _evaluate(self, command: str, selected_text: str) -> tuple[str | None, str | None]:
        """Internal helper to evaluate, returning result and error."""
        
        if not command:
            return None, None # No command, no result or error

        try:
            self._update_context(selected_text)

            combined_buf = io.StringIO()
            fake_stdin = io.StringIO(selected_text)
            # security:ignore. this eval command is the intent use of this plugin.
            with redirect_stdin(fake_stdin), \
     contextlib.redirect_stdout(combined_buf), \
     contextlib.redirect_stderr(combined_buf):

                result = smart_eval(command,self.eval_context) # TODO: better eval.
            
            output = combined_buf.getvalue()
            if result is None and output:
                result_str = output
            else:
                result_str =repr_as_json(result,selected_text)
                if output:
                    result_str = output+'\n'+result_str
            return result_str, None
        except Exception as e:
            return None, f"🚨 Error: {str(e)}"

    def update_preview(self, command: str, selected_text: str, preview_widget: QTextEdit, status_widget: QLabel,manual:bool) -> None:
        result_str, error_str = self._evaluate(command, selected_text)

        if error_str:
            preview_widget.setPlainText(error_str)
            preview_widget.show()
        elif result_str is not None:
            preview_widget.setPlainText(result_str)
            preview_widget.show()

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
    
    def _create_context(self):
        ctx = dotdict(builtins.__dict__)
        ctx.space = " "
        ctx.lj = ctx.ljoin = ctx.lnjoin = ctx.linejoin = "\n".join
        ctx.sjoin = ctx.spacejoin = " ".join
        ctx.vjoin = ctx.voidjoin = "".join
        return ctx

    def _update_context(self,text:str):
        ctx = dotdict()
        ctx.raw = ctx.text = text
        ctx.lines = text.split("\n")
        ctx.words = text.split()
        ctx.chars = ctx.characters = list(text)

        str_methods = ["count","split","replace","lower","upper","title","center","format"]
        for method in str_methods:
            ctx[method] = getattr(text,method)
        # shortcuts/logcuts
        ctx.split_on = ctx.split
        # utility functions
        utils = PyUtils(text)
        ctx.lines_map = utils.lines_map
        ctx.grep = utils.grep
        ctx.lines_map = utils.lines_map
        # auto parse
        try:
            auto = auto_parse(text) or text
        except Exception:
            ctx.parse_error = sys.exc_info()
            # do not block user on error
            auto = text

        ctx._ = ctx.auto = auto

        self.eval_context.update(ctx)

    def update_completions(self, command: str, cursor_pos: int) -> None:
        """Generate Python completions and update the launcher's completer."""
        if not self.launcher.completer or not self.launcher.completion_model:
             # Should not happen if launcher initializes correctly
             print("Warning: Launcher completer not available.", file=sys.stderr)
             return

        text_before_cursor = command[:cursor_pos]

        # --- Determine the text fragment to complete ---
        # Use regex to find the last sequence of word characters/dots before cursor
        match = WORD_BOUNDARY_RE.search(text_before_cursor)
        if match:
            prefix = match.group(1)
            # Use rlcompleter logic
            # Need a *new* completer instance each time? Or update namespace?
            # rlcompleter seems stateful with its matches, safer to recreate.
            completer = rlcompleter.Completer(self.eval_context)
            completer.use_main_ns = False
            completer.use_readline = False

            completions = []
            state = 0
            while True:
                # rlcompleter needs the *fragment* and state index
                comp = completer.complete(prefix, state)
                if comp is None:
                    break
                completions.append(comp)
                state += 1

            # Update the model *before* setting the prefix
            self.launcher.completion_model.setStringList(completions)

            # Tell the QCompleter which part of the input it's completing
            # This ensures it filters correctly and knows what to replace
            self.launcher.completer.setCompletionPrefix(prefix)
            if not completions and prefix: # If we had a prefix but found nothing
             self.launcher.completer.popup().hide()
            elif not prefix: # If there wasn't even a prefix to search for
                self.launcher.completer.popup().hide()

        else:
            return
    def register_settings(self, settings):
        return super().register_settings(settings) # TODO