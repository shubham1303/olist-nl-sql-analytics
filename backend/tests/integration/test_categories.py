"""English category names everywhere in the analytics layer."""

from tests.integration.helpers import Conn, row, scalar

PROJECT_TRANSLATIONS = {
    "home_comfort",
    "pc_gamer",
    "small_appliances_kitchen_and_food_preparers",
}


def allowed_categories(owner: Conn) -> set[str]:
    olist = {c for (c,) in owner.execute(
        "SELECT product_category_name_english FROM raw.product_category_name_translation"
    )}  # fmt: skip
    return (olist - {"home_confort"}) | PROJECT_TRANSLATIONS | {"uncategorized"}


def portuguese_only_names(owner: Conn) -> set[str]:
    portuguese = {c for (c,) in owner.execute(
        "SELECT DISTINCT product_category_name FROM raw.products WHERE product_category_name IS NOT NULL"
    )}  # fmt: skip
    return portuguese - allowed_categories(owner)


def test_every_category_is_english(owner: Conn, reader: Conn) -> None:
    allowed = allowed_categories(owner)
    for view in ["products", "order_items", "order_categories"]:
        values = {c for (c,) in reader.execute(f"SELECT DISTINCT product_category FROM {view}")}
        assert values <= allowed, (view, values - allowed)
        assert not values & portuguese_only_names(owner), view


def test_no_product_is_left_untranslated(reader: Conn) -> None:
    sources: dict[str, int] = dict(
        reader.execute("SELECT category_translation_source, count(*) FROM products GROUP BY 1")
    )
    assert sources == {"olist": 32_217, "project": 124, "uncategorized": 610}


def test_project_translations(reader: Conn) -> None:
    counts: dict[str, int] = dict(
        reader.execute(
            """SELECT product_category, count(*) FROM products
               WHERE category_translation_source = 'project' GROUP BY 1"""
        )
    )
    assert counts == {
        "home_comfort": 111,
        "pc_gamer": 3,
        "small_appliances_kitchen_and_food_preparers": 10,
    }


def test_source_typo_is_not_exposed(reader: Conn) -> None:
    assert (
        scalar(reader, "SELECT count(*) FROM products WHERE product_category = 'home_confort'") == 0
    )


def test_category_count(reader: Conn) -> None:
    # 73 source categories + 'uncategorized'.
    assert scalar(reader, "SELECT count(DISTINCT product_category) FROM products") == 74


def test_top_category_by_revenue(reader: Conn) -> None:
    category, _ = row(
        reader,
        "SELECT product_category, sum(revenue) FROM order_categories GROUP BY 1 ORDER BY 2 DESC NULLS LAST LIMIT 1",
    )
    assert category == "health_beauty"


def test_category_revenue_matches_item_level(reader: Conn) -> None:
    mismatches = scalar(
        reader,
        """SELECT count(*) FROM
             (SELECT product_category, sum(revenue) r FROM order_categories GROUP BY 1) a
           FULL JOIN
             (SELECT product_category, sum(revenue) r FROM order_items GROUP BY 1) b
           USING (product_category)
           WHERE a.r IS DISTINCT FROM b.r""",
    )
    assert mismatches == 0
