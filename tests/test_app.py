from __future__ import annotations

import json
import unittest
from pathlib import Path

from app import app
from solver import solve_roster, validate_solution


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def basic_payload() -> dict:
    return {
        "grid_available": [False] + [True] * 9,
        "generator_capacity_kw": 10,
        "fuel_budget_litres": 8.0,
        "fuel_table": [
            {"load_kw": 4, "litres_per_hour": 0.8},
            {"load_kw": 7, "litres_per_hour": 1.2},
            {"load_kw": 10, "litres_per_hour": 1.6},
        ],
        "max_consecutive_dark": 2,
        "shops": [
            {
                "id": "pharmacy",
                "kw": 3,
                "type": "mandatory",
                "value_per_slot": [5] * 10,
            }
        ],
    }


class SolverTests(unittest.TestCase):
    def test_supplied_twelve_shop_sample_produces_a_valid_roster(self) -> None:
        payload = json.loads((PROJECT_ROOT / "sample_input.json").read_text(encoding="utf-8"))
        result = solve_roster(payload)

        self.assertEqual(result["status"], "ok")
        self.assertTrue(validate_solution(payload, result))
        self.assertEqual(len(result["roster"]), 7)
        self.assertLessEqual(result["fuel_total_litres"], payload["fuel_budget_litres"])

    def test_worked_example_has_expected_value_and_fuel(self) -> None:
        payload = {
            "grid_available": [True, True, False, False, False, True, True, False, False, False],
            "generator_capacity_kw": 10,
            "fuel_budget_litres": 8.0,
            "fuel_table": [
                {"load_kw": 4, "litres_per_hour": 0.8},
                {"load_kw": 7, "litres_per_hour": 1.2},
                {"load_kw": 10, "litres_per_hour": 1.6},
            ],
            "max_consecutive_dark": 2,
            "shops": [
                {"id": "pharmacy", "kw": 3, "type": "mandatory", "value_per_slot": [5] * 10},
                {"id": "tailor", "kw": 4, "type": "normal", "value_per_slot": [2, 2, 3, 3, 4, 4, 4, 4, 5, 5]},
                {"id": "mobile", "kw": 3, "type": "normal", "value_per_slot": [1, 1, 2, 2, 2, 3, 4, 6, 8, 8]},
                {"id": "photocopy", "kw": 2, "type": "normal", "value_per_slot": [3, 3, 5, 5, 4, 3, 2, 2, 1, 1]},
                {"id": "tea_stall", "kw": 1, "type": "normal", "value_per_slot": [2, 2, 2, 3, 3, 2, 2, 3, 3, 3]},
            ],
        }

        result = solve_roster(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["value_total"], 84)
        self.assertEqual(result["fuel_total_litres"], 8.0)
        self.assertTrue(validate_solution(payload, result))

    def test_mandatory_shops_are_powered_and_count_toward_value(self) -> None:
        payload = basic_payload()
        payload["shops"].append(
            {"id": "atm", "kw": 2, "type": "mandatory", "value_per_slot": [4] * 10}
        )

        result = solve_roster(payload)

        self.assertEqual(set(result["hours"][0]["powered"]), {"pharmacy", "atm"})
        self.assertEqual(result["value_total"], 9)

    def test_capacity_boundary_and_combined_load_fuel_tier(self) -> None:
        payload = basic_payload()
        payload["shops"] = [
            {"id": "exact_capacity", "kw": 10, "type": "mandatory", "value_per_slot": [7] * 10}
        ]

        result = solve_roster(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["hours"][0]["load_kw"], 10)
        self.assertEqual(result["hours"][0]["fuel_used_litres"], 1.6)
        self.assertEqual(result["value_total"], 7)

    def test_fuel_budget_boundary_is_exact_to_one_hundredth(self) -> None:
        payload = basic_payload()
        payload["grid_available"] = [False, False] + [True] * 8
        payload["fuel_budget_litres"] = 1.6
        payload["shops"] = [
            {"id": "small", "kw": 1, "type": "mandatory", "value_per_slot": [3] * 10}
        ]

        result = solve_roster(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["fuel_total_litres"], 1.6)
        self.assertTrue(validate_solution(payload, result))

    def test_consecutive_dark_limit_resets_after_powered_and_grid_hours(self) -> None:
        payload = basic_payload()
        payload["grid_available"] = [False, False, False, True, True, True, True, True, True, True]
        payload["fuel_budget_litres"] = 2.0
        payload["max_consecutive_dark"] = 1
        payload["fuel_table"] = [{"load_kw": 1, "litres_per_hour": 1.0}, {"load_kw": 10, "litres_per_hour": 1.0}]
        payload["shops"] = [
            {"id": "normal", "kw": 1, "type": "normal", "value_per_slot": [1] * 10}
        ]

        result = solve_roster(payload)

        self.assertEqual(result["status"], "ok")
        outage_on = [bool(hour["powered"]) for hour in result["roster"]]
        self.assertEqual(sum(outage_on), 2)
        self.assertTrue(all(outage_on[index] or outage_on[index + 1] for index in range(2)))
        self.assertEqual(len(result["per_shop_dark_hours"]["normal"]), 1)
        self.assertTrue(validate_solution(payload, result))

    def test_invalid_fractional_capacity_is_rejected_not_truncated(self) -> None:
        payload = basic_payload()
        payload["generator_capacity_kw"] = 10.9

        result = solve_roster(payload)

        self.assertEqual(result["status"], "invalid_input")
        self.assertIn("generator_capacity_kw", result["detail"])

        payload = basic_payload()
        payload["shops"][0]["kw"] = 3.5
        result = solve_roster(payload)

        self.assertEqual(result["status"], "invalid_input")
        self.assertIn("shops[0].kw", result["detail"])

    def test_duplicate_shop_ids_and_invalid_fuel_tables_are_rejected(self) -> None:
        duplicate_payload = basic_payload()
        duplicate_payload["shops"].append(dict(duplicate_payload["shops"][0]))
        duplicate = solve_roster(duplicate_payload)
        self.assertEqual(duplicate["status"], "invalid_input")
        self.assertIn("duplicate shop id", duplicate["detail"])

        invalid_fuel_payload = basic_payload()
        invalid_fuel_payload["fuel_table"][1]["load_kw"] = 4
        invalid_fuel = solve_roster(invalid_fuel_payload)
        self.assertEqual(invalid_fuel["status"], "invalid_input")
        self.assertIn("strictly increasing", invalid_fuel["detail"])

    def test_fractional_fuel_precision_and_values_are_rejected(self) -> None:
        payload = basic_payload()
        payload["fuel_budget_litres"] = 1.001
        result = solve_roster(payload)
        self.assertEqual(result["status"], "invalid_input")
        self.assertIn("fuel_budget_litres", result["detail"])

        payload = basic_payload()
        payload["shops"][0]["value_per_slot"][0] = -1
        result = solve_roster(payload)
        self.assertEqual(result["status"], "invalid_input")
        self.assertIn("value_per_slot", result["detail"])

        payload = basic_payload()
        payload["fuel_table"][0]["litres_per_hour"] = 1e16
        result = solve_roster(payload)
        self.assertEqual(result["status"], "invalid_input")
        self.assertIn("supported solver range", result["detail"])

    def test_no_outages_returns_zero_totals_and_an_empty_roster(self) -> None:
        payload = basic_payload()
        payload["grid_available"] = [True] * 10

        result = solve_roster(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["roster"], [])
        self.assertEqual(result["value_total"], 0)
        self.assertEqual(result["fuel_total_litres"], 0)
        self.assertTrue(all(hour["grid"] for hour in result["hours"]))

    def test_empty_shop_list_is_valid_during_an_outage(self) -> None:
        payload = basic_payload()
        payload["shops"] = []

        result = solve_roster(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["roster"]), 1)
        self.assertEqual(result["roster"][0]["powered"], [])
        self.assertEqual(result["roster"][0]["dark"], [])
        self.assertEqual(result["fuel_total_litres"], 0)

    def test_infeasible_mandatory_load_has_a_useful_conflict(self) -> None:
        payload = basic_payload()
        payload["generator_capacity_kw"] = 4
        payload["fuel_table"] = [{"load_kw": 4, "litres_per_hour": 0.8}]
        payload["shops"].append(
            {"id": "atm", "kw": 2, "type": "mandatory", "value_per_slot": [1] * 10}
        )

        result = solve_roster(payload)

        self.assertEqual(result["status"], "infeasible")
        self.assertIn("Mandatory shops", result["detail"])
        self.assertEqual(result["conflicts"][0]["rule"], "generator_capacity_kw")
        self.assertEqual(set(result["conflicts"][0]["shops"]), {"pharmacy", "atm"})

    def test_shop_larger_than_generator_is_never_powered_during_outage(self) -> None:
        payload = basic_payload()
        payload["shops"] = [
            {"id": "large", "kw": 11, "type": "normal", "value_per_slot": [9] * 10}
        ]

        result = solve_roster(payload)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["hours"][0]["powered"], [])
        self.assertEqual(result["hours"][0]["dark"][0]["id"], "large")
        self.assertIn("Capacity", result["hours"][0]["dark"][0]["reason"])

    def test_api_returns_http_200_for_infeasible_and_400_for_invalid(self) -> None:
        client = app.test_client()
        impossible = basic_payload()
        impossible["generator_capacity_kw"] = 2
        impossible["fuel_table"] = [{"load_kw": 2, "litres_per_hour": 0.4}]

        infeasible_response = client.post("/api/roster", json=impossible)
        self.assertEqual(infeasible_response.status_code, 200)
        self.assertEqual(infeasible_response.get_json()["status"], "infeasible")

        invalid_response = client.post("/api/roster", json={"grid_available": [True]})
        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.get_json()["status"], "invalid_input")

        missing_fields_response = client.post("/api/roster", json={})
        self.assertEqual(missing_fields_response.status_code, 400)
        self.assertIn("missing required field", missing_fields_response.get_json()["detail"])

        malformed_response = client.post(
            "/api/roster", data="{", content_type="application/json"
        )
        self.assertEqual(malformed_response.status_code, 400)
        self.assertEqual(malformed_response.get_json()["status"], "invalid_input")

    def test_api_serves_the_frontend_and_valid_sample(self) -> None:
        client = app.test_client()
        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Who Stays On", page.data)

        payload = json.loads((PROJECT_ROOT / "sample_input.json").read_text(encoding="utf-8"))
        response = client.post("/api/roster", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_solver_is_deterministic(self) -> None:
        payload = basic_payload()
        payload["shops"].append(
            {"id": "normal", "kw": 2, "type": "normal", "value_per_slot": [4] * 10}
        )

        first = solve_roster(payload)
        second = solve_roster(payload)

        self.assertEqual(first, second)

    def test_equal_value_rosters_use_less_fuel(self) -> None:
        payload = basic_payload()
        payload["generator_capacity_kw"] = 2
        payload["fuel_table"] = [
            {"load_kw": 1, "litres_per_hour": 0.5},
            {"load_kw": 2, "litres_per_hour": 1.0},
        ]
        payload["shops"] = [
            {"id": "efficient", "kw": 1, "type": "normal", "value_per_slot": [5] + [0] * 9},
            {"id": "high_load", "kw": 2, "type": "normal", "value_per_slot": [5] + [0] * 9},
        ]

        result = solve_roster(payload)

        self.assertEqual(result["value_total"], 5)
        self.assertEqual(result["hours"][0]["powered"], ["efficient"])
        self.assertEqual(result["fuel_total_litres"], 0.5)


if __name__ == "__main__":
    unittest.main()
