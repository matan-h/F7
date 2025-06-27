import ast
import base64
import binascii
import builtins
import csv
import io
import json
import re
import sys
import tokenize as tokenize
import types
from contextlib import _RedirectStream


# general utils:
class redirect_stdin(
    _RedirectStream
):  # https://github.com/pyodide/pyodide/blob/main/docs/usage/faq.md
    _stream = "stdin"


# python specific
class PyUtils:
    """
    some utilities to make it easy to write and eval python programs
    """

    def __init__(self, text):
        self.text = text

    # user-facing utils
    def lines_map(self, f, src=None):
        return "\n".join(map(f, (src or self.text).split("\n")))

    def grep(self, text, src=None):
        return list(
            filter(lambda x: re.search(text, x), (src or self.text).split("\n"))
        )

    def sub(self, a, b, src=None, count=0):
        return re.sub(a, b, (src or self.text), count=count)

    # eval-facing utils
    def _run_if(self, f):
        ignorelist = [str, format, min, max]
        if f in ignorelist:
            return

        result = None
        if hasattr(f, "__self__") and f.__self__ is not builtins:
            if f.__self__ == self.text:
                try:
                    result = f()
                except Exception:
                    pass
        else:
            try:
                result = f(self.text)
            except Exception:
                pass
        if type(result) is str:
            return result
        else:
            return None

        exec(compile(tree, "<ast>", "exec"), globals_dict)
        return None


def _run_if(f, text):
    ignorelist = [str, format, min, max]
    if f in ignorelist:
        return

    result = None
    if hasattr(f, "__self__") and f.__self__ is not builtins:
        if f.__self__ == text:
            try:
                result = f()
            except Exception:
                pass
    else:
        try:
            result = f(text)
        except Exception:
            pass
    if type(result) is str:
        return result
    else:
        return None


def repr_as_json(obj, text):
    if callable(obj):
        maybe_out = _run_if(obj, text)
        if maybe_out:
            return maybe_out
    if isinstance(obj, str):
        return obj

    if isinstance(obj, bytes):
        return repr(obj)
    # Accept any iterable that is map/filter/generator and convert to list
    if isinstance(obj, (map, filter, types.GeneratorType)):
        obj = list(obj)

    # Check if obj is a list or subclass of list, and all elements are str (like Pipeable list)
    if isinstance(obj, list) and all(isinstance(x, str) for x in obj):
        return "\n".join(obj)

    return repr(obj)


def auto_parse(text):
    parsed = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass
    if not parsed:
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            pass
    if not parsed:
        try:
            __data = list(csv.reader(io.StringIO(text)))
            if (  # sanity check
                all(len(row) > 1 for row in __data)
                and len(__data) > 1
                and not (text.startswith("{") or text.startswith("[]"))
            ):
                parsed = __data
        except csv.Error:
            pass
    if not parsed:
        try:
            decoded = base64.b64decode(text, validate=True).decode("utf-8")
            if decoded.isprintable():
                parsed = decoded
        except (binascii.Error, ValueError, UnicodeDecodeError):
            pass
    return parsed
