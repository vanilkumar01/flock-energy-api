Urja Meter Ops REST API
A FastAPI adapter for the legacy Urja Meter Ops portal.
Verified from the supplied DevTools evidence
- Energy request: GET /portal/meters/{meter_id}/energy
- Example status: 200 OK
- Energy response includes timestamp, kwh, and kvah.
- The meter page visually shows 403 total meters and columns Meter, Serial, Make, Phase, Status, DT.
- The browser's /meters request was observed, but the supplied response showed an empty HTML page; this does not establish the data endpoint that populates the table.
- Login route, login form fields, and pagination parameter names remain unverified.
Setup (Windows PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
Edit .env with your authorized portal credentials and the verified routes/fields.
Run
uvicorn app.main:app --reload
- Health: http://127.0.0.1:8000/health
- Swagger: http://127.0.0.1:8000/docs
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json
Endpoints
- POST /api/v1/auth/login
- GET /api/v1/meters
- GET /api/v1/meters/{meter_id}
- GET /api/v1/meters/{meter_id}/consumption
- GET /api/v1/hierarchy
Important configuration work still required
1. Inspect the login request in DevTools and set PORTAL_LOGIN_PATH, field names, and success detection.
2. Find the request whose response contains the meter records. Set PORTAL_METERS_DATA_PATH to that data endpoint.
3. Inspect page 2's request and set the actual pagination parameter names in app/client.py if they differ from page and limit.
4. Inspect the meter-detail request before relying on the default detail path.
5. Confirm how session expiry is represented and verify reauthentication works.
The client uses a configurable form-login approximation. It cannot be considered production-ready until the real authentication flow and meter-list request are verified.
Test
pytest -v
Example energy response
{
  "meter_id": "J100000",
  "items": [
    {
      "timestamp": "23/06/2026 23:30",
      "kwh": 48438.74,
      "kvah": 50000.1
    }
  ],
  "total": 1
}
Illustrative structure only; use actual portal response data when testing.
Security
- Never commit .env.
- Do not log passwords, session cookies, CSRF tokens, or authorization headers.
- Restrict this API to trusted callers before exposing it outside your machine.
- Use only authorized p