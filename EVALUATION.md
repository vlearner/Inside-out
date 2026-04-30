# Evaluation (DeepEval + pytest)

This project now includes a **DeepEval-based evaluation matrix** that runs with `pytest` and writes results in **JSON** format.

## Files

- `eval/cases.json` — evaluation cases dataset.
- `tests/test_deepeval_matrix.py` — pytest evaluation suite powered by DeepEval.
- `eval/results/latest.json` — generated matrix report (created after a run).

## Run

```bash
pytest tests/test_deepeval_matrix.py -q
```

## JSON matrix format

`eval/results/latest.json` contains:

- `generated_at`
- `tool`
- `summary`
  - `total`
  - `passed`
  - `failed`
  - `avg_score`
- `rows[]`
  - `case_id`
  - `prompt`
  - `actual_output`
  - `expected_output`
  - `score`
  - `passed`
  - `reason`

## Notes

- The test is marked with `@pytest.mark.evaluation`.
- If `deepeval` is not installed, pytest will skip this file.
