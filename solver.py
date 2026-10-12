from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from ortools.sat.python import cp_model


HOUR_LABELS = [f"{hour}:00" for hour in range(10, 20)]
_MAX_CP_INTEGER = (1 << 62) - 1


def _whole_number(value: Any, field: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} must be a whole number greater than or equal to {minimum}")
    return value


def _cents(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number with at most two decimal places")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not amount.is_finite() or amount < 0 or amount * 100 != (amount * 100).to_integral_value():
        raise ValueError(f"{field} must be non-negative with at most two decimal places")
    cents = int(amount * 100)
    if cents > _MAX_CP_INTEGER:
        raise ValueError(f"{field} is too large for the supported solver range")
    return cents


def _normalise_input(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")

    required = (
        "grid_available",
        "generator_capacity_kw",
        "fuel_budget_litres",
        "fuel_table",
        "max_consecutive_dark",
        "shops",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")

    grid = payload["grid_available"]
    if not isinstance(grid, list) or len(grid) != 10:
        raise ValueError("grid_available must contain exactly 10 Boolean values")
    if any(type(value) is not bool for value in grid):
        raise ValueError("grid_available entries must be Boolean values")

    capacity = _whole_number(payload["generator_capacity_kw"], "generator_capacity_kw", minimum=1)
    if capacity > _MAX_CP_INTEGER:
        raise ValueError("generator_capacity_kw exceeds the supported solver range")

    budget_cents = _cents(payload["fuel_budget_litres"], "fuel_budget_litres")
    max_dark = _whole_number(payload["max_consecutive_dark"], "max_consecutive_dark", minimum=0)

    fuel_table = payload["fuel_table"]
    if not isinstance(fuel_table, list) or not fuel_table:
        raise ValueError("fuel_table must be a non-empty list")
    cleaned_fuel: list[dict[str, int]] = []
    previous_load = 0
    for index, row in enumerate(fuel_table):
        if not isinstance(row, dict):
            raise ValueError(f"fuel_table[{index}] must be an object")
        load_kw = _whole_number(row.get("load_kw"), f"fuel_table[{index}].load_kw", minimum=1)
        if load_kw <= previous_load:
            raise ValueError("fuel_table load_kw levels must be strictly increasing")
        if load_kw > capacity:
            raise ValueError(f"fuel_table[{index}].load_kw cannot exceed generator_capacity_kw")
        rate_cents = _cents(row.get("litres_per_hour"), f"fuel_table[{index}].litres_per_hour")
        if rate_cents > _MAX_CP_INTEGER // 10:
            raise ValueError(f"fuel_table[{index}].litres_per_hour is too large for the supported solver range")
        cleaned_fuel.append({"load_kw": load_kw, "litres_cents": rate_cents})
        previous_load = load_kw
    if cleaned_fuel[-1]["load_kw"] != capacity:
        raise ValueError("the last fuel_table load_kw must equal generator_capacity_kw")

    shops = payload["shops"]
    if not isinstance(shops, list):
        raise ValueError("shops must be a list")
    if len(shops) > 12:
        raise ValueError("shops may contain at most 12 entries")
    cleaned_shops: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, shop in enumerate(shops):
        if not isinstance(shop, dict):
            raise ValueError(f"shops[{index}] must be an object")
        shop_id = shop.get("id")
        if not isinstance(shop_id, str) or not shop_id.strip():
            raise ValueError(f"shops[{index}].id must be a non-blank string")
        shop_id = shop_id.strip()
        if shop_id in seen_ids:
            raise ValueError(f"duplicate shop id: {shop_id}")
        seen_ids.add(shop_id)

        kw = _whole_number(shop.get("kw"), f"shops[{index}].kw", minimum=1)
        shop_type = shop.get("type")
        if not isinstance(shop_type, str) or shop_type not in {"mandatory", "normal"}:
            raise ValueError(f"shops[{index}].type must be 'mandatory' or 'normal'")
        values = shop.get("value_per_slot")
        if not isinstance(values, list) or len(values) != 10:
            raise ValueError(f"shops[{index}].value_per_slot must contain exactly 10 values")
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError(f"shops[{index}].value_per_slot values must be non-negative whole numbers")
        cleaned_shops.append(
            {
                "id": shop_id,
                "kw": kw,
                "type": shop_type,
                "value_per_slot": values.copy(),
            }
        )

    if sum(shop["kw"] for shop in cleaned_shops) > _MAX_CP_INTEGER:
        raise ValueError("combined shop load exceeds the supported solver range")
    max_total_value = sum(
        shop["value_per_slot"][hour]
        for shop in cleaned_shops
        for hour, available in enumerate(grid)
        if not available
    )
    if max_total_value > _MAX_CP_INTEGER:
        raise ValueError("sum of value_per_slot exceeds the supported solver range")

    return {
        "grid_available": grid.copy(),
        "generator_capacity_kw": capacity,
        "fuel_budget_cents": budget_cents,
        "fuel_budget_litres": budget_cents / 100,
        "fuel_table": cleaned_fuel,
        "max_consecutive_dark": max_dark,
        "shops": cleaned_shops,
        "max_total_value": max_total_value,
    }


def _fuel_for_load_cents(load_kw: int, fuel_table: list[dict[str, int]]) -> int:
    if load_kw == 0:
        return 0
    for tier in fuel_table:
        if load_kw <= tier["load_kw"]:
            return tier["litres_cents"]
    raise ValueError("combined load exceeds the last fuel_table load level")


def _fuel_litres(cents: int) -> float:
    return cents / 100


def _empty_solution(data: dict[str, Any]) -> dict[str, Any]:
    shops = data["shops"]
    hours = [
        {
            "hour": HOUR_LABELS[index],
            "grid": True,
            "capacity_kw": data["generator_capacity_kw"],
            "load_kw": 0,
            "fuel_used_litres": 0.0,
            "powered": [shop["id"] for shop in shops],
            "dark": [],
        }
        for index in range(10)
    ]
    return {
        "status": "ok",
        "value_total": 0,
        "fuel_total_litres": 0.0,
        "per_shop_dark_hours": {shop["id"]: [] for shop in shops},
        "hours": hours,
        "roster": [],
    }


def _infeasible_result(data: dict[str, Any]) -> dict[str, Any]:
    capacity = data["generator_capacity_kw"]
    fuel_table = data["fuel_table"]
    mandatory = [shop for shop in data["shops"] if shop["type"] == "mandatory"]
    mandatory_load = sum(shop["kw"] for shop in mandatory)
    outage_indexes = [
        index for index, is_grid_available in enumerate(data["grid_available"]) if not is_grid_available
    ]
    conflicts: list[dict[str, Any]] = []
    if mandatory_load > capacity:
        conflicts.append(
            {
                "rule": "generator_capacity_kw",
                "shops": [shop["id"] for shop in mandatory],
                "hours": [HOUR_LABELS[index] for index in outage_indexes],
                "required_load_kw": mandatory_load,
                "capacity_kw": capacity,
            }
        )
    elif outage_indexes:
        mandatory_fuel = _fuel_for_load_cents(mandatory_load, fuel_table) * len(outage_indexes)
        if mandatory_fuel > data["fuel_budget_cents"]:
            conflicts.append(
                {
                    "rule": "fuel_budget_litres",
                    "shops": [shop["id"] for shop in mandatory],
                    "hours": [HOUR_LABELS[index] for index in outage_indexes],
                    "mandatory_fuel_litres": _fuel_litres(mandatory_fuel),
                    "fuel_budget_litres": data["fuel_budget_litres"],
                }
            )
    detail = "No valid roster satisfies the generator, fuel-budget, and consecutive-dark constraints together."
    if conflicts:
        detail = "Mandatory shops alone exceed a hard generator or fuel constraint."
    return {"status": "infeasible", "detail": detail, "conflicts": conflicts}


def _dark_reason(
    shop: dict[str, Any],
    hour_index: int,
    load_kw: int,
    fuel_used_cents: int,
    day_fuel_cents: int,
    total_value: int,
    data: dict[str, Any],
) -> str:
    added_load = load_kw + shop["kw"]
    if added_load > data["generator_capacity_kw"]:
        return (
            f"Capacity: this would require {added_load} kW, above the "
            f"{data['generator_capacity_kw']} kW limit (current load {load_kw} kW)."
        )

    added_fuel = _fuel_for_load_cents(added_load, data["fuel_table"]) - fuel_used_cents
    if day_fuel_cents + added_fuel > data["fuel_budget_cents"]:
        over_by = day_fuel_cents + added_fuel - data["fuel_budget_cents"]
        return (
            f"Fuel budget: powering it would add {_fuel_litres(added_fuel):.2f} L "
            f"and exceed the daily budget by {_fuel_litres(over_by):.2f} L."
        )

    hour_value = shop["value_per_slot"][hour_index]
    return (
        f"Day-wide value trade-off: this shop is worth {hour_value} points at "
        f"{HOUR_LABELS[hour_index]}; the selected feasible roster scores {total_value} points."
    )


def solve_roster(payload: Any) -> dict[str, Any]:
    try:
        data = _normalise_input(payload)
    except ValueError as exc:
        return {"status": "invalid_input", "detail": str(exc)}

    grid = data["grid_available"]
    outage_indexes = [index for index, is_available in enumerate(grid) if not is_available]
    shops = data["shops"]
    capacity = data["generator_capacity_kw"]

    if not outage_indexes:
        return _empty_solution(data)

    model = cp_model.CpModel()
    powered_vars: dict[tuple[int, int], Any] = {}
    for shop_index, shop in enumerate(shops):
        for hour in range(10):
            variable = model.NewBoolVar(f"powered_{shop_index}_{hour}")
            powered_vars[(shop_index, hour)] = variable
            if grid[hour] or shop["type"] == "mandatory":
                model.Add(variable == 1)
            elif shop["kw"] > capacity:
                model.Add(variable == 0)

    possible_loads = {0}
    for shop in shops:
        possible_loads |= {
            load + shop["kw"]
            for load in tuple(possible_loads)
            if load + shop["kw"] <= capacity
        }
    load_vars: dict[int, Any] = {}
    fuel_vars: dict[int, Any] = {}
    for hour in outage_indexes:
        maximum_reachable_load = max(possible_loads)
        load_var = model.NewIntVar(0, maximum_reachable_load, f"load_{hour}")
        fuel_var = model.NewIntVar(
            0,
            max(tier["litres_cents"] for tier in data["fuel_table"]),
            f"fuel_cents_{hour}",
        )
        load_choices = {
            load: model.NewBoolVar(f"load_{hour}_{load}")
            for load in sorted(possible_loads)
        }
        model.AddExactlyOne(load_choices.values())
        model.Add(
            load_var
            == sum(load * choice for load, choice in load_choices.items())
        )
        model.Add(
            fuel_var
            == sum(
                _fuel_for_load_cents(load, data["fuel_table"]) * choice
                for load, choice in load_choices.items()
            )
        )
        model.Add(
            load_var
            == sum(
                shop["kw"] * powered_vars[(shop_index, hour)]
                for shop_index, shop in enumerate(shops)
            )
        )
        load_vars[hour] = load_var
        fuel_vars[hour] = fuel_var

    total_fuel_var = model.NewIntVar(0, data["fuel_budget_cents"], "total_fuel_cents")
    model.Add(total_fuel_var == sum(fuel_vars.values()))

    max_dark = data["max_consecutive_dark"]
    for shop_index, shop in enumerate(shops):
        if shop["type"] != "normal":
            continue
        for start in range(max(0, 10 - max_dark)):
            model.Add(
                sum(
                    1 - powered_vars[(shop_index, hour)]
                    for hour in range(start, start + max_dark + 1)
                )
                <= max_dark
            )

    value_expr = sum(
        shop["value_per_slot"][hour] * powered_vars[(shop_index, hour)]
        for shop_index, shop in enumerate(shops)
        for hour in outage_indexes
    )
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    fuel_scale = data["fuel_budget_cents"] + 1
    objective_bound = (
        data["max_total_value"] * fuel_scale + data["fuel_budget_cents"]
    )
    if objective_bound <= _MAX_CP_INTEGER:
        model.Maximize(value_expr * fuel_scale - total_fuel_var)
    else:
        model.Maximize(value_expr)
    status = solver.Solve(model)
    if status == cp_model.INFEASIBLE:
        return _infeasible_result(data)
    if status != cp_model.OPTIMAL:
        raise RuntimeError(f"CP-SAT could not prove an optimal roster (solver status {status})")
    best_value = solver.Value(value_expr)
    if objective_bound > _MAX_CP_INTEGER:
        model.Add(value_expr == best_value)
        model.Minimize(total_fuel_var)
        status = solver.Solve(model)
        if status == cp_model.INFEASIBLE:
            return _infeasible_result(data)
        if status != cp_model.OPTIMAL:
            raise RuntimeError(f"CP-SAT could not prove the fuel tie-break (solver status {status})")

    powered_by_hour: dict[int, list[str]] = {}
    dark_by_shop: dict[str, list[int]] = {shop["id"]: [] for shop in shops}
    hours_result: list[dict[str, Any]] = []
    total_fuel_cents = 0
    for hour in range(10):
        powered = [
            shop["id"]
            for shop_index, shop in enumerate(shops)
            if solver.Value(powered_vars[(shop_index, hour)])
        ]
        powered_by_hour[hour] = powered
        dark_ids = [
            shop
            for shop_index, shop in enumerate(shops)
            if not grid[hour] and not solver.Value(powered_vars[(shop_index, hour)])
        ]
        if grid[hour]:
            load_kw = 0
            fuel_cents = 0
        else:
            load_kw = solver.Value(load_vars[hour])
            fuel_cents = solver.Value(fuel_vars[hour])
            total_fuel_cents += fuel_cents
            for shop in dark_ids:
                dark_by_shop[shop["id"]].append(hour)

        hours_result.append(
            {
                "hour": HOUR_LABELS[hour],
                "grid": bool(grid[hour]),
                "capacity_kw": capacity,
                "load_kw": load_kw,
                "fuel_used_litres": _fuel_litres(fuel_cents),
                "powered": powered,
                "dark": [],
            }
        )

    for hour in outage_indexes:
        load_kw = hours_result[hour]["load_kw"]
        fuel_cents = round(hours_result[hour]["fuel_used_litres"] * 100)
        hours_result[hour]["dark"] = [
            {
                "id": shop["id"],
                "reason": _dark_reason(
                    shop,
                    hour,
                    load_kw,
                    fuel_cents,
                    total_fuel_cents,
                    best_value,
                    data,
                ),
            }
            for shop in shops
            if shop["id"] in dark_by_shop and hour in dark_by_shop[shop["id"]]
        ]

    outage_roster = [
        {
            "hour": hours_result[hour]["hour"],
            "powered": hours_result[hour]["powered"],
            "dark": hours_result[hour]["dark"],
            "load_kw": hours_result[hour]["load_kw"],
            "fuel_used_litres": hours_result[hour]["fuel_used_litres"],
        }
        for hour in outage_indexes
    ]
    result = {
        "status": "ok",
        "value_total": best_value,
        "fuel_total_litres": _fuel_litres(total_fuel_cents),
        "per_shop_dark_hours": dark_by_shop,
        "hours": hours_result,
        "roster": outage_roster,
    }
    if not validate_solution(payload, result):
        raise RuntimeError("solver generated a roster that failed independent validation")
    return result


def validate_solution(payload: Any, result: Any) -> bool:
    try:
        data = _normalise_input(payload)
    except ValueError:
        return False
    if not isinstance(result, dict) or result.get("status") != "ok":
        return False
    hours = result.get("hours")
    if not isinstance(hours, list) or len(hours) != 10:
        return False

    shops = data["shops"]
    shops_by_id = {shop["id"]: shop for shop in shops}
    dark_by_shop = {shop["id"]: [] for shop in shops}
    value_total = 0
    fuel_total_cents = 0
    for index, entry in enumerate(hours):
        if not isinstance(entry, dict) or entry.get("hour") != HOUR_LABELS[index]:
            return False
        if entry.get("grid") is not data["grid_available"][index]:
            return False
        powered = entry.get("powered")
        dark = entry.get("dark")
        if not isinstance(powered, list) or not isinstance(dark, list):
            return False
        if len(powered) != len(set(powered)) or any(shop_id not in shops_by_id for shop_id in powered):
            return False
        dark_ids = []
        for dark_entry in dark:
            if not isinstance(dark_entry, dict):
                return False
            shop_id = dark_entry.get("id")
            if shop_id not in shops_by_id or not isinstance(dark_entry.get("reason"), str) or not dark_entry["reason"]:
                return False
            dark_ids.append(shop_id)
        if len(dark_ids) != len(set(dark_ids)) or set(powered) & set(dark_ids):
            return False
        if set(powered) | set(dark_ids) != set(shops_by_id):
            return False
        if type(entry.get("capacity_kw")) is not int or entry["capacity_kw"] != data["generator_capacity_kw"]:
            return False
        if data["grid_available"][index]:
            if set(powered) != set(shops_by_id) or dark or entry.get("load_kw") != 0 or entry.get("fuel_used_litres") != 0:
                return False
            continue

        load_kw = sum(shops_by_id[shop_id]["kw"] for shop_id in powered)
        if (
            load_kw > data["generator_capacity_kw"]
            or type(entry.get("load_kw")) is not int
            or entry["load_kw"] != load_kw
        ):
            return False
        expected_fuel = _fuel_for_load_cents(load_kw, data["fuel_table"])
        actual_fuel = entry.get("fuel_used_litres")
        if isinstance(actual_fuel, bool) or not isinstance(actual_fuel, (int, float)):
            return False
        actual_fuel_cents = _cents(actual_fuel, "fuel_used_litres")
        if actual_fuel_cents != expected_fuel:
            return False
        fuel_total_cents += actual_fuel_cents
        value_total += sum(shops_by_id[shop_id]["value_per_slot"][index] for shop_id in powered)
        for shop_id in dark_ids:
            dark_by_shop[shop_id].append(index)
        if any(
            shops_by_id[shop_id]["type"] == "mandatory"
            for shop_id in dark_ids
        ):
            return False

    if fuel_total_cents > data["fuel_budget_cents"]:
        return False
    if type(result.get("value_total")) is not int or result["value_total"] != value_total:
        return False
    try:
        if _cents(result.get("fuel_total_litres"), "fuel_total_litres") != fuel_total_cents:
            return False
    except ValueError:
        return False
    if result.get("per_shop_dark_hours") != dark_by_shop:
        return False
    expected_roster = [
        {
            "hour": entry["hour"],
            "powered": entry["powered"],
            "dark": entry["dark"],
            "load_kw": entry["load_kw"],
            "fuel_used_litres": entry["fuel_used_litres"],
        }
        for index, entry in enumerate(hours)
        if not data["grid_available"][index]
    ]
    if result.get("roster") != expected_roster:
        return False

    for shop in shops:
        if shop["type"] != "normal":
            continue
        dark_run = 0
        for index, entry in enumerate(hours):
            if data["grid_available"][index] or shop["id"] in entry["powered"]:
                dark_run = 0
            else:
                dark_run += 1
                if dark_run > data["max_consecutive_dark"]:
                    return False
    return True
