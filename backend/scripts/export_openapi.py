"""Write the API contract the frontend builds and tests against.

- frontend/src/api/openapi.json: the OpenAPI schema, for the generated types
- frontend/src/test/role-permissions.json: each role's permissions, for the test fixtures

Run from backend/:  uv run python -m scripts.export_openapi
CI regenerates both and fails if a committed copy differs.
"""

import json
from pathlib import Path

from app.auth.permissions import ADMIN, FRONT_DESK, MATRIX, NURSE, PROVIDER
from app.config import Settings
from app.main import create_app

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
OPENAPI = FRONTEND / "src/api/openapi.json"
ROLE_PERMISSIONS = FRONTEND / "src/test/role-permissions.json"


def role_permissions() -> dict[str, list[str]]:
    return {
        role: sorted(p.value for p, roles in MATRIX.items() if role in roles)
        for role in (PROVIDER, NURSE, FRONT_DESK, ADMIN)
    }


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {path.relative_to(FRONTEND.parent)}")


def main() -> None:
    # The schema doesn't depend on configuration; a placeholder URL avoids needing .env.
    settings = Settings(_env_file=None, database_url="postgresql+asyncpg://schema@localhost/schema")
    write_json(OPENAPI, create_app(settings).openapi())
    write_json(ROLE_PERMISSIONS, role_permissions())


if __name__ == "__main__":
    main()
