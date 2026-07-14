from __future__ import annotations

import os
import re
import secrets
import time
from ctypes import (
    POINTER,
    Structure,
    WinDLL,
    byref,
    c_void_p,
    cast,
    create_string_buffer,
    sizeof,
)
from ctypes.wintypes import BOOL, BYTE, DWORD, HANDLE, LPCWSTR, LPWSTR, WORD
from enum import StrEnum, unique
from pathlib import Path
from typing import Callable, ClassVar, Final, override

from pydantic import BaseModel, ConfigDict

from app.operations.windows_dpapi import DpapiError, DpapiPurpose, protect_for_current_user, unprotect_for_current_user

# CurrentUser-scoped DPAPI store for OpenAI-compatible provider credentials.
#
# Ciphertext lives under a SID-scoped ProgramData root so only the account that wrote
# it (via DPAPI CurrentUser scope) can ever unprotect it. Plaintext key material is
# never logged, returned as a model field, or persisted outside the DPAPI ciphertext
# blob written here. Uses the dedicated `DpapiPurpose.PROVIDER_CREDENTIAL` purpose so
# this ciphertext can never cross-decrypt against credential-rotation bundle entropy.

_advapi32 = WinDLL("advapi32", use_last_error=True)
_kernel32 = WinDLL("kernel32", use_last_error=True)

SE_FILE_OBJECT: Final = 1
OWNER_SECURITY_INFORMATION: Final = 0x00000001
DACL_SECURITY_INFORMATION: Final = 0x00000004
ERROR_SUCCESS: Final = 0
TOKEN_QUERY: Final = 0x0008
_TOKEN_USER_CLASS: Final = 1
FILE_ATTRIBUTE_REPARSE_POINT: Final = 0x400
INVALID_FILE_ATTRIBUTES: Final = 0xFFFFFFFF
GENERIC_READ: Final = 0x80000000
FILE_SHARE_READ: Final = 0x1
FILE_SHARE_WRITE: Final = 0x2
OPEN_EXISTING: Final = 3
FILE_FLAG_BACKUP_SEMANTICS: Final = 0x02000000
FILE_FLAG_OPEN_REPARSE_POINT: Final = 0x00200000
_ACCESS_ALLOWED_ACE_TYPE: Final = 0
_ACL_SIZE_INFORMATION_CLASS: Final = 2
_WELL_KNOWN_SAFE_SID_SUFFIXES: Final = ("S-1-5-18", "S-1-5-32-544")  # LocalSystem, BUILTIN\Administrators

_advapi32.GetNamedSecurityInfoW.argtypes = [LPCWSTR, DWORD, DWORD, POINTER(c_void_p), POINTER(c_void_p), POINTER(c_void_p), POINTER(c_void_p), POINTER(c_void_p)]
_advapi32.GetNamedSecurityInfoW.restype = DWORD
_advapi32.ConvertSidToStringSidW.argtypes = [c_void_p, POINTER(LPWSTR)]
_advapi32.ConvertSidToStringSidW.restype = BOOL
_advapi32.GetAclInformation.argtypes = [c_void_p, c_void_p, DWORD, DWORD]
_advapi32.GetAclInformation.restype = BOOL
_advapi32.GetAce.argtypes = [c_void_p, DWORD, POINTER(c_void_p)]
_advapi32.GetAce.restype = BOOL
_advapi32.OpenProcessToken.argtypes = [HANDLE, DWORD, POINTER(HANDLE)]
_advapi32.OpenProcessToken.restype = BOOL
_advapi32.GetTokenInformation.argtypes = [HANDLE, DWORD, c_void_p, DWORD, POINTER(DWORD)]
_advapi32.GetTokenInformation.restype = BOOL
_kernel32.GetCurrentProcess.restype = HANDLE
_kernel32.CloseHandle.argtypes = [HANDLE]
_kernel32.CloseHandle.restype = BOOL
_kernel32.LocalFree.argtypes = [c_void_p]
_kernel32.LocalFree.restype = c_void_p
_kernel32.GetFileAttributesW.argtypes = [LPCWSTR]
_kernel32.GetFileAttributesW.restype = DWORD
_kernel32.CreateFileW.argtypes = [LPCWSTR, DWORD, DWORD, c_void_p, DWORD, DWORD, HANDLE]
_kernel32.CreateFileW.restype = HANDLE
_kernel32.GetFileInformationByHandle.argtypes = [HANDLE, c_void_p]
_kernel32.GetFileInformationByHandle.restype = BOOL


class _FILETIME(Structure):
    _fields_ = [("dwLowDateTime", DWORD), ("dwHighDateTime", DWORD)]


