import collections
import functools
import hashlib
import io
import json
import math
import os
import random
import re
import string
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from string import *
from urllib.parse import quote, quote_plus, unquote, unquote_plus, urlparse, urlsplit

from string_utils import (
    asciify,
    booleanize,
    camel_case_to_snake,
    prettify,
    random_string,
    reverse,
    roman_decode,
    roman_encode,
    secure_random_hex,
    shuffle,
    snake_case_to_camel,
    strip_html,
    strip_margin,
    uuid,
    words_count,
)

# simple shortcuts/longcuts
## string_utils
snake = snake_case = camel_case_to_snake
camel = camel_case = snake_case_to_camel

# join
space = " "
lj = ljoin = lnjoin = linejoin = "\n".join
sjoin = spacejoin = " ".join
vjoin = voidjoin = "".join
# url
urldecode = unquote_plus
urlencode = quote_plus
static_globals = globals()
