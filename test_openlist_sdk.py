import sys
from pprint import pprint

from config_loader import get_value, load_config
from openlist_sdk import OpenListAPIError, OpenListClient, OpenListHTTPError


def required_config(config: dict, *keys: str) -> str:
    value = str(get_value(config, *keys, default="") or "").strip()
    if not value:
        raise RuntimeError(f"Missing config value: {'.'.join(keys)}")
    return value


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    config = load_config()
    base_url = required_config(config, "openlist", "base_url")
    username = str(get_value(config, "openlist", "username", default="") or "").strip()
    password = str(get_value(config, "openlist", "password", default="") or "").strip()
    token = str(get_value(config, "openlist", "token", default="") or "").strip()
    use_hash_login = bool(get_value(config, "openlist", "hash_login", default=False))
    test_path = str(get_value(config, "tests", "openlist", "path", default="/") or "/").strip() or "/"

    try:
        with OpenListClient(base_url, token=token or None) as client:
            if not token:
                if not username or not password:
                    raise RuntimeError(
                        "Set openlist.token or both openlist.username and openlist.password in config.yml."
                    )
                if use_hash_login:
                    token = client.login_hashed(username, password)
                    print("Logged in with hashed password.")
                else:
                    token = client.login(username, password)
                    print("Logged in with plain password.")
                print(f"Token: {token}")
            else:
                print("Using token from config.yml.")

            print("\n== Ping ==")
            print(client.ping())

            print("\n== Me ==")
            pprint(client.me())

            print("\n== Public Settings ==")
            pprint(client.public_settings())

            print(f"\n== List Dir: {test_path} ==")
            pprint(client.list_dir(test_path))

            print(f"\n== FS Info: {test_path} ==")
            pprint(client.get_fs_info(test_path))

        return 0
    except (OpenListAPIError, OpenListHTTPError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
