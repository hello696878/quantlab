"""Strict bounded registration envelope; scientific provenance is validated separately."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .identity import canonical

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Adapter = Literal["validation", "calibration", "features", "costs", "decay"]


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=160)
    dataset_version_id: int = Field(strict=True, gt=0)
    dataset_content_hash: Hash
    snapshot: dict[str, Any]

    @field_validator("name")
    @classmethod
    def name_valid(cls, value):
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()

    @field_validator("snapshot")
    @classmethod
    def bounded(cls, value):
        canonical(value)
        return value


class LinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adapter: Adapter
