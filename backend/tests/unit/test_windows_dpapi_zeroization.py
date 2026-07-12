from __future__ import annotations

from ctypes import POINTER, c_void_p, cast, memset
from ctypes.wintypes import BYTE

import pytest

from app.operations import windows_dpapi


class _TrackedKernel32:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def RtlZeroMemory(self, pointer: c_void_p, size: int) -> None:
        self.events.append("zero")
        _ = memset(pointer, 0, size)

    def LocalFree(self, pointer: c_void_p) -> int:
        self.events.append("free")
        return 0


@pytest.mark.parametrize("copy_fails", (False, True))
def test_native_dpapi_buffer_is_zeroed_before_free(
    monkeypatch: pytest.MonkeyPatch,
    copy_fails: bool,
) -> None:
    plaintext = b"synthetic-native-plaintext"
    native = (BYTE * len(plaintext)).from_buffer_copy(plaintext)
    blob = windows_dpapi._DataBlob(len(plaintext), cast(native, POINTER(BYTE)))
    events: list[str] = []
    native_api = _TrackedKernel32(events)
    monkeypatch.setattr(windows_dpapi, "_kernel32", native_api)
    monkeypatch.setattr(windows_dpapi, "_ntdll", native_api)
    if copy_fails:

        def fail_copy(_pointer: object, _size: int) -> bytes:
            raise RuntimeError("synthetic-copy-failure")

        monkeypatch.setattr(windows_dpapi, "string_at", fail_copy)
        with pytest.raises(RuntimeError, match="synthetic-copy-failure"):
            windows_dpapi._copy_and_free(blob)
    else:
        assert windows_dpapi._copy_and_free(blob) == plaintext

    assert bytes(native) == b"\0" * len(plaintext)
    assert events == ["zero", "free"]
