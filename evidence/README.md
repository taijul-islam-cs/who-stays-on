# Verification evidence

All JSON outputs in this folder were generated from the corresponding input with the current solver. `boundary_input.json` spends exactly the full 0.80 L budget on a mandatory shop in one outage hour; `boundary_output.json` is the actual result and confirms the exact budget boundary is accepted.

`regression_input.json` exercises the previously observed fractional-number coercion bug. The earlier implementation returned `ok` after truncating the generator capacity from 10.9 to 10 kW and the shop load from 3.5 to 3 kW. The corrected output is in `regression_corrected_output.json` and rejects the capacity with a field-specific `invalid_input` detail.

The old implementation's full response body was not retained. `regression_old_failure.json` records only the baseline behavior that was actually observed; it deliberately does not reconstruct or fabricate the old response. The unavailable minute-150 update input is not represented as evidence.
