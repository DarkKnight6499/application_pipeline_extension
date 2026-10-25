"""Portal logins kept in the Windows Credential Manager (never in repo or data files), one entry per host."""
import argparse
import getpass
import sys

# Config
SERVICE_PREFIX = "application-pipeline:"
INDEX_ACCOUNT = "__accounts__"


def _backend(backend=None):
    if backend is not None:
        return backend
    import keyring
    return keyring


def _service(host):
    return SERVICE_PREFIX + str(host).strip().lower()


def save_login(host, username, password, backend=None):
    if not str(host).strip() or not username or not password:
        raise ValueError("Host, username and password are all required.")
    store = _backend(backend)
    service = _service(host)
    store.set_password(service, INDEX_ACCOUNT, username)
    store.set_password(service, username, password)


def get_login(host, backend=None):
    """Returns (username, password) for the host, or None."""
    store = _backend(backend)
    service = _service(host)
    username = store.get_password(service, INDEX_ACCOUNT)
    password = store.get_password(service, username) if username else None
    return (username, password) if password else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="Store a login; the password is prompted, never passed on the command line.")
    add.add_argument("host")
    add.add_argument("username")
    show = sub.add_parser("show", help="Show the stored username for a host (never the password).")
    show.add_argument("host")
    args = parser.parse_args(argv)
    if args.command == "add":
        save_login(args.host, args.username, getpass.getpass("Password: "))
        print("Stored in Windows Credential Manager.")
        return 0
    login = get_login(args.host)
    print(login[0] if login else "No login stored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
