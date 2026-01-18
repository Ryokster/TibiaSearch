# If missing: pip install pywin32
from __future__ import annotations

from typing import Tuple

try:
    import pywintypes
    import win32cred
except ImportError:  # pragma: no cover - handled at runtime
    pywintypes = None
    win32cred = None


_NOT_FOUND_CODES = {1168}  # ERROR_NOT_FOUND


class CredentialStoreError(RuntimeError):
    """Base error for credential storage failures."""


class CredentialNotFoundError(CredentialStoreError):
    """Raised when a credential target does not exist."""


def _ensure_win32cred() -> None:
    if win32cred is None or pywintypes is None:
        raise CredentialStoreError("pywin32 is required. Install with: pip install pywin32")


def _is_not_found_error(exc: BaseException) -> bool:
    winerror = getattr(exc, "winerror", None)
    return winerror in _NOT_FOUND_CODES


def save_credentials(target: str, username: str, password: str) -> None:
    """Save or update a generic credential for the given target.

    Passwords are stored as str in the credential blob.
    """
    _ensure_win32cred()
    try:
        credential = {
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": target,
            "UserName": username,
            "CredentialBlob": password,
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }
        win32cred.CredWrite(credential, 0)
    except pywintypes.error as exc:
        raise CredentialStoreError(f"Failed to save credentials for target '{target}': {exc}") from exc


def load_credentials(target: str) -> Tuple[str, str]:
    """Load credentials for the given target.

    Returns (username, password). Passwords are stored as str in the credential blob.
    """
    _ensure_win32cred()
    try:
        credential = win32cred.CredRead(target, win32cred.CRED_TYPE_GENERIC, 0)
    except pywintypes.error as exc:
        if _is_not_found_error(exc):
            raise CredentialNotFoundError(f"Credentials not found for target '{target}'.") from exc
        raise CredentialStoreError(f"Failed to load credentials for target '{target}': {exc}") from exc

    username = str(credential.get("UserName") or "")
    password = credential.get("CredentialBlob") or ""
    if isinstance(password, (bytes, bytearray)):
        try:
            password = bytes(password).decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise CredentialStoreError(f"Failed to decode password for target '{target}'.") from exc
    return username, str(password)


def delete_credentials(target: str) -> None:
    """Delete credentials for the given target."""
    _ensure_win32cred()
    try:
        win32cred.CredDelete(target, win32cred.CRED_TYPE_GENERIC, 0)
    except pywintypes.error as exc:
        if _is_not_found_error(exc):
            raise CredentialNotFoundError(f"Credentials not found for target '{target}'.") from exc
        raise CredentialStoreError(f"Failed to delete credentials for target '{target}': {exc}") from exc


def exists(target: str) -> bool:
    """Return True if credentials exist for the given target."""
    _ensure_win32cred()
    try:
        win32cred.CredRead(target, win32cred.CRED_TYPE_GENERIC, 0)
        return True
    except pywintypes.error as exc:
        if _is_not_found_error(exc):
            return False
        raise CredentialStoreError(f"Failed to check credentials for target '{target}': {exc}") from exc
