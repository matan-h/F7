import functools
import re

class dotdict(dict): # see https://stackoverflow.com/a/23689767
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

def remove_none(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if not isinstance(result, dict):
            # If the function doesn’t return a dict, just pass it through
            raise ValueError(f"remove_none: result '{result}' is not a dict.")
        # Filter out None values
        return {k: v for k, v in result.items() if v is not None}
    return wrapper

WORD_BOUNDARY_RE = re.compile(r"([a-zA-Z0-9_.]+)$")
