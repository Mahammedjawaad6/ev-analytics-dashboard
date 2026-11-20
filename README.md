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
10 countries in the latest historical year, with a data-trained country stock
forecast. CSV parsing, validation, charts, ranking, model training, validation,
and prediction run client-side without a third-party JavaScript dependency.

## Forecast model

The forecast panel trains a short-term supervised model from the uploaded CSV;
it does not call an external AI service or send data to a server. For each
country with at least four eligible historical EV car-stock observations, it
fits ordinary least-squares linear regression to the latest four observed
stocks against calendar year. Projections are limited to one, two, or three
years after the latest common country-stock year.

Model selection uses rolling-origin validation on up to the latest three
observations per country. It compares regression against a last-observation
("persistence") baseline using weighted absolute percentage error (WAPE):
`sum(abs(prediction - actual)) / sum(actual)`. The method with lower validation
error generates the displayed forecasts. The panel reports both errors,
validation coverage, the selected method, and forecast year. Projections are
point estimates without confidence intervals and are not guarantees; new data,
policy, supply, and market conditions may change future stock.

For the available 49,375-row local example CSV, the rolling holdout contained
117 predictions across 40 countries. The four-observation linear trend scored
13.0% WAPE versus 24.2% for persistence on that particular snapshot. This is
a historical validation result, not a promise of future accuracy; the model is
retrained and re-evaluated independently for each uploaded file.

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
