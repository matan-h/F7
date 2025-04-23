from .ai_ollama_plugin import AiOllamaPlugin
from .python_eval_plugin import PythonEvalPlugin
from .base_plugin import PluginInterface

plugins:list[PluginInterface] = [
    AiOllamaPlugin,
    PythonEvalPlugin
    ]