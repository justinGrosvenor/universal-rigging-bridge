from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ConversionRequest(BaseModel):
    source_uri: str = Field(description="S3 URI or absolute local path to the rigged asset")
    output_uri: Optional[str] = Field(
        default=None,
        description="Optional S3 URI where the converted GLB should be stored",
    )
    collection: str = Field(
        default="",
        description="Optional source collection override for the converter",
    )
    include_extra_bones: bool = Field(default=False)
    t_pose: bool = Field(default=True)
    export_textures: bool = Field(default=True)
    remove_fingers: bool = Field(default=True)

    @field_validator("source_uri")
    @classmethod
    def validate_source_uri(cls, value: str) -> str:
        if not value:
            msg = "source_uri must not be empty"
            raise ValueError(msg)
        return value


class ConversionArtifact(BaseModel):
    uri: str
    content_type: str


class ConversionResponse(BaseModel):
    status: str
    artifacts: list[ConversionArtifact]
    logs: Optional[list[str]] = None
