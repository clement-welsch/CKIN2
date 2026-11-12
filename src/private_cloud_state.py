"""Local secret storage: Windows account-bound DPAPI, or mode 0600 on POSIX."""

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tempfile


def windows_protect(content, *, decrypt=False):
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(content)
    source = Blob(len(content), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise OSError("Windows could not protect or unlock the Google authorization")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


def save_private(path, value):
    content = json.dumps(value).encode("utf-8")
    content = b"DPAPI\n" + windows_protect(content) if os.name == "nt" else b"LOCAL\n" + content
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_private(path):
    content = Path(path).read_bytes()
    if content.startswith(b"DPAPI\n") and os.name == "nt":
        content = windows_protect(content[6:], decrypt=True)
    elif content.startswith(b"LOCAL\n") and os.name != "nt":
        content = content[6:]
    else:
        raise ValueError("Google authorization belongs to another system; connect again")
    return json.loads(content)