class _BY_HANDLE_FILE_INFORMATION(Structure):
    _fields_ = [
        ("dwFileAttributes", DWORD),
        ("ftCreationTime", _FILETIME),
        ("ftLastAccessTime", _FILETIME),
        ("ftLastWriteTime", _FILETIME),
        ("dwVolumeSerialNumber", DWORD),
        ("nFileSizeHigh", DWORD),
        ("nFileSizeLow", DWORD),
        ("nNumberOfLinks", DWORD),
        ("nFileIndexHigh", DWORD),
        ("nFileIndexLow", DWORD),
    ]


class _ACE_HEADER(Structure):
    _fields_ = [("AceType", BYTE), ("AceFlags", BYTE), ("AceSize", WORD)]


class _ACL_SIZE_INFORMATION(Structure):
    _fields_ = [("AceCount", DWORD), ("AclBytesInUse", DWORD), ("AclBytesFree", DWORD)]


class _SID_AND_ATTRIBUTES(Structure):
    _fields_ = [("Sid", c_void_p), ("Attributes", DWORD)]


class _TOKEN_USER(Structure):
    _fields_ = [("User", _SID_AND_ATTRIBUTES)]


@unique
class ProviderCredentialStoreErrorCode(StrEnum):
    SID_RESOLUTION_FAILED = "sid-resolution-failed"
    ROOT_UNREADABLE = "root-unreadable"
    ROOT_REPARSE_POINT = "root-reparse-point"
    ROOT_OWNER_MISMATCH = "root-owner-mismatch"
    ROOT_DACL_MISSING = "root-dacl-missing"
    ROOT_DACL_TOO_BROAD = "root-dacl-too-broad"
    ROOT_SECURITY_QUERY_FAILED = "root-security-query-failed"
    FILE_REPARSE_POINT = "file-reparse-point"
    FILE_HARDLINKED = "file-hardlinked"
    FILE_UNREADABLE = "file-unreadable"
    ENVELOPE_CORRUPT = "envelope-corrupt"
    BINDING_VERSION_IMMUTABLE = "binding-version-immutable"
    STAGE_WRITE_FAILED = "stage-write-failed"
    CREDENTIAL_NOT_FOUND = "credential-not-found"
    INVALID_REF = "invalid-ref"


class ProviderCredentialStoreError(RuntimeError):
    code: ProviderCredentialStoreErrorCode

    def __init__(self, code: ProviderCredentialStoreErrorCode) -> None:
        self.code = code
        super().__init__(code.value)

    @override
    def __str__(self) -> str:
        return self.code.value


