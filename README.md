# Who Stays On?

**Keeping Shapla Shopping Complex alive through a day of load shedding.**

Who Stays On? creates an optimal generator schedule for up to 12 shops over the 10 hourly slots from 10:00 to 20:00. The responsive English-language dashboard calls the same Flask API available to other markets. The interface uses local HTML, CSS, and JavaScript only; after Python dependencies have been installed, the app has no internet or database requirement.

## Run on Windows

Install Python 3.10 or newer, then open PowerShell in this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Alternatively, after installing the requirements, double-click `run.bat`. Open <http://127.0.0.1:5000>.

## Publish a public website on Render

The repository includes a Render Blueprint in `render.yaml`. To publish it, push this project to a GitHub repository you control, sign in to Render, choose **New → Blueprint**, connect that repository, and apply the `who-stays-on` service. Render installs `requirements.txt`, starts the Flask app with Gunicorn, and provides the public `*.onrender.com` URL when deployment succeeds. The first build may take several minutes.

The public URL cannot be created until Render is authorized to access a GitHub repository. Do not commit `.venv`, Python cache folders, or private credentials.

## Project map

- `app.py` serves the dashboard and `POST /api/roster`.
- `solver.py` validates input, builds the exact CP-SAT optimization model, creates explanations, and independently validates the result.
- `render.yaml` configures public deployment on Render.
- `templates/index.html`, `static/style.css`, and `static/script.js` implement the complete responsive dashboard. The dashboard sends its inputs to the same API; it does not contain a second solver.
- `sample_input.json` and `sample_output.json` are the 12-shop example and its actual API output.
- `tests/` contains standard-library `unittest` tests.
- `evidence/` contains actual boundary and regression inputs/outputs.

## Dashboard

Edit the generator, diesel, outage, and shop information with the visual form. Each shop has ten separate value fields, one for each hour. A shop requiring more power than the generator is automatically unavailable during outages. Shops marked জরুরি (mandatory) must stay on during every outage. The optional JSON panel imports a local JSON file or applies pasted JSON to the form. After a plan is calculated, download the JSON response or print the A4 landscape roster and generator loads.

## Input JSON

The input format is also documented in [schema.md](./schema.md). `grid_available` has exactly ten Booleans: `true` means grid power is available and `false` means an outage. Fuel-table load levels increase strictly, and the last level equals the generator capacity. Diesel figures support at most two decimal places. A shop has ten non-negative integer values in `value_per_slot`.

The supplied 12-shop scenario is in `sample_input.json`. The five-shop worked example in the project brief is covered by a unit test.

## API

`POST http://127.0.0.1:5000/api/roster` accepts the input JSON as its request body.

- HTTP 200 with `status: "ok"` and the optimized roster
- HTTP 200 with `status: "infeasible"` and details when constraints conflict
- HTTP 400 with `status: "invalid_input"` and a field-specific detail for malformed input

The response keeps the supplied schema's `hours` array for the full ten-slot board. It also includes `roster`, containing only outage-hour decisions; on a day with no outages, `roster` is empty. Fuel, value, and dark-hour totals are calculated from the returned schedule.

Example PowerShell request:

```powershell
$payload = Get-Content .\sample_input.json -Raw
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/roster -Method Post -ContentType "application/json" -Body $payload
```

## Solver design

The CP-SAT model uses one Boolean per shop/hour, enforces mandatory power, capacity and consecutive-dark-window constraints, and models the combined hourly load. Fuel is selected from the first table tier that covers that load and represented in integer hundredths of a litre. The objective maximizes total outage-hour value; its lexicographic tie-break minimizes total fuel without allowing fuel savings to reduce the optimal value. One solver worker and a fixed seed make equal inputs deterministic.

The supported input has at most 12 shops and ten hourly slots. The solver enumerates only distinct load totals achievable by shop subsets, not every possible load up to an arbitrarily large capacity.

## Test

Run the full suite with Python's built-in `unittest`:

```powershell
python -m unittest discover -v
```

Tests cover the 12-shop scenario, the supplied worked example, mandatory shops, capacity and fuel boundaries, consecutive dark limits, strict input validation, API response codes, no-outage and empty-shop cases, infeasibility, oversized shops, deterministic results, and fuel tie-breaking.

The project prompt refers to a later “minute-150” updated input, but that changed JSON file was not included with the supplied files. No output is claimed for that unavailable input; the updated case can be run through the API once it is provided.
