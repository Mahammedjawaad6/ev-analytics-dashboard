# EV Country Analytics

A browser-based EV market dashboard and optional PySpark batch pipeline.
The static website works on GitHub Pages and renders charts from a CSV selected
by the visitor. The CSV is parsed and analyzed in the browser; it is not sent to
a server, stored in the repository, or kept after the page is closed.

The dashboard updates immediately when a new CSV is selected. It does not poll
an external data provider, so its figures are only as current as the uploaded
file. No source dataset is included in this repository.

## Dashboard preview

The website source is in [`web/`](./web/). Open `web/index.html` in a browser,
or serve it locally:

```powershell
python -m http.server 8080 --directory web
```

Then visit [http://localhost:8080](http://localhost:8080) and upload a CSV. The
dashboard shows global EV car-stock trends, year-over-year growth, and the top
10 countries in the latest historical year. CSV parsing, validation, charts,
and ranking run client-side without a third-party JavaScript dependency.

## GitHub Pages hosting

The GitHub Actions workflow in
[`pages.yml`](./.github/workflows/pages.yml) publishes the `web/` directory
after changes to `main`.

1. Push this repository to `Mahammedjawaad6/ev-analytics-dashboard`.
2. In the repository's **Settings → Pages**, select **GitHub Actions** as the
   build and deployment source if Pages is not already enabled.
3. Check the `Deploy dashboard to GitHub Pages` workflow. Its environment
   contains the published site URL after a successful deployment.

GitHub Pages is static hosting; it can't run Spark or a streaming data feed.
GitHub also records visitor IP addresses for site security. Private-repository
Pages availability depends on the GitHub account plan. Keep the repository
private unless you choose otherwise and verify Pages is included in your plan.

## Data format

Upload a CSV with `region_country`, `category`, `parameter`, `mode`,
`powertrain`, `year`, `unit`, `value`, and `Aggregate group`. The dashboard
filters historical EV car stock, excluding projections. The displayed refresh
time indicates when the currently selected file was analyzed, not when the
underlying data provider last published new information.

## Batch analytics

The PySpark batch job reads `/data/ev-data.csv` and writes Parquet datasets
under `output/`. Keep the source CSV in the project folder locally; it is
excluded from Git and Docker build contexts.

```powershell
docker compose run --build --rm ev-analytics
```

- `global_ev_stock_growth/` — yearly global stock and year-over-year growth
- `top_countries_latest_year/` — top 10 countries in the latest historical year
- `run_summary.json` — input row count and run metadata

For local Streamlit development instead of Pages:

```powershell
docker compose up --build dashboard
```

Open [http://localhost:8501](http://localhost:8501) and upload the CSV.

## Tests

```powershell
node --test tests/dashboard_frontend.test.mjs
docker compose build
docker compose run --rm --entrypoint python ev-analytics -m pytest -v
```

GitHub Actions runs the browser analytics and PySpark tests on pushes and pull
requests to `main`.
