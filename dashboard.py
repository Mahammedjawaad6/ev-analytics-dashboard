"""Streamlit dashboard for uploaded or locally monitored EV country data."""

import os
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from src.dashboard_analytics import (
    build_country_forecast,
    build_dashboard_analytics,
    load_data_file,
    load_uploaded_csv,
)

DATA_FILE = Path(os.environ.get("EV_DATA_FILE", "/data/ev-data.csv"))
REFRESH_SECONDS = 10

st.set_page_config(
    page_title="EV Country Analytics",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ EV Country Analytics")
st.caption(
    f"The mounted CSV is checked every {REFRESH_SECONDS} seconds while this page "
    "is open. Analytics and the forecast model are recalculated when it changes."
)


@st.fragment(run_every=f"{REFRESH_SECONDS}s")
def render_dashboard():
    uploaded_file = st.file_uploader("Upload EV country data (CSV)", type=["csv"])
    st.info(
        "Uploaded files are processed for this app session and are not saved. "
        "When no file is uploaded, the dashboard reads the mounted CSV directly."
    )

    try:
        if uploaded_file is not None:
            data = load_uploaded_csv(BytesIO(uploaded_file.getvalue()))
            source_name = uploaded_file.name
            updated_at = datetime.now().astimezone()
        elif DATA_FILE.is_file():
            data = load_data_file(DATA_FILE)
            source_name = DATA_FILE.name
            updated_at = datetime.fromtimestamp(
                DATA_FILE.stat().st_mtime
            ).astimezone()
        else:
            st.markdown(
                """
                ### Start exploring

                Upload an EV country CSV to see:
                - Global historical EV car stock and year-over-year growth
                - The top 10 countries in the latest historical year
                - A validated country-stock forecast

                The mounted CSV must contain `region_country`, `category`,
                `parameter`, `mode`, `powertrain`, `year`, `unit`, `value`, and
                `Aggregate group`.
                """
            )
            return

        growth, top_countries, latest_year = build_dashboard_analytics(data)
    except (ValueError, UnicodeDecodeError, OSError) as exc:
        st.error(
            "Could not analyze the current CSV; it will be retried "
            f"automatically: {exc}"
        )
        return

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

    st.caption(
        f"Source: {source_name} · Last modified/analyzed: "
        f"{updated_at.strftime('%Y-%m-%d %H:%M:%S %Z')}"
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

    units = sorted(growth["unit"].dropna().unique())
    forecast_unit = "Vehicles" if "Vehicles" in units else units[0]
    forecast_data, forecast_summary = build_country_forecast(data, forecast_unit)
    with st.expander("Country EV stock forecast"):
        st.caption(
            f"Selected model: {forecast_summary['model_name']} · "
            f"{forecast_summary['validation_samples']} rolling validation "
            f"predictions across {forecast_summary['validation_countries']} countries"
        )
        model_wape = forecast_summary["model_wape"]
        baseline_wape = forecast_summary["baseline_wape"]
        score_columns = st.columns(2)
        score_columns[0].metric(
            "Regression WAPE",
            "—" if model_wape is None else f"{model_wape * 100:.1f}%",
        )
        score_columns[1].metric(
            "Last-value WAPE",
            "—" if baseline_wape is None else f"{baseline_wape * 100:.1f}%",
        )
        if forecast_data.empty:
            st.write("At least four historical observations per country are needed.")
        else:
            st.write(f"Forecast year: **{forecast_summary['target_year']}**")
            st.dataframe(
                forecast_data.rename(
                    columns={
                        "country": "Country",
                        "current_year": "Current year",
                        "current_stock": "Current EV stock",
                        "forecast_year": "Forecast year",
                        "forecast_stock": "Forecast EV stock",
                        "change_pct": "Change (%)",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )

    with st.expander("About the data"):
        st.write(
            f"Analyzed {len(data):,} rows from **{source_name}**. "
            "Only historical EV stock records for cars and the EV powertrain "
            "are used for analytics and the forecast. Projections are excluded."
        )


render_dashboard()
