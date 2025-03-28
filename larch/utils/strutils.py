#!/usr/bin/env python
"""
utilities for larch
"""
from __future__ import print_function
import re
import sys
import os
import uuid
import hashlib
from base64 import b64encode, b32encode
from random import Random
from packaging import version as pkg_version

from pyshortcuts import gformat, fix_filename, fix_varname, bytes2str, str2bytes


rng = Random()

def strict_ascii(s, replacement='_'):
    """for string to be truly ASCII with all characters below 128"""
    t = bytes(s, 'UTF-8')
    return ''.join([chr(a) if a < 128 else replacement for a in t])


RESERVED_WORDS = ('False', 'None', 'True', 'and', 'as', 'assert', 'async',
                  'await', 'break', 'class', 'continue', 'def', 'del', 'elif',
                  'else', 'end', 'enddef', 'endfor', 'endif', 'endtry',
                  'endwhile', 'eval', 'except', 'exec', 'execfile', 'finally',
                  'for', 'from', 'global', 'group', 'if', 'import', 'in', 'is',
                  'lambda', 'nonlocal', 'not', 'or', 'pass', 'print', 'raise',
                  'return', 'try', 'while', 'with', 'yield')


NAME_MATCH = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$").match
VALID_SNAME_CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'
VALID_NAME_CHARS = '.%s' % VALID_SNAME_CHARS
VALID_CHARS1 = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'

BAD_FILECHARS = ';~,`!%$@$&^?*#:"/|\'\\\t\r\n (){}[]<>'
GOOD_FILECHARS = '_'*len(BAD_FILECHARS)

BAD_VARSCHARS = BAD_FILECHARS + '=+-.'
GOOD_VARSCHARS = '_'*len(BAD_VARSCHARS)

TRANS_FILE = str.maketrans(BAD_FILECHARS, GOOD_FILECHARS)
TRANS_VARS = str.maketrans(BAD_VARSCHARS, GOOD_VARSCHARS)


def PrintExceptErr(err_str, print_trace=True):
    " print error on exceptions"
    print('\n***********************************')
    print(err_str)
    #print 'PrintExceptErr', err_str
    try:
        print('Error: %s' % sys.exc_type)
        etype, evalue, tback = sys.exc_info()
        if print_trace == False:
            tback = ''
        sys.excepthook(etype, evalue, tback)
    except:
        print('Error printing exception error!!')
        raise
    print('***********************************\n')

def strip_comments(sinp, char='#'):
    "find character in a string, skipping over quoted text"
    if sinp.find(char) < 0:
        return sinp
    i = 0
    while i < len(sinp):
        tchar = sinp[i]
        if tchar in ('"',"'"):
            eoc = sinp[i+1:].find(tchar)
            if eoc > 0:
                i = i + eoc
        elif tchar == char:
            return sinp[:i].rstrip()
        i = i + 1
    return sinp

def strip_quotes(t):
    d3, s3, d1, s1 = '"""', "'''", '"', "'"
    if hasattr(t, 'startswith'):
        if ((t.startswith(d3) and t.endswith(d3)) or
            (t.startswith(s3) and t.endswith(s3))):
            t = t[3:-3]
        elif ((t.startswith(d1) and t.endswith(d1)) or
              (t.startswith(s1) and t.endswith(s1))):
            t = t[1:-1]
    return t

def isValidName(name):
    "input is a valid name"
    if name in RESERVED_WORDS:
        return False
    tnam = name[:].lower()
    return NAME_MATCH(tnam) is not None

def fixName(name, allow_dot=True):
    "try to fix string to be a valid name"
    if isValidName(name):
        return name

    if isValidName('_%s' % name):
        return '_%s' % name
    chars = []
    valid_chars = VALID_SNAME_CHARS
    if allow_dot:
        valid_chars = VALID_NAME_CHARS
    for s in name:
        if s not in valid_chars:
            s = '_'
        chars.append(s)
    name = ''.join(chars)
    # last check (name may begin with a number or .)
    if not isValidName(name):
        name = '_%s' % name
    return name

def common_startstring(words):
    """common starting substring for a list of words"""
    out = words[0]
    for tmp in words[1:]:
        i = 0
        for a, b in zip(out, tmp):
            if a == b:
                i += 1
            else:
                out = out[:i]
    return out


def unique_name(name, nlist, max=1000):
    """return name so that is is not in list,
    by appending _1, _2, ... as necessary up to a max suffix

    >>> unique_name('foo', ['bar, 'baz'])
    'foo'

    >>> unique_name('foo', ['foo', 'bar, 'baz'])
    'foo_1'

    """
    out = name
    if name in nlist:
        for i in range(1, max+1):
            out = "%s_%i"  % (name, i)
            if out not in nlist:
                break
    return out


def isNumber(num):
    "input is a number"
    try:
        x = float(num)
        return True
    except (TypeError, ValueError):
        return False

