"""Create the encryption keys in KEYS_DIR if they're missing; existing keys are left alone.

Run once before the API starts (Compose's keys-init service):  python -m scripts.init_keys
"""

from app.config import get_settings
from app.crypto import load_or_create_keys


def main() -> None:
    load_or_create_keys(get_settings().keys_dir)
    print("Encryption keys ready.")


if __name__ == "__main__":
    main()
