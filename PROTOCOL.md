Protocol Discovery Notes
Confirmed observations
Energy readings
- Request method: GET
- Route pattern: /portal/meters/{meter_id}/energy
- Observed example: /portal/meters/J100000/energy
- Observed HTTP status: 200 OK
- Preview includes timestamps and kwh, kvah fields.
- Preview appears to wrap readings in a data object, with a nested list under data.
Meter listing page
- Browser URL/request observed: /meters
- UI showed 403 total meters.
- Visible columns: Meter, Serial, Make, Phase, Status, DT.
- A captured /meters response view showed “0 total / No meters found”; therefore this document request is not yet confirmed as the populated data source.
- The actual request that supplies the meter table must still be identified.
Not yet verified
- Login URL and HTTP method.
- Username/password field names.
- CSRF behavior.
- Session cookie name and expiry response.
- Actual meter-list data endpoint.
- Actual meter-detail endpoint.
- Pagination parameter names and response metadata.
- Hierarchy endpoint and response schema.
- HTML selectors for populated meter data.
Pagination investigation
The user reports 21 pages and around 20 rows per page, but the request parameters have not been observed. Inspect the page-2 request before implementing pagination assumptions.