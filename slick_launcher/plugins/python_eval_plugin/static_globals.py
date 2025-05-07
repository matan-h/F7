import os,sys

import string, re, json, random, math, io, string, collections, hashlib
from datetime import datetime, date, timedelta
from string import *
from collections import Counter, defaultdict
from urllib.parse import unquote, unquote_plus, urlsplit, quote, quote_plus,urlparse

from string_utils import camel_case_to_snake,snake_case_to_camel,reverse,shuffle,strip_html,prettify,asciify,asciify,booleanize,strip_margin,roman_encode,roman_decode,uuid,random_string,secure_random_hex,words_count

# shortcuts/longcuts
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
