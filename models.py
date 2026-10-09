from pydantic import BaseModel, Field


class Meter(BaseModel):
    meter_id: str
    serial_number: str | None = None
    make: str | None = None
    phase: str | None = None
    status: str | None = None
    dt: str | None = None


class MeterListResponse(BaseModel):
    items: list[Meter]
    total: int


class EnergyRecord(BaseModel):
    timestamp: str
    kwh: float | None = None
    kvah: float | None = None


class EnergyResponse(BaseModel):
    meter_id: str
    items: list[EnergyRecord]
    total: int = Field(ge=0)