def asfloat(x):
    """try to convert value to float, or fail gracefully"""
    return float(x) if isNumber(x) else x



def isLiteralStr(inp):
    "is a literal string"
    return ((inp.startswith("'") and inp.endswith("'")) or
            (inp.startswith('"') and inp.endswith('"')))


def find_delims(s, delim='"',match=None):
    """find matching delimeters (quotes, braces, etc) in a string.
    returns
      True, index1, index2 if a match is found
      False, index1, len(s) if a match is not found
    the delimiter can be set with the keyword arg delim,
    and the matching delimiter with keyword arg match.

    if match is None (default), match is set to delim.

    >>> find_delims(mystr, delim=":")
    >>> find_delims(mystr, delim='<', match='>')
    """
    esc, dbesc = "\\", "\\\\"
    if match is None:
        match = delim
    j = s.find(delim)
    if j > -1 and s[j:j+len(delim)] == delim:
        p1, p2, k = None, None, j
        while k < j+len(s[j+1:]):
            k = k+1
            if k > 0: p1 = s[k-1:k]
            if k > 1: p2 = s[k-2:k]
            if (s[k:k+len(match)] == match and not (p1 == esc and p2 != dbesc)):
                return True, j, k+len(match)-1
            p1 = s[k:k+1]
    return False, j, len(s)

def version_ge(v1, v2):
    "returns whether version string 1 >= version_string2"
    return pkg_version.parse(v1) >= pkg_version.parse(v2)

def b32hash(s):
    """return a base32 hash of a string"""
    _hash = hashlib.sha256()
    _hash.update(str2bytes(s))
    return bytes2str(b32encode(_hash.digest()))

def b64hash(s):
    """return a base64 hash of a string"""
    _hash = hashlib.sha256()
    _hash.update(str2bytes(s))
    return bytes2str(b64encode(_hash.digest()))

def get_sessionid():
    """get 8 character string encoding machine name and process id"""
    _hash = hashlib.sha256()
    _hash.update(f"{uuid.getnode():d} {os.getpid():d}".encode('ASCII'))
    out = b64encode(_hash.digest()).decode('ASCII')[3:11]
    return out.replace('/', '-').replace('+', '=')


def random_varname(n, rng_seed=None):
    L = 'abcdefghijklmnopqrstuvwxyz0123456789'

    global rng
    if rng_seed is None:
        rng.seed(rng_seed)
    return rng.choice(L[:26]) + ''.join([rng.choice(L) for _ in range(n-1)])


def file2groupname(filename, slen=9, minlen=2, symtable=None, rng_seed=None):
    """create a group name based of filename
    the group name will have a string component of
    length slen followed by a 2 digit number

    Arguments
    ---------
    filename  (str) filename to use
    slen      (int) maximum length of string portion (default 9)
    symtable  (None or larch symbol table) symbol table for
              checking that the group name is unique
    """
    global rng
    if rng_seed is None:
        rng.seed(rng_seed)

    gname = fix_varname(filename).lower().replace('_', '')

    if gname[0] not in 'abcdefghijklmnopqrstuvwxyz':
        gname = rng.choice(['a', 'b', 'c', 'd', 'e', 'f', 'g']) + gname
    if len(gname) < minlen:
        gname = gname + random_varname(minlen-len(gname))

    gname = gname[:slen]
    if symtable is None:
        return gname

    gbase = gname
    scount, count, n = 0, 0, 2
    while hasattr(symtable, gname):
        count += 1
        if count == 100:
            count = 1
            scount += 1
            if scount > 200:
                scount = 0
                n = n + 1
            gbase = gname + random_varname(n)
        gname = f"{gbase}{count:02d}"
    return gname


def break_longstring(s, maxlen=90, n1=20):
    """breaks a long string into a list of smaller strings,
    broken at commas, space, tab, period, or slash

    returns a list of strings, even if length 1"""

    minlen = maxlen-n1

    if len(s) < maxlen:
        return [s]
    out = []
    while len(s) > maxlen:
        icomma = s[minlen:].find(',')
        ispace = s[minlen:].find(' ')
        itab   = s[minlen:].find('\t')
        idot   = s[minlen:].find('.')
        islash = s[minlen:].find('/')
        ibreak =  -1
        if icomma > 0:    ibreak = icomma
        elif ispace > 0:  ibreak = ispace
        elif itab > 0:    ibreak = itab
        elif idot > 0:    ibreak = idot
        elif islash > 0:  ibreak = islash
        if ibreak < 0:
            ibreak = maxlen
        out.append(s[:ibreak+minlen+1])
        s = s[ibreak+minlen+1:]
    out.append(s)
    return out


def array_hash(arr, len=12):
    """generate hash for an array, to tell if an array has changed"""
    return b32hash(''.join([gformat(x, length=16) for x in arr]))[:len].lower()
