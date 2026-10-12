# Input and output schema

## Input

Send one JSON object with all of these fields:

| Field | Type and rules |
|---|---|
| `grid_available` | Exactly 10 Boolean values for hourly slots 10:00–19:00. `true` means grid power is available; `false` means outage. |
| `generator_capacity_kw` | Positive whole number. |
| `fuel_budget_litres` | Non-negative number with at most two decimal places. |
| `fuel_table` | Non-empty array of `{ "load_kw": integer, "litres_per_hour": number }` tiers. Load thresholds strictly increase, do not exceed capacity, and the last threshold equals capacity. |
| `max_consecutive_dark` | Non-negative whole number. |
| `shops` | Array of at most 12 shops; an empty array is valid. |

Each shop must have a unique, non-blank string `id`, positive integer `kw`, `type` equal to `mandatory` or `normal`, and exactly 10 non-negative integer `value_per_slot` values.

## Successful response

`hours` is the full ten-slot timeline. `roster` is the subset of outage-hour decisions requested by the project brief. `per_shop_dark_hours` contains zero-based slot indexes (`0` is 10:00, `9` is 19:00). Fuel values are rounded to hundredths of a litre.

```json
{
  "status": "ok",
  "value_total": 42,
  "fuel_total_litres": 7.2,
  "per_shop_dark_hours": {
    "shop_a": [2, 5],
    "shop_b": []
  },
  "hours": [
    {
      "hour": "10:00",
      "grid": true,
      "capacity_kw": 10,
      "load_kw": 0,
      "fuel_used_litres": 0,
      "powered": ["shop_a", "shop_b"],
      "dark": []
    },
    {
      "hour": "12:00",
      "grid": false,
      "capacity_kw": 10,
      "load_kw": 7,
      "fuel_used_litres": 1.2,
      "powered": ["pharmacy", "tailor"],
      "dark": [
        {"id": "mobile", "reason": "Capacity: this would require 13 kW, above the 10 kW limit (current load 7 kW)."}
      ]
    }
  ],
  "roster": [
    {
      "hour": "12:00",
      "powered": ["pharmacy", "tailor"],
      "dark": [
        {"id": "mobile", "reason": "Capacity: this would require 13 kW, above the 10 kW limit (current load 7 kW)."}
      ],
      "load_kw": 7,
      "fuel_used_litres": 1.2
    }
  ]
}
```

On a valid day with no outages, `roster` is empty and both totals are zero. `hours` still contains ten grid-powered entries.

## Other statuses

- Invalid input returns `{"status":"invalid_input","detail":"..."}` and HTTP 400. The detail names the field or validation issue.
- Infeasible constraints return HTTP 200 and `{"status":"infeasible","detail":"...","conflicts":[...]}`. A conflict identifies shops and outage hours when a mandatory-load or mandatory-fuel conflict can be established.

## Rules enforced

- Every mandatory shop is powered during every outage.
- Combined outage-hour load never exceeds generator capacity.
- Hourly fuel is based on combined load and the first fuel-table tier covering that load; zero load uses zero fuel.
- Total fuel never exceeds the daily budget. Fuel arithmetic uses integer hundredths of a litre.
- No normal shop remains dark for more than the configured number of consecutive slots. Grid-on and powered slots reset a dark run.
- Total value is maximized across outage slots, including mandatory shops. Among equal-value rosters, lower fuel use wins.
- Every shop dark in an outage has a reason in `dark`.
