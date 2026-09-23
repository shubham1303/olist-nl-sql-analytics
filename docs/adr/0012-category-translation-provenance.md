# 0012. Category translations: raw unchanged, corrections in the curated layer with provenance

- Status: Accepted
- Date: 2026-09-23

## Context

Olist's translation table maps 71 Portuguese category names to English, but it has
gaps and a typo:
- `pc_gamer` (3 products) and `portateis_cozinha_e_preparadores_de_alimentos` (10
  products) have no translation.
- `casa_conforto` translates to `home_confort`, while its sibling category is
  `home_comfort_2`.

The model should only ever work with English names, and changes to source data must
stay traceable.

## Decision

- **Raw source values stay unchanged.** `raw.products` and
  `raw.product_category_name_translation` are faithful copies of the CSVs.
- **Corrections and manual translations live only in the curated layer**, in the
  `analytics_internal.product_category_map` view. That view is hidden from the model
  and from `analytics_reader`.
- For every category the map records:
  - the source value (`product_category_name`, Portuguese)
  - Olist's own English value, if any (`source_english_name`)
  - the normalized value (`product_category`)
  - `translation_source`: `olist` or `project`
  - `provenance`: the reason for the entry
- The manual entries:

| Source value | Olist English | Normalized value | Provenance |
|---|---|---|---|
| `casa_conforto` | `home_confort` | `home_comfort` | Corrects the source typo; the sibling category is `home_comfort_2` |
| `pc_gamer` | *(none)* | `pc_gamer` | Missing from the source table; the source name is already English |
| `portateis_cozinha_e_preparadores_de_alimentos` | *(none)* | `small_appliances_kitchen_and_food_preparers` | Missing; follows Olist's naming of `portateis_casa_forno_e_cafe` → `small_appliances_home_oven_and_coffee` |

- Products with no category are labelled `uncategorized`.
- Portuguese is used only as a last-resort fallback, and today no category needs it.

## Consequences

- Every category value in `analytics` is English, and tests enforce this.
- A test checks that each manual entry keeps its source value and provenance, and that
  the raw values are untouched.
- Adding or changing a manual translation means editing the view's VALUES list and
  this ADR's table together.
- `products.category_translation_source` lets an analysis separate project-supplied
  names from Olist's.
