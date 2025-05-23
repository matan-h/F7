import base64
import functools
import math
from collections import Counter

from ...utils import dotdict

"""
the idea of this file is to offer the must-have options, support both python notion and cyberchef notion
"""
ctx = dotdict()


def byteMethod(func):
    """
    Wrap a bytes-in/bytes-out function so it also accepts str
    and returns str whenever possible.
    """

    @functools.wraps(func)
    def inner(data, *args, **kwargs):
        if isinstance(data, str):
            data = data.encode()

        result = func(data, *args, **kwargs)

        if isinstance(result, bytes):
            try:
                text = result.decode()
                if text.isprintable():
                    return text
            except UnicodeDecodeError:
                pass

    return inner


### string base
bases = ["64", "32", "16", "85"]

for base in bases:
    encode = byteMethod(getattr(base64, f"b{base}encode"))
    decode = byteMethod(getattr(base64, f"b{base}decode"))
    ctx[f"b{base}encode"] = encode
    ctx[f"b{base}decode"] = decode

    ctx[f"base{base}encode"] = encode
    ctx[f"base{base}decode"] = decode

    ctx[f"to_base{base}"] = encode
    ctx[f"from_base{base}"] = decode

ctx.urlsafe_b64encode = byteMethod(base64.urlsafe_b64encode)
ctx.urlsafe_b64decode = byteMethod(base64.urlsafe_b64decode)


### entropy
def entropy(s: str) -> float:
    """
    Calculate the Shannon entropy of a string in bits.
    """
    # Count occurrences of each character
    counts = Counter(s)
    n = len(s)
    # Compute probability for each character
    probs = (count / n for count in counts.values())
    # Sum -p * log2(p)
    return -sum(p * math.log2(p) for p in probs)


ctx.entropy = ctx.calculate_entropy = entropy


### string math


@byteMethod
def xor(s: bytes, k: int | str, encoding="utf-8"):
    if isinstance(k, int):
        k = bytes([k])
    else:
        k = k.encode(encoding)

    k = (k * len(s))[: len(s)]

    return bytes(a ^ b for a, b in zip(s, k)).hex()


ctx.xor = xor
