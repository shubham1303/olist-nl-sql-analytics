# Evaluation

The NL-to-SQL benchmark ([ADR 0006](../docs/adr/0006-evaluation-methodology.md),
comparison rules in [ADR 0017](../docs/adr/0017-benchmark-comparison-and-verification.md),
human-written items in [ADR 0018](../docs/adr/0018-human-written-benchmark-items.md)).

| Path | What |
|---|---|
| `benchmark/dev.yaml` | 35 development questions (5 human-written): the only split used while tuning |
| `benchmark/test.yaml` | 23 held-out questions (3 human-written): checkpoint runs only, never tuned on |
| `results/` | One JSON record + markdown report per run, committed |
| `triage/<run_id>.yaml` | Human failure categories for a run (optional) |

Commands run from `backend/` and need the local database (except `check`):

```sh
uv run python -m olist_nlsql.evaluation check                  # structure + validator, no db
uv run python -m olist_nlsql.evaluation snapshot --split dev   # store reference results
uv run python -m olist_nlsql.evaluation show --split dev dev-007
uv run python -m olist_nlsql.evaluation verify --split dev --by "Your Name" dev-007
uv run python -m olist_nlsql.evaluation run --split dev        # real model (Bedrock)
uv run python -m olist_nlsql.evaluation run --split dev --repeat 3
uv run python -m olist_nlsql.evaluation compare --before <3 records> --after <3 records>
uv run python -m olist_nlsql.evaluation run --split test --checkpoint "end of phase 4"
uv run python -m olist_nlsql.evaluation report ../eval/results/<run_id>.json
```

## Verifying an item

An item is ground truth only after a person has checked it. Until then it is run but
not scored. For each item:

1. `show` it and read the question, notes, SQL and result.
2. Check that the SQL answers the question **as a business user would mean it**, using
   the catalog's metric definitions ([metrics.md](../docs/metrics.md)): right relation,
   right population (revenue orders, delivered orders…), right time window, right
   grain.
3. Check that the result looks right (magnitudes, row count, no NULL rankings).
4. Check that the comparison options fit: `order_matters` for rankings and series,
   `allow_percent` for rates, and a tolerance suited to the value.
5. `verify` it. If you change anything, re-run `snapshot` first. Editing the question,
   SQL, options or result after verifying un-verifies the item automatically.

Snapshots must come from a database built from the pinned Kaggle files
(`dbsetup download` + `build`).

## Runs

- `run` writes `results/<run_id>.json` and `.md`. Commit both. Metrics in reports are
  computed from the JSON, never typed in.
- `--fake-reference` answers each question with its own reference SQL. It's a harness
  self-test that should score 100%. Its reports are marked as such and must not be
  quoted as accuracy. Write them elsewhere with `--results-dir`.
- Test-split runs need `--checkpoint "reason"` and are always recorded. Don't change
  anything because of a test-split failure. They are single runs (`--repeat` is refused).
- Each item records every model call: the SQL as written, the outcome and the validator
  codes (record version 2). The report lists attempts that did not pass.
- A run is "dirty" only if tracked code or data changed; uncommitted files in `results/`
  don't count.

## Before/after claims

One dev run can move by a couple of items with nothing changed (four identical runs
scored 30, 30, 30, 28). A claim that a change helped needs at least three runs per side:

1. `run --split dev --repeat 3` before and after the change (records are suffixed
   `_r1of3` … `_r3of3`). Reuse "before" runs when nothing else changed.
2. `compare --before … --after …` prints the per-run counts, mean, min and max, the
   items that weren't correct every time, and a verdict: **improvement** when the mean
   rises and the minimum doesn't fall, **regression** when the mean falls and the
   maximum doesn't rise, otherwise **no clear difference**. It refuses held-out runs,
   fake-model runs, and runs over different benchmark versions or items.
3. Put the comparison in [CHANGELOG.md](CHANGELOG.md).

A 35-item run costs about 250k tokens (about 90% read from cache) and 65–100 s.

## Triage

Stage failures (generation, validation, execution) are categorised automatically.
Wrong results get a guess (`wrong_relation_or_join` when the relations differ,
otherwise `untriaged_mismatch`), and validator rejections still need splitting into
correct and false rejections. Record your call in `triage/<run_id>.yaml`:

```yaml
dev-007:
  category: wrong_filter_or_time_window   # see runner.CATEGORIES
  note: used delivered orders only
```

Then re-run `report` on the JSON.
