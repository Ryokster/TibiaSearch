# If missing: pip install pywin32
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

# --- IMPORTANT: ensure project root is on sys.path ---
ROOT = Path(__file__).resolve().parents[1]  # ...\TibiaSearch
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.credential_store import (
    CredentialNotFoundError,
    CredentialStoreError,
    delete_credentials,
    load_credentials,
    save_credentials,
)


def _cmd_set(args: argparse.Namespace) -> int:
    password = getpass.getpass("Password: ")
    save_credentials(args.target, args.username, password)
    return 0


def _cmd_get(args: argparse.Namespace) -> int:
    username, password = load_credentials(args.target)
    if args.show_password:
        print(username)
        print(password)
    else:
        print(username)
    return 0


def _cmd_delete(args: argparse.Namespace) -> int:
    delete_credentials(args.target)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Windows Credential Manager entries.")
    subparsers = parser.add_subparsers(dest="command")

    set_parser = subparsers.add_parser("set", help="Create or update credentials.")
    set_parser.add_argument("--target", required=True)
    set_parser.add_argument("--username", required=True)
    set_parser.set_defaults(func=_cmd_set)

    get_parser = subparsers.add_parser("get", help="Fetch credentials.")
    get_parser.add_argument("--target", required=True)
    get_parser.add_argument("--show-password", action="store_true")
    get_parser.set_defaults(func=_cmd_get)

    delete_parser = subparsers.add_parser("delete", help="Delete credentials.")
    delete_parser.add_argument("--target", required=True)
    delete_parser.set_defaults(func=_cmd_delete)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except CredentialNotFoundError:
        return 1
    except CredentialStoreError:
        return 2


if __name__ == "__main__":
    sys.exit(main())
