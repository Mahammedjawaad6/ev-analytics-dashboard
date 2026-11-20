"""Streamlit dashboard for uploaded EV country data."""

from io import BytesIO

import pandas as pd
import streamlit as st

from src.dashboard_analytics import build_dashboard_analytics, load_uploaded_csv

st.set_page_config(
    page_title="EV Country Analytics",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ EV Country Analytics")
st.caption(
    "Explore historical EV adoption. Upload a refreshed CSV to update the analysis; "
    "this dashboard does not connect to a live data feed."
)

uploaded_file = st.file_uploader("Upload EV country data (CSV)", type=["csv"])
st.info(
    "Data is processed for this app session and is not written to the repository. "
    "For an update, upload the latest CSV again."
)

if uploaded_file is None:
    st.markdown(
        """
        ### Start exploring

        Upload the EV country CSV to see:
        - Global historical EV car stock and year-over-year growth
        - The top 10 countries in the latest available historical year

        The file must contain the columns `region_country`, `category`,
        `parameter`, `mode`, `powertrain`, `year`, `unit`, `value`, and
        `Aggregate group`.
        """
    )
    st.stop()

try:
    data = load_uploaded_csv(BytesIO(uploaded_file.getvalue()))
    growth, top_countries, latest_year = build_dashboard_analytics(data)
except (ValueError, UnicodeDecodeError, OSError) as exc:
    st.error(f"Could not analyze this CSV: {exc}")
    st.stop()

latest_global = growth.sort_values("year").iloc[-1]
metric_columns = st.columns(4)
metric_columns[0].metric("Rows analyzed", f"{len(data):,}")
metric_columns[1].metric("Historical years", f"{data['year'].nunique():,}")
metric_columns[2].metric("Latest country year", str(latest_year))
growth_value = latest_global["year_over_year_growth_pct"]
metric_columns[3].metric(
    "Latest global YoY growth",
    "—" if pd.isna(growth_value) else f"{growth_value:.1f}%",
)

st.subheader("Global EV car stock")
st.line_chart(
    growth.pivot(index="year", columns="unit", values="ev_stock_millions"),
    y_label="Vehicles (millions)",
)

left, right = st.columns([3, 2])
with left:
    st.subheader(f"Top countries — {latest_year}")
    st.bar_chart(
        top_countries.set_index("country")["ev_stock_millions"],
        horizontal=True,
        x_label="EV stock (millions)",
    )
with right:
    st.subheader("Country ranking")
    st.dataframe(
        top_countries[["country", "ev_stock_millions"]].rename(
            columns={"ev_stock_millions": "EV stock (millions)"}
        ),
        hide_index=True,
        use_container_width=True,
    )

with st.expander("About the data"):
    st.write(
        f"Analyzed {len(data):,} rows from **{uploaded_file.name}**. "
        "Only historical EV stock records for cars and the EV powertrain are "
        "used for these indicators. Projections are not included."
    )
