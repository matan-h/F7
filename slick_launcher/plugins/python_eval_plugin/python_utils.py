import csv,io,base64,json,ast,sys,builtins,re
from contextlib import _RedirectStream
# general utils:
class redirect_stdin(_RedirectStream): # https://github.com/pyodide/pyodide/blob/main/docs/usage/faq.md
    _stream = "stdin"


# python specific
class PyUtils:
    """
    some utilities to make it easy to write and eval python programs
    """
    def __init__(self,text):
        self.text = text
    # user-facing utils
    def lines_map(self,f):
        return "\n".join(map(f, self.text.split("\n")))
    def grep(self,text):
        return list(filter(lambda x: re.search(text, x), self.text.split("\n")))
    def sub(self,a, b, count=0):
        return re.sub(a, b, self.text, count=count)

    
    # eval-facing utils
    def _run_if(self,f):
        ignorelist = [str,format,min,max]
        if f in ignorelist:
            return
        
        result = None
        if hasattr(f, '__self__') and f.__self__ is not builtins:
            if f.__self__==self.text:
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
    


def smart_eval(code,globals_dict=None): # inspired by pyodide CodeRunner : https://github.com/pyodide/pyodide/blob/4fbbbedc09496c6968086d69aadba75398718b13/src/py/_pyodide/_base.py#L172
    if globals_dict is None:
        globals_dict = {}

    try:
        tree = ast.parse(code, mode='exec',filename="<main>")
    except SyntaxError:
        raise
    if not tree.body:
        return None
    last_stmt = tree.body[-1]
    if isinstance(last_stmt, ast.Expr):
        # globals_dict = {}
        if len(tree.body) > 1:
            exec(compile(ast.Module(body=tree.body[:-1], type_ignores=[]), '<ast>', 'exec'), globals_dict)
        return eval(compile(ast.Expression(last_stmt.value), '<ast>', 'eval'), globals_dict)
    else:
        exec(compile(tree, '<ast>', 'exec'), globals_dict)
        return None
def _run_if(f,text):
    ignorelist = [str,format,min,max]
    if f in ignorelist:
        return
    
    result = None
    if hasattr(f, '__self__') and f.__self__ is not builtins:
        if f.__self__==text:
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

def repr_as_json(obj,text):   
    if callable(obj):
        maybe_out = _run_if(obj,text)
        if maybe_out: return maybe_out
    if type(obj) is str:
        return obj
    if type(obj) is bytes:
        return repr(obj)
    if type(obj) is list and len(obj) < 8 and  all(type(x) is str for x in obj):
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
            if ( # sanity check
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
        except (base64.binascii.Error, ValueError,UnicodeDecodeError):
            pass
    return parsed
