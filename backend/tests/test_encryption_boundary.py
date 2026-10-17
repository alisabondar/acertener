import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
ALLOWED = {APP_DIR / "crypto", APP_DIR / "db" / "types.py"}
FORBIDDEN = re.compile(r"^\s*(from|import)\s+cryptography\b|\.(encrypt|decrypt)\(", re.MULTILINE)


def _allowed(path: Path) -> bool:
    return any(path == a or a in path.parents for a in ALLOWED)


def test_only_the_crypto_module_and_column_types_touch_encryption() -> None:
    offenders = [
        str(path.relative_to(APP_DIR))
        for path in APP_DIR.rglob("*.py")
        if not _allowed(path) and FORBIDDEN.search(path.read_text())
    ]

    assert offenders == []
