from __future__ import annotations

from ctypes import POINTER, Structure, WinDLL, byref, get_last_error, string_at
from ctypes.wintypes import BOOL, BYTE, DWORD, HLOCAL, LPCWSTR
from dataclasses import dataclass
from typing import Final


_CRYPTPROTECT_UI_FORBIDDEN: Final = 0x01


class _DataBlob(Structure):
    _fields_ = [('size', DWORD), ('data', POINTER(BYTE))]


@dataclass(frozen=True, slots=True)
class DpapiError(Exception):
    operation: str
    error_code: int

    def __str__(self) -> str:
        return f'DPAPI {self.operation} failed with Windows error {self.error_code}'


_crypt32 = WinDLL('crypt32', use_last_error=True)
_kernel32 = WinDLL('kernel32', use_last_error=True)
_crypt32.CryptProtectData.argtypes = [
    POINTER(_DataBlob),
    LPCWSTR,
    POINTER(_DataBlob),
    POINTER(BYTE),
    POINTER(BYTE),
    DWORD,
    POINTER(_DataBlob),
]
_crypt32.CryptProtectData.restype = BOOL
_crypt32.CryptUnprotectData.argtypes = [
    POINTER(_DataBlob),
    POINTER(LPCWSTR),
    POINTER(_DataBlob),
    POINTER(BYTE),
    POINTER(BYTE),
    DWORD,
    POINTER(_DataBlob),
]
_crypt32.CryptUnprotectData.restype = BOOL
_kernel32.LocalFree.argtypes = [HLOCAL]
_kernel32.LocalFree.restype = HLOCAL


def _copy_and_free(output: _DataBlob) -> bytes:
    try:
        return string_at(output.data, output.size)
    finally:
        _kernel32.LocalFree(output.data)


def protect_for_current_user(payload: bytes) -> bytes:
    input_buffer = (BYTE * len(payload)).from_buffer_copy(payload)
    input_blob = _DataBlob(len(payload), input_buffer)
    output_blob = _DataBlob()
    succeeded = _crypt32.CryptProtectData(
        byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        byref(output_blob),
    )
    del input_buffer
    if not succeeded:
        raise DpapiError(operation='protect', error_code=get_last_error())
    return _copy_and_free(output_blob)


def unprotect_for_current_user(payload: bytes) -> bytes:
    input_buffer = (BYTE * len(payload)).from_buffer_copy(payload)
    input_blob = _DataBlob(len(payload), input_buffer)
    output_blob = _DataBlob()
    succeeded = _crypt32.CryptUnprotectData(
        byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        byref(output_blob),
    )
    del input_buffer
    if not succeeded:
        raise DpapiError(operation='unprotect', error_code=get_last_error())
    return _copy_and_free(output_blob)