class ProviderCredentialEnvelope(BaseModel):
    """Safe, non-secret metadata about a stored credential. Never carries plaintext or ciphertext."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    credential_ref: str
    credential_binding_version: int
    created_at: float


_ENVELOPE_MAGIC: Final = b"AEROONE-PCV1\n"
_REF_RE: Final = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _safe_ref(credential_ref: str) -> str:
    if not _REF_RE.match(credential_ref):
        raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.INVALID_REF)
    return credential_ref


def _sid_ptr_to_string(sid_ptr: int) -> str:
    if not sid_ptr:
        raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.SID_RESOLUTION_FAILED)
    out = LPWSTR()
    if not _advapi32.ConvertSidToStringSidW(c_void_p(sid_ptr), byref(out)):
        raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.SID_RESOLUTION_FAILED)
    try:
        value = out.value
        if value is None:
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.SID_RESOLUTION_FAILED)
        return value
    finally:
        _ = _kernel32.LocalFree(out)


def _current_user_sid_string() -> str:
    process = _kernel32.GetCurrentProcess()
    token = HANDLE()
    if not _advapi32.OpenProcessToken(process, TOKEN_QUERY, byref(token)):
        raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.SID_RESOLUTION_FAILED)
    try:
        size = DWORD(0)
        _ = _advapi32.GetTokenInformation(token, _TOKEN_USER_CLASS, None, 0, byref(size))
        buf = create_string_buffer(size.value)
        if not _advapi32.GetTokenInformation(token, _TOKEN_USER_CLASS, buf, size, byref(size)):
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.SID_RESOLUTION_FAILED)
        token_user = cast(buf, POINTER(_TOKEN_USER)).contents
        sid_ptr = token_user.User.Sid
        return _sid_ptr_to_string(sid_ptr or 0)
    finally:
        _ = _kernel32.CloseHandle(token)


def _validate_dacl(dacl_ptr: c_void_p, expected_owner_sid: str) -> None:
    if not dacl_ptr.value:
        raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ROOT_DACL_MISSING)
    size_info = _ACL_SIZE_INFORMATION()
    if not _advapi32.GetAclInformation(dacl_ptr, byref(size_info), sizeof(size_info), _ACL_SIZE_INFORMATION_CLASS):
        raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ROOT_SECURITY_QUERY_FAILED)
    allowed = {expected_owner_sid, *_WELL_KNOWN_SAFE_SID_SUFFIXES}
    for index in range(size_info.AceCount):
        ace_ptr = c_void_p()
        if not _advapi32.GetAce(dacl_ptr, index, byref(ace_ptr)):
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ROOT_SECURITY_QUERY_FAILED)
        header = cast(ace_ptr, POINTER(_ACE_HEADER)).contents
        if header.AceType != _ACCESS_ALLOWED_ACE_TYPE:
            continue
        trustee_sid = _sid_ptr_to_string((ace_ptr.value or 0) + 8)
        if trustee_sid not in allowed:
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ROOT_DACL_TOO_BROAD)


def _validate_directory_security(path: Path, expected_owner_sid: str) -> None:
    raw = str(path)
    attrs = _kernel32.GetFileAttributesW(raw)
    if attrs == INVALID_FILE_ATTRIBUTES:
        raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ROOT_UNREADABLE)
    if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
        raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ROOT_REPARSE_POINT)

    owner_sid_ptr = c_void_p()
    dacl_ptr = c_void_p()
    sd_ptr = c_void_p()
    status = _advapi32.GetNamedSecurityInfoW(
        raw,
        SE_FILE_OBJECT,
        OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
        byref(owner_sid_ptr),
        None,
        byref(dacl_ptr),
        None,
        byref(sd_ptr),
    )
    if status != ERROR_SUCCESS:
        raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ROOT_SECURITY_QUERY_FAILED)
    try:
        owner_sid = _sid_ptr_to_string(owner_sid_ptr.value or 0)
        if owner_sid not in {expected_owner_sid, *_WELL_KNOWN_SAFE_SID_SUFFIXES}:
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ROOT_OWNER_MISMATCH)
        _validate_dacl(dacl_ptr, expected_owner_sid)
    finally:
        _ = _kernel32.LocalFree(sd_ptr)


def _reject_reparse_or_hardlink_file(path: Path) -> None:
    raw = str(path)
    attrs = _kernel32.GetFileAttributesW(raw)
    if attrs == INVALID_FILE_ATTRIBUTES:
        return
    if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
        raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.FILE_REPARSE_POINT)
    handle = _kernel32.CreateFileW(
        raw,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if not handle or handle == HANDLE(-1).value:
        raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.FILE_UNREADABLE)
    try:
        info = _BY_HANDLE_FILE_INFORMATION()
        if not _kernel32.GetFileInformationByHandle(handle, byref(info)):
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.FILE_UNREADABLE)
        if info.nNumberOfLinks > 1:
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.FILE_HARDLINKED)
    finally:
        _ = _kernel32.CloseHandle(handle)


class ProviderCredentialStore:
    """Atomic stage/promote/delete DPAPI credential store, SID-scoped under ProgramData.

    `root_dir` is the injected temp seam tests use to avoid touching the real machine
    ProgramData tree. `unsafe_skip_host_validation` additionally bypasses the owner/
    DACL/reparse/hardlink host security checks on that overridden root — it is only
    honored when `root_dir` is also explicitly supplied, so production code (which
    never sets `root_dir`) always validates host security and can never take this
    path by accident.
    """

    def __init__(
        self,
        *,
        root_dir: Path | None = None,
        sid_provider: Callable[[], str] | None = None,
        unsafe_skip_host_validation: bool = False,
    ) -> None:
        if unsafe_skip_host_validation and root_dir is None:
            raise ValueError("unsafe_skip_host_validation requires an explicit root_dir override")
        self._root_override = root_dir
        self._sid_provider = sid_provider or _current_user_sid_string
        self._unsafe_skip_host_validation = unsafe_skip_host_validation

    @property
    def root(self) -> Path:
        if self._root_override is not None:
            return self._root_override
        program_data = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
        return program_data / "AeroOne" / "provider-credentials" / self._sid_provider()

    def _prepare_root(self) -> Path:
        root = self.root
        root.mkdir(parents=True, exist_ok=True)
        if self._root_override is None or not self._unsafe_skip_host_validation:
            _validate_directory_security(root, self._sid_provider())
        return root

    def _blob_path(self, credential_ref: str) -> Path:
        return self._prepare_root() / f"{_safe_ref(credential_ref)}.dpapi"

    def store_credential(
        self,
        credential_ref: str,
        plaintext: bytes,
        *,
        binding_version: int,
        existing_binding_version: int | None,
    ) -> ProviderCredentialEnvelope:
        """Atomically stage+promote ciphertext for `credential_ref`.

        `credential_binding_version` is immutable once set for a given ref: if a blob
        already exists, both `existing_binding_version` and the requested
        `binding_version` must match the persisted value exactly or the write is
        rejected — callers rotate by minting a brand new `credential_ref`, never by
        silently overwriting the binding of an existing one. Callers (the config
        service) allocate `binding_version`; the store never invents one, so the
        returned envelope's binding is exactly what the caller asked to persist.
        """
        target = self._blob_path(credential_ref)
        if target.exists():
            _reject_reparse_or_hardlink_file(target)
            current = self._read_envelope(credential_ref)
            if existing_binding_version != current.credential_binding_version or binding_version != current.credential_binding_version:
                raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.BINDING_VERSION_IMMUTABLE)
        else:
            if existing_binding_version is not None:
                raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.CREDENTIAL_NOT_FOUND)

        ciphertext = protect_for_current_user(plaintext, DpapiPurpose.PROVIDER_CREDENTIAL)
        created_at = time.time()
        payload = _ENVELOPE_MAGIC + str(binding_version).encode("ascii") + b"\n" + str(created_at).encode("ascii") + b"\n" + ciphertext

        staging = target.with_suffix(target.suffix + f".staging-{secrets.token_hex(8)}")
        try:
            staging.write_bytes(payload)
            _reject_reparse_or_hardlink_file(staging)
            os.replace(staging, target)  # atomic promote on NTFS
        except OSError as exc:
            if staging.exists():
                staging.unlink(missing_ok=True)
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.STAGE_WRITE_FAILED) from exc
        return ProviderCredentialEnvelope(credential_ref=credential_ref, credential_binding_version=binding_version, created_at=created_at)

    def _read_envelope(self, credential_ref: str) -> ProviderCredentialEnvelope:
        path = self._blob_path(credential_ref)
        if not path.exists():
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.CREDENTIAL_NOT_FOUND)
        _reject_reparse_or_hardlink_file(path)
        raw = path.read_bytes()
        if not raw.startswith(_ENVELOPE_MAGIC):
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ENVELOPE_CORRUPT)
        rest = raw[len(_ENVELOPE_MAGIC):]
        try:
            binding_version_bytes, created_at_bytes, _ciphertext = rest.split(b"\n", 2)
            binding_version = int(binding_version_bytes.decode("ascii"))
            created_at = float(created_at_bytes.decode("ascii"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ENVELOPE_CORRUPT) from exc
        return ProviderCredentialEnvelope(credential_ref=credential_ref, credential_binding_version=binding_version, created_at=created_at)

    def get_envelope(self, credential_ref: str) -> ProviderCredentialEnvelope | None:
        try:
            return self._read_envelope(credential_ref)
        except ProviderCredentialStoreError as exc:
            if exc.code == ProviderCredentialStoreErrorCode.CREDENTIAL_NOT_FOUND:
                return None
            raise

    def load_plaintext(self, credential_ref: str) -> bytes:
        """Returns raw secret bytes for immediate in-process use (e.g. building an
        Authorization header right before an egress call). Callers MUST NOT log, repr,
        or persist the return value."""
        path = self._blob_path(credential_ref)
        if not path.exists():
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.CREDENTIAL_NOT_FOUND)
        _reject_reparse_or_hardlink_file(path)
        raw = path.read_bytes()
        if not raw.startswith(_ENVELOPE_MAGIC):
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ENVELOPE_CORRUPT)
        rest = raw[len(_ENVELOPE_MAGIC):]
        try:
            _binding_version_bytes, _created_at_bytes, ciphertext = rest.split(b"\n", 2)
        except ValueError as exc:
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ENVELOPE_CORRUPT) from exc
        try:
            return unprotect_for_current_user(ciphertext, DpapiPurpose.PROVIDER_CREDENTIAL)
        except DpapiError as exc:
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.ENVELOPE_CORRUPT) from exc

    def delete_credential(self, credential_ref: str) -> None:
        path = self._blob_path(credential_ref)
        if not path.exists():
            return
        _reject_reparse_or_hardlink_file(path)
        try:
            path.unlink()
        except OSError as exc:
            raise ProviderCredentialStoreError(ProviderCredentialStoreErrorCode.STAGE_WRITE_FAILED) from exc
