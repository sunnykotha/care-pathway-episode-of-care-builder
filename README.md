# Care Pathway and Episode-of-Care Builder

A Python project for assigning healthcare claims to episodes, aggregating costs, comparing benchmarks, tracking complications, and summarizing outcomes by provider.

## Setup

Install dependencies using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the worked example

```powershell
$env:PYTHONPATH = "$PWD\src"; .\.venv\Scripts\python.exe examples\run_example.py
```

The knee-replacement example includes preoperative imaging, hospital costs, an infection-related readmission, rehabilitation, a benchmark comparison, and provider/facility attribution. All amounts and identifiers are illustrative.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Modules

- `episode_builder.py`: builds episode definitions from index-procedure claims and supplied admission/discharge dates.
- `episode_windows.py`: episode date windows.
- `claim_assignment.py`: claim eligibility and overlapping episode assignment.
- `cost_analysis.py`: cost buckets, benchmark comparison, and statistical outlier detection.
- `episode_details.py`: complication tracking and provider/facility attribution.
- `episode_lifecycle.py`: readmissions, transfers, late claims, and patient-death tracking.
- `provider_summary.py`: provider-level episode and cost summaries.

## Important behavior

- Each claim is assigned to at most one eligible episode; claims outside the configured window are excluded.
- Temporal phases (preoperative, hospital, post-acute) differ from financial buckets (surgery, facility, rehab, readmissions).
- A readmission is not automatically a complication; complication events must be provided explicitly.
- Statistical outlier detection needs multiple episode reports; a single episode can still be compared with its benchmark.

This is a task implementation, not a production clinical or reimbursement system. Validate business rules and benchmarks before real-world use.
