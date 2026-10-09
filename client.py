import logging
import re
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)


class UrjaPortalError(Exception):
    """Base error for communication with the legacy portal."""


class PortalAuthenticationError(UrjaPortalError):
    """Authentication could not be verified."""


class UrjaPortalClient:
    """
    Session-aware adapter for Urja Meter Ops.

    Verified from the supplied DevTools screenshots:
      GET /portal/meters/{meter_id}/energy -> JSON containing timestamps,
      kwh and kvah fields.

    The portal login route and meter-list data API were not established by
    the supplied screenshots. Configure them in .env after verifying them.
    """

    def __init__(self, config=settings):
        self.config = config
        self.base_url = config.portal_base_url.rstrip("/") + "/"
        self.client = httpx.Client(
            timeout=config.request_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "UrjaMeterOpsAPI/1.0",
                "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            },
        )
        self.authenticated = False
        self.closed = False

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    @staticmethod
    def clean_text(value: Any) -> str | None:
        if value is None:
            return None
        value = re.sub(r"\\s+", " ", str(value)).strip()
        if value.upper() in {"", "-", "N/A", "NA", "NULL", "NONE"}:
            return None
        return value

    @staticmethod
    def clean_number(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        value = str(value).strip().replace(",", "")
        if not re.fullmatch(r"[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)", value):
            return None
        try:
            return float(value)
        except (ValueError, OverflowError):
            return None

    @staticmethod
    def _field(obj: dict, *names: str):
        normalized = {
            str(k).strip().lower().replace(" ", "_"): v
            for k, v in obj.items()
        }
        for name in names:
            key = name.lower().replace(" ", "_")
            if key in normalized:
                return normalized[key]
        return None

    def login(self) -> bool:
        """
        Generic form-login implementation.

        IMPORTANT: this must be adapted to the actual login request.
        It assumes the login form is on the base page and POSTs to the
        configured login path with configured field names.
        """
        if self.closed:
            raise UrjaPortalError("Client is closed")
        if not self.config.portal_username or not self.config.portal_password:
            raise PortalAuthenticationError(
                "Set PORTAL_USERNAME and PORTAL_PASSWORD in .env."
            )

        login_url = self._url(self.config.portal_login_path)
        try:
            page = self.client.get(self.base_url)
            page.raise_for_status()
            soup = BeautifulSoup(page.text, "html.parser")

            # Preserve hidden form values, including a CSRF token if present.
            payload = {}
            form = soup.find("form")
            if form:
                for field in form.find_all("input"):
                    name = field.get("name")
                    if name and field.get("type", "").lower() == "hidden":
                        payload[name] = field.get("value", "")
                action = form.get("action")
                if action:
                    login_url = urljoin(str(page.url), action)

            payload[self.config.portal_username_field] = self.config.portal_username
            payload[self.config.portal_password_field] = self.config.portal_password

            response = self.client.post(login_url, data=payload)
            response.raise_for_status()

            marker = self.config.portal_login_success_marker
            cookie_name = self.config.portal_auth_cookie_name
            if marker:
                success = marker in response.text
            elif cookie_name:
                success = any(
                    cookie.name == cookie_name
                    for cookie in self.client.cookies.jar
                )
            else:
                # Heuristic only; configure a verified marker/cookie for
                # reliable success detection.
                soup_after = BeautifulSoup(response.text, "html.parser")
                password_form_remains = (
                    soup_after.find("input", {"type": "password"}) is not None
                )
                current_path = urlparse(str(response.url)).path.rstrip("/")
                configured_path = urlparse(login_url).path.rstrip("/")
                success = not (
                    password_form_remains and current_path == configured_path
                )

            if not success:
                raise PortalAuthenticationError(
                    "Login response was received, but success was not verified. "
                    "Check the real login route, field names, CSRF flow and success marker."
                )
            self.authenticated = True
            return True
        except PortalAuthenticationError:
            self.authenticated = False
            raise
        except httpx.HTTPError as exc:
            self.authenticated = False
            raise PortalAuthenticationError("Portal login request failed.") from exc

    def _looks_like_login(self, response: httpx.Response) -> bool:
        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type:
            return False
        path = urlparse(str(response.url)).path.lower()
        login_path = urlparse(self._url(self.config.portal_login_path)).path.lower()
        if path.rstrip("/") == login_path.rstrip("/"):
            return True
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.find("input", {"type": "password"}) is not None

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        if self.closed:
            raise UrjaPortalError("Client is closed")
        for attempt in range(2):
            if not self.authenticated:
                self.login()
            try:
                response = self.client.request(method, self._url(path), **kwargs)
                if response.status_code in (401, 403) or self._looks_like_login(response):
                    self.authenticated = False
                    if attempt == 0:
                        continue
                    raise PortalAuthenticationError(
                        "Portal session expired or access was denied."
                    )
                response.raise_for_status()
                return response
            except PortalAuthenticationError:
                raise
            except httpx.HTTPError as exc:
                raise UrjaPortalError("Portal request failed.") from exc
        raise UrjaPortalError("Portal request could not be completed.")

    def _get_data(self, path: str, params: dict | None = None):
        response = self._request("GET", path, params=params)
        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type:
            try:
                return response.json()
            except ValueError as exc:
                raise UrjaPortalError("Portal returned invalid JSON.") from exc
        return response.text

    def _normalize_meter(self, raw: dict) -> dict:
        return {
            "meter_id": self.clean_text(self._field(
                raw, "meter_id", "meter", "id", "meterId", "meter_number"
            )),
            "serial_number": self.clean_text(self._field(
                raw, "serial_number", "serial", "serial_no", "serialNumber"
            )),
            "make": self.clean_text(self._field(raw, "make", "manufacturer", "brand")),
            "phase": self.clean_text(self._field(raw, "phase", "phase_type", "phaseType")),
            "status": self.clean_text(self._field(raw, "status", "installation_status")),
            "dt": self.clean_text(self._field(raw, "dt", "distribution_transformer")),
        }

    def _parse_meter_html(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        result = []
        # The portal's visible table headings are METER, SERIAL, MAKE,
        # PHASE, STATUS, DT. This parser assumes that column order.
        for row in soup.select("table tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            values = [self.clean_text(c.get_text(" ", strip=True)) for c in cells]
            meter_id = values[0]
            if not meter_id:
                link = row.find("a", href=True)
                if link:
                    match = re.search(r"/meters/([^/?#]+)", link["href"])
                    meter_id = match.group(1) if match else None
            if not meter_id:
                continue
            result.append({
                "meter_id": meter_id,
                "serial_number": values[1] if len(values) > 1 else None,
                "make": values[2] if len(values) > 2 else None,
                "phase": values[3] if len(values) > 3 else None,
                "status": values[4] if len(values) > 4 else None,
                "dt": values[5] if len(values) > 5 else None,
            })
        return result

    @staticmethod
    def _extract_records(data, keys: tuple[str, ...]) -> list:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in keys:
                value = data.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    nested = UrjaPortalClient._extract_records(
                        value, keys + ("items", "results", "records")
                    )
                    if nested:
                        return nested
            # Some responses wrap an array in data.data.
            nested_data = data.get("data")
            if isinstance(nested_data, list):
                return nested_data
        return []

    def get_meters(self) -> dict:
        """
        Fetch meter records. Configure PORTAL_METERS_DATA_PATH and pagination
        parameter names to match the actual data request seen in DevTools.

        The visible /meters page is confirmed, but its actual data-loading
        endpoint and query parameter names are not yet verified.
        """
        all_items = []
        seen_ids = set()
        page_size = max(1, self.config.page_size)

        for page in range(1, self.config.max_pages + 1):
            # Common query pattern; change if DevTools shows other parameters.
            data = self._get_data(
                self.config.portal_meters_data_path,
                params={"page": page, "limit": page_size},
            )

            if isinstance(data, str):
                records = self._parse_meter_html(data)
                # HTML page may be a shell that does not contain populated rows.
                if not records and page == 1:
                    raise UrjaPortalError(
                        "The meters URL returned HTML without meter rows. "
                        "Find the request that supplies the 403-meter table in "
                        "DevTools and set PORTAL_METERS_DATA_PATH to that endpoint."
                    )
            else:
                records = self._extract_records(
                    data, ("items", "meters", "results", "records", "data")
                )
                if not records and isinstance(data, dict):
                    # A single object is not accepted as a list response.
                    raise UrjaPortalError(
                        "Could not identify the meter array in the JSON response."
                    )

            if not records:
                break

            new_count = 0
            for raw in records:
                if not isinstance(raw, dict):
                    continue
                meter = self._normalize_meter(raw)
                meter_id = meter.get("meter_id")
                if not meter_id or meter_id in seen_ids:
                    continue
                seen_ids.add(meter_id)
                all_items.append(meter)
                new_count += 1

            # Stop when server returns fewer than requested, or no new records.
            if len(records) < page_size or new_count == 0:
                break

        return {"items": all_items, "total": len(all_items)}

    def get_meter_details(self, meter_id: str) -> dict:
        if not meter_id or not meter_id.strip():
            raise ValueError("meter_id must not be empty")
        path = self.config.portal_meter_detail_path.format(
            meter_id=quote(meter_id, safe="")
        )
        data = self._get_data(path)
        if isinstance(data, str):
            soup = BeautifulSoup(data, "html.parser")
            serial = soup.select_one("#meter-serial")
            status = soup.select_one(".status-value")
            # Fall back to a label/value layout if selectors differ.
            result = {
                "meter_id": meter_id,
                "serial_number": serial.get_text(strip=True) if serial else None,
                "status": status.get_text(strip=True) if status else None,
                "make": None,
                "phase": None,
                "dt": None,
            }
        elif isinstance(data, dict):
            raw = data.get("meter", data.get("data", data))
            if not isinstance(raw, dict):
                raise UrjaPortalError("Unexpected meter-detail JSON structure.")
            result = self._normalize_meter(raw)
            result["meter_id"] = result["meter_id"] or meter_id
        else:
            raise UrjaPortalError("Unsupported meter-detail response format.")
        return result

    def get_energy(self, meter_id: str) -> dict:
        """Read the observed /portal/meters/{id}/energy JSON endpoint."""
        if not meter_id or not meter_id.strip():
            raise ValueError("meter_id must not be empty")
        path = self.config.portal_energy_path.format(
            meter_id=quote(meter_id, safe="")
        )
        data = self._get_data(path)

        # Observed Preview shape: {data: {timestamp: ..., data: [{timestamp,kwh,kvah}]}}
        payload = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                records = payload["data"]
            elif "timestamp" in payload:
                records = [payload]
            else:
                records = self._extract_records(
                    payload, ("items", "records", "readings", "energy")
                )
        elif isinstance(payload, list):
            records = payload
        else:
            records = []

        items = []
        for raw in records:
            if not isinstance(raw, dict):
                continue
            items.append({
                "timestamp": self.clean_text(raw.get("timestamp")) or "",
                "kwh": self.clean_number(raw.get("kwh")),
                "kvah": self.clean_number(raw.get("kvah")),
            })
        return {"meter_id": meter_id, "items": items, "total": len(items)}

    # Compatibility method for the route name used in the assignment.
    def get_consumption(self, meter_id: str) -> dict:
        return self.get_energy(meter_id)

    def get_hierarchy(self):
        # Endpoint not verified from supplied evidence; configure before use.
        path = self.config.portal_hierarchy_path if hasattr(
            self.config, "portal_hierarchy_path"
        ) else "hierarchy"
        return self._get_data(path)

    def close(self):
        if not self.closed:
            self.client.close()
            self.authenticated = False
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
