import base64
import csv
import functools
import io
import math
from collections import Counter

from ...utils import dotdict

"""
the idea of this file is to offer the nice to have functions to parse,analysis,and manipulate data, with support both python notion and cyberchef notion
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
        return result

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

    return bytes(a ^ b for a, b in zip(s, k))


ctx.xor = xor


### data formats
def parse_tsv(text: str, key_field=0, delimiter="\t"):

    rows = list(csv.DictReader(io.StringIO(text), delimiter=delimiter))
    if key_field is None:
        return rows

    if isinstance(key_field, int):
        fieldnames = rows[0].keys()
        key_field = list(fieldnames)[key_field]
    return {row[key_field]: row for row in rows}


ctx.parse_tsv = ctx.from_tsv = parse_tsv


def to_tsv(rows: dict | list, delimiter="\t") -> str:
    if isinstance(rows, dict):
        rows = list(rows.values())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys(), delimiter=delimiter)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


ctx.to_tsv = to_tsv
