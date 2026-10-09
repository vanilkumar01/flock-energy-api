from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    portal_base_url: str = "https://urja-ops.flockenergy.tech"
    portal_username: str = ""
    portal_password: str = ""

    # Set these after confirming the actual portal requests in DevTools.
    portal_login_path: str = "login"
    portal_username_field: str = "username"
    portal_password_field: str = "password"
    portal_login_success_marker: str = ""
    portal_auth_cookie_name: str = ""

    # Confirmed from the user's DevTools screenshot:
    # GET /portal/meters/{meter_id}/energy returns JSON with data/timestamp/kwh/kvah.
    portal_energy_path: str = "portal/meters/{meter_id}/energy"

    # The /meters URL was observed, but its browser request returned HTML and
    # did not establish the data endpoint used to populate the 403-meter table.
    # Replace this with the actual data request discovered in DevTools.
    portal_meters_data_path: str = "meters"
    portal_meter_detail_path: str = "portal/meters/{meter_id}"

    request_timeout: float = 15.0
    page_size: int = 20
    max_pages: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
