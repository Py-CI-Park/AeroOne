from __future__ import annotations

from ctypes import (
    POINTER,
    Structure,
    WinDLL,
    byref,
    c_size_t,
    c_void_p,
    get_last_error,
    memset,
    string_at,
)
from ctypes.wintypes import BOOL, BYTE, DWORD, HLOCAL, LPCWSTR
from enum import StrEnum, unique
import hashlib
from typing import Final, cast, final, override


_CRYPTPROTECT_UI_FORBIDDEN: Final = 0x01
_ENTROPY_PREFIX: Final = b"AeroOne.CredentialRotation.v1:"


@unique
class DpapiPurpose(StrEnum):
    CREDENTIAL_BUNDLE = "credential-bundle"
    DATABASE_RECOVERY = "database-recovery"
    ROTATION_JOURNAL = "rotation-journal"
    PENDING_ROOT_ENVIRONMENT = "pending-root-environment"
    PENDING_BACKEND_ENVIRONMENT = "pending-backend-environment"
    BOOTSTRAP_MARKER = "rotation-bootstrap-marker"
    TEST_PAYLOAD = "test-payload"


@final
class _DataBlob(Structure):
    _fields_ = [
        ("size", DWORD),
        ("data", POINTER(BYTE)),
    ]


class DpapiError(Exception):
    operation: str
    error_code: int

    def __init__(self, operation: str, error_code: int) -> None:
        self.operation = operation
        self.error_code = error_code
        super().__init__(operation, error_code)

    @override
    def __str__(self) -> str:
        return f"DPAPI {self.operation} failed with Windows error {self.error_code}"


_crypt32 = WinDLL("crypt32", use_last_error=True)
_kernel32 = WinDLL("kernel32", use_last_error=True)
_ntdll = WinDLL("ntdll", use_last_error=True)
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
_ntdll.RtlZeroMemory.argtypes = [c_void_p, c_size_t]
_ntdll.RtlZeroMemory.restype = None


def _zero_and_free(output: _DataBlob) -> None:
    data = cast(HLOCAL, output.data)
    size = cast(int, output.size)
    try:
        if data and size > 0:
            _ntdll.RtlZeroMemory(data, size)
    finally:
        if data:
            _ = cast(HLOCAL, _kernel32.LocalFree(data))


def _copy_and_free(output: _DataBlob) -> bytes:
    data = cast(HLOCAL, output.data)
    size = cast(int, output.size)
    try:
        return string_at(data, size)
    finally:
        _zero_and_free(output)


def _entropy(purpose: DpapiPurpose) -> bytes:
    return hashlib.sha256(_ENTROPY_PREFIX + purpose.value.encode("ascii")).digest()


def protect_for_current_user(payload: bytes, purpose: DpapiPurpose) -> bytes:
    entropy = _entropy(purpose)
    input_buffer = (BYTE * len(payload)).from_buffer_copy(payload)
    entropy_buffer = (BYTE * len(entropy)).from_buffer_copy(entropy)
    input_blob = _DataBlob(len(payload), input_buffer)
    entropy_blob = _DataBlob(len(entropy), entropy_buffer)
    output_blob = _DataBlob()
    try:
        succeeded = bool(
            cast(
                int,
                _crypt32.CryptProtectData(
                    byref(input_blob),
                    purpose.value,
                    byref(entropy_blob),
                    None,
                    None,
                    _CRYPTPROTECT_UI_FORBIDDEN,
                    byref(output_blob),
                ),
            )
        )
        error_code = get_last_error() if not succeeded else 0
    finally:
        _ = memset(input_buffer, 0, len(payload))
        _ = memset(entropy_buffer, 0, len(entropy))
    if not succeeded:
        _zero_and_free(output_blob)
        raise DpapiError(operation="protect", error_code=error_code)
    return _copy_and_free(output_blob)


def unprotect_for_current_user(payload: bytes, purpose: DpapiPurpose) -> bytes:
    entropy = _entropy(purpose)
    input_buffer = (BYTE * len(payload)).from_buffer_copy(payload)
    entropy_buffer = (BYTE * len(entropy)).from_buffer_copy(entropy)
    input_blob = _DataBlob(len(payload), input_buffer)
    entropy_blob = _DataBlob(len(entropy), entropy_buffer)
    output_blob = _DataBlob()
    try:
        succeeded = bool(
            cast(
                int,
                _crypt32.CryptUnprotectData(
                    byref(input_blob),
                    None,
                    byref(entropy_blob),
                    None,
                    None,
                    _CRYPTPROTECT_UI_FORBIDDEN,
                    byref(output_blob),
                ),
            )
        )
        error_code = get_last_error() if not succeeded else 0
    finally:
        _ = memset(input_buffer, 0, len(payload))
        _ = memset(entropy_buffer, 0, len(entropy))
    if not succeeded:
        _zero_and_free(output_blob)
        raise DpapiError(operation="unprotect", error_code=error_code)
    return _copy_and_free(output_blob)
