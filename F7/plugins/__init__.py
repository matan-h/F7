from .ai_ollama_plugin import AiOllamaPlugin
from .base_plugin import PluginInterface
from .cmd_plugin import CmdPlugin
from .python_eval_plugin import PythonEvalPlugin

plugins: list[PluginInterface] = [AiOllamaPlugin, PythonEvalPlugin, CmdPlugin]
