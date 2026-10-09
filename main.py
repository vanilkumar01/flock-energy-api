from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from app.client import (
    UrjaPortalClient,
    UrjaPortalError,
    PortalAuthenticationError,
)
from app.config import settings
from app.models import Meter, MeterListResponse, EnergyResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.portal = UrjaPortalClient(settings)
    yield
    app.state.portal.close()


app = FastAPI(
    title="Flock Energy - Urja Meter Ops API",
    version="1.0.0",
    description=(
        "REST adapter for the legacy Urja Meter Ops portal. "
        "Portal routes must be verified/configured locally."
    ),
    lifespan=lifespan,
)


def portal_or_http_error(exc: Exception):
    if isinstance(exc, PortalAuthenticationError):
        raise HTTPException(status_code=502, detail="Legacy portal authentication failed")
    if isinstance(exc, UrjaPortalError):
        raise HTTPException(status_code=502, detail=str(exc))
    raise HTTPException(status_code=502, detail="Legacy portal request failed")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/auth/login")
def login(request: Request):
    try:
        request.app.state.portal.login()
        return {"authenticated": True}
    except Exception as exc:
        portal_or_http_error(exc)


@app.get("/api/v1/meters", response_model=MeterListResponse)
def list_meters(request: Request):
    try:
        return request.app.state.portal.get_meters()
    except Exception as exc:
        portal_or_http_error(exc)


@app.get("/api/v1/meters/{meter_id}", response_model=Meter)
def get_meter(meter_id: str, request: Request):
    try:
        data = request.app.state.portal.get_meter_details(meter_id)
        if not data.get("meter_id"):
            raise HTTPException(status_code=404, detail="Meter not found")
        return data
    except HTTPException:
        raise
    except Exception as exc:
        portal_or_http_error(exc)


@app.get(
    "/api/v1/meters/{meter_id}/consumption",
    response_model=EnergyResponse,
)
def get_consumption(meter_id: str, request: Request):
    try:
        return request.app.state.portal.get_energy(meter_id)
    except Exception as exc:
        portal_or_http_error(exc)


@app.get("/api/v1/hierarchy")
def get_hierarchy(request: Request):
    try:
        return request.app.state.portal.get_hierarchy()
    except Exception as exc:
        portal_or_http_error(exc)
