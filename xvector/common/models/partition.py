from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class PartitionLoadReleaseRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "collectionName": "demo",
                    "partitionNames": ["p1"],
                    "dbName": "default",
                }
            ]
        },
    )

    collectionName: str
    dbName: str = "default"
    partitionNames: list[str] | None = None
    partitionName: str | None = None

    __example__ = {
        "collectionName": "demo",
        "partitionNames": ["p1"],
        "dbName": "default",
    }

    @model_validator(mode="after")
    def _require_partition(self) -> PartitionLoadReleaseRequest:
        if not self.partitionNames and not self.partitionName:
            raise ValueError("partitionNames or partitionName required")
        return self

    def model_dump(self, **kwargs):  # type: ignore[override]
        data = super().model_dump(**kwargs)
        if not data.get("partitionNames") and data.get("partitionName"):
            data["partitionNames"] = [data["partitionName"]]
        return data
