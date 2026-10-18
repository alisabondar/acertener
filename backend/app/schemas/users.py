import uuid

from pydantic import BaseModel, ConfigDict

from app.auth.permissions import Permission


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    role: str
    credential: str | None


class MeOut(UserOut):
    permissions: list[Permission]
