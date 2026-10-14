# 0018. Human-written benchmark items (34 dev / 23 held-out)

- Status: Accepted
- Date: 2026-10-11
- Amends [ADR 0006](0006-evaluation-methodology.md): the split sizes change from
  30 / 20 to 34 / 23. Everything else in 0006 and
  [ADR 0017](0017-benchmark-comparison-and-verification.md) still applies.

## Context

The 50 original items were drafted with Claude's help and are answered by a Claude
model. Their references are human-verified, but the questions themselves may share the
model's phrasing habits. By the start of Phase 5 the dev split was saturated: four runs
on prompt v2 scored 30, 30, 30 and 28, and the only misses were a rounding artefact.
Dev no longer pointed at anything to improve, and the held-out result could not show
how the system handles questions phrased by a person.

Eight harder questions were written by hand (cohorts, revenue concentration,
month-over-month change, time between purchases, thresholds on rankings).

## Decision

- Add seven of them: **four to dev** (dev-031 to dev-034) and **three to held-out**
  (test-021 to test-023), giving 34 dev and 23 held-out items. The eighth (late vs
  on-time review averages) is dropped because it nearly duplicates test-008. In dev it
  would leak a held-out item into tuning; in test it would add nothing.
- The questions are kept as written. Reference SQL is drafted and verified the same way
  as for the original items. Where a question allows several readings, the reference
  takes the reading the catalog and earlier items support, and the notes record the
  alternatives and their values. Tolerances accept harmless variants (for example
  calendar days vs exact elapsed time) and nothing more.
- Each item is tagged `human_written` and its notes say so.
- `EXPECTED_SIZES` in the benchmark loader changes to 34 / 23.

## Consequences

- Held-out results before and after this change cover different item sets. Compare
  them on the original 20 items, which every run record lists per item, and report the
  three human-written items separately.
- The dev baseline for later Phase 5 work is a fresh run on 34 items. Earlier 30-item
  dev runs stay valid for the changes they measured.
- The benchmark is still small. Each held-out item is worth about 4.3 points, so
  differences of one or two items are not meaningful on their own.

## Amendment (2026-10-13, Phase 9): dev-035

The owner tried 15 of their own questions on the live site. One of them failed every
time (validator rejection), and it became **dev-035**, which takes dev to 35 items.
Two others weren't added:

- The "delays vs reviews within category and state" question has no single correct
  number as worded: it doesn't fix a group size or a summary. It's judged on the live
  site only.
- Two questions nearly duplicate held-out items (test-008, test-021), so they stay out
  of dev to keep the held-out split clean.
