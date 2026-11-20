# EV Country Analytics

An interactive dashboard and PySpark batch pipeline for analyzing EV adoption
from the EV country CSV. The dashboard supports refreshed CSV uploads; it does
not poll a live provider. Results are scoped to historical records for EV cars.

## Interactive dashboard

### Run locally

```powershell
docker compose up --build dashboard
```

Open [http://localhost:8501](http://localhost:8501) and upload a CSV with the
expected columns. Uploads are analyzed in memory for the current app session
and are not written to the repository or container filesystem.

### Deploy on Streamlit Community Cloud

1. Push this repository to GitHub. Keep the CSV and notebook out of the repo;
   the `.gitignore` excludes both.
2. In Streamlit Community Cloud, create an app from
   `Mahammedjawaad6/ev-analytics-dashboard`, branch `main`, entrypoint
   `dashboard.py`.
3. If prompted, sign in through GitHub and grant the repository access needed
   for deployment. Upload a refreshed CSV in the deployed app when new data is
   available.

Community Cloud requires permission to access private repositories and creates
a read-only deploy key for the selected repository. Review its current
permission prompt before approving. The app does not require secrets or API
credentials.

## Batch analytics

The Spark job reads the source CSV from `/data/ev-data.csv` and writes Parquet
datasets under `output/`. Run it from the project directory:

```powershell
docker compose run --build --rm ev-analytics
```

The source file is mounted read-only and is deliberately not copied into the
Docker image or GitHub repository.

- `global_ev_stock_growth/` — yearly global stock and year-over-year growth
- `top_countries_latest_year/` — top 10 countries in the latest historical year
- `run_summary.json` — input row count and run metadata

## Tests

```powershell
docker compose build
docker compose run --rm --entrypoint python ev-analytics -m pytest -v
```

GitHub Actions runs the test suite on pushes and pull requests to `main`.

## Data requirements

The CSV must include `region_country`, `category`, `parameter`, `mode`,
`powertrain`, `year`, `unit`, `value`, and `Aggregate group`. The deployed
dashboard uses a manual file upload; it is not a real-time feed. To automate
updates, connect an authorized EV data provider/API and define its refresh and
usage policy first.
