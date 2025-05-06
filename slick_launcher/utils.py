import re
class dotdict(dict): # see https://stackoverflow.com/a/23689767
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


WORD_BOUNDARY_RE = re.compile(r"([a-zA-Z0-9_.]+)$")
