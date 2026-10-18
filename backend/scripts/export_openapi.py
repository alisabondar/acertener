"""Write the API's OpenAPI schema for the frontend's generated types.

Run from backend/:  uv run python -m scripts.export_openapi
CI regenerates it and fails if the committed copy differs (the type-drift check).
"""

import json
from pathlib import Path

from app.config import Settings
from app.main import create_app

OUTPUT = Path(__file__).resolve().parents[2] / "frontend/src/api/openapi.json"


def main() -> None:
    # The schema doesn't depend on configuration; a placeholder URL avoids needing .env.
    settings = Settings(_env_file=None, database_url="postgresql+asyncpg://schema@localhost/schema")
    schema = create_app(settings).openapi()
    OUTPUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {OUTPUT.relative_to(OUTPUT.parents[3])}")


if __name__ == "__main__":
    main()
