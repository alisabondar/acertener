import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def test_only_the_gateway_can_reach_an_ai_provider() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "importlinter.cli", "--no-cache"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
