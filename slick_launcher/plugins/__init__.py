from .base_plugin import PluginInterface

from .ai_ollama_plugin import AiOllamaPlugin
from .python_eval_plugin import PythonEvalPlugin
from .cmd_plugin import CmdPlugin

plugins:list[PluginInterface] = [
    AiOllamaPlugin,
    PythonEvalPlugin,
    CmdPlugin
    ]