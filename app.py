
import os
import requests
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Urja Meter Ops",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ Urja Meter Ops")
st.caption("Meter Management and Energy Monitoring Dashboard")

# Configure this in Streamlit Cloud → Settings → Secrets
DEFAULT_API_URL = "http://localhost:8000"

api_base_url = st.sidebar.text_input(
    "REST API Base URL",
    value=st.secrets.get(
        "API_BASE_URL",
        os.getenv("API_BASE_URL", DEFAULT_API_URL),
    ),
).rstrip("/")


def api_get(path, params=None):
    """Send GET requests to the FastAPI backend."""
    try:
        response = requests.get(
            f"{api_base_url}{path}",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as exc:
        st.error(f"API request failed: {exc}")
    except ValueError:
        st.error("The API returned invalid JSON.")

    return None


def extract_records(payload):
    """Extract list data from common API response formats."""
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in (
            "items",
            "meters",
            "data",
            "results",
            "records",
            "readings",
        ):
            value = payload.get(key)

            if isinstance(value, list):
                return value

            if isinstance(value, dict):
                records = extract_records(value)
                if records:
                    return records

    return []


with st.sidebar:
    st.header("Navigation")

    page = st.radio(
        "Select a page",
        [
            "API Health",
            "Meters",
            "Meter Details",
            "Energy Readings",
        ],
    )

    st.divider()
    st.caption("Urja Meter Ops API Client")


if page == "API Health":
    st.subheader("Backend Status")

    if st.button("Check API Health", type="primary"):
        result = api_get("/health")

        if result is not None:
            st.success("API responded successfully")
            st.json(result)


elif page == "Meters":
    st.subheader("Meter List")

    col1, col2 = st.columns(2)

    with col1:
        page_number = st.number_input(
            "Page Number",
            min_value=1,
            value=1,
            step=1,
        )

    with col2:
        page_size = st.selectbox(
            "Records per page",
            [10, 20, 50, 100],
            index=1,
        )

    if st.button("Load Meters", type="primary"):
        result = api_get(
            "/api/v1/meters",
            params={
                "page": int(page_number),
                "page_size": int(page_size),
            },
        )

        if result is not None:
            records = extract_records(result)

            if records:
                df = pd.json_normalize(records)

                st.metric("Meters Returned", len(df))
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                )

                st.download_button(
                    "Download Meters CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name="meters.csv",
                    mime="text/csv",
                )
            else:
                st.warning(
                    "No meter records found. "
                    "Check the backend response format."
                )
                st.json(result)


elif page == "Meter Details":
    st.subheader("Meter Details")

    meter_id = st.text_input(
        "Enter Meter ID",
        value="J100000",
        placeholder="Example: J100000",
    )

    if st.button("Get Meter Details", type="primary"):
        if not meter_id.strip():
            st.warning("Please enter a meter ID.")
        else:
            result = api_get(
                f"/api/v1/meters/{meter_id.strip()}"
            )

            if result is not None:
                st.json(result)


elif page == "Energy Readings":
    st.subheader("Meter Energy Readings")

    meter_id = st.text_input(
        "Enter Meter ID",
        value="J100000",
        key="energy_meter_id",
    )

    if st.button("Load Energy Readings", type="primary"):
        if not meter_id.strip():
            st.warning("Please enter a meter ID.")
        else:
            result = api_get(
                f"/api/v1/meters/"
                f"{meter_id.strip()}/consumption"
            )

            if result is not None:
                records = extract_records(result)

                if records:
                    df = pd.json_normalize(records)

                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True,
                    )

                    numeric_columns = [
                        column
                        for column in df.columns
                        if column.lower().split(".")[-1]
                        in ("kwh", "kvah")
                    ]

                    if numeric_columns:
                        st.subheader("Energy Trend")

                        chart_df = df[numeric_columns].apply(
                            pd.to_numeric,
                            errors="coerce",
                        )

                        st.line_chart(chart_df)

                    st.download_button(
                        "Download Readings CSV",
                        data=df.to_csv(index=False).encode("utf-8"),
                        file_name=(
                            f"{meter_id.strip()}_energy.csv"
                        ),
                        mime="text/csv",
                    )

                else:
                    st.info(
                        "No readings list detected. "
                        "Showing the raw response."
                    )
                    st.json(result)


st.divider()
st.caption("Urja Meter Ops | Streamlit Dashboard")
