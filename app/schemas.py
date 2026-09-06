from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal


class ClientConfigUpdate(BaseModel):
    rate_per_second: float = Field(..., gt=0)
    burst_size: int = Field(..., gt=0)
    mode: Literal["token_bucket", "sliding_window"]

    @field_validator("rate_per_second")
    @classmethod
    def rate_must_be_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("rate_per_second must be positive")
        return value


class ClientConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_key: str
    rate_per_second: float
    burst_size: int
    mode: Literal["token_bucket", "sliding_window"]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RateLimitResponse(BaseModel):
    client_key: str
    allowed: bool
    limit: int
    remaining: int
    reset: float
    mode: Literal["token_bucket", "sliding_window"]
    timestamp: float
