from app.client import UrjaPortalClient


def test_clean_number():
    assert UrjaPortalClient.clean_number("48,438.74") == 48438.74
    assert UrjaPortalClient.clean_number("-") is None
    assert UrjaPortalClient.clean_number("not a number") is None


def test_clean_text():
    assert UrjaPortalClient.clean_text("  Installed  ") == "Installed"
    assert UrjaPortalClient.clean_text("N/A") is None


def test_extract_energy_records():
    data = {
        "data": {
            "timestamp": "23/06/2026 23:30",
            "data": [
                {"timestamp": "23/06/2026 23:30", "kwh": "48438.74", "kvah": "50000.1"}
            ],
        }
    }
    payload = data.get("data", data)
    records = payload["data"]
    assert len(records) == 1
    assert UrjaPortalClient.clean_number(records[0]["kwh"]) == 48438.74
