"""Load the restaurant MySQL dump into DuckDB and analyse orders."""

from itertools import combinations
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DUMP = ROOT / "create_restaurant_db.sql"


def connect(path: Path = DUMP) -> duckdb.DuckDBPyConnection:
    """Run the dump in an in-memory DuckDB. The MySQL-only schema lines are skipped."""
    sql = path.read_text(encoding="utf-8")
    keep = [line for line in sql.splitlines() if not line.strip().upper().startswith(("DROP SCHEMA", "CREATE SCHEMA", "USE "))]
    con = duckdb.connect()
    con.execute("\n".join(keep))
    con.execute(
        """
        CREATE VIEW orders AS
        SELECT od.order_details_id, od.order_id, od.order_date, od.order_time, od.item_id,
               mi.item_name, mi.category, CAST(mi.price AS DOUBLE) AS price
        FROM order_details od LEFT JOIN menu_items mi ON od.item_id = mi.menu_item_id
        """
    )
    return con


def quality(con) -> dict:
    return con.sql(
        """
        SELECT COUNT(*) AS order_lines,
               COUNT(DISTINCT order_id) AS orders,
               SUM(CASE WHEN item_id IS NULL THEN 1 ELSE 0 END) AS lines_without_item,
               MIN(order_date) AS first_day, MAX(order_date) AS last_day,
               (SELECT COUNT(*) FROM menu_items) AS menu_items
        FROM order_details
        """
    ).df().iloc[0].to_dict()


# The project's own queries (res.sql and "restaurant analysis.sql"), unchanged apart from
# LIMITs for display. Each is shown on the page beside its result.
QUERIES = [
    ("Menu", "How many items are on the menu, and how do they break down by cuisine?",
     "SELECT category,\n       COUNT(menu_item_id) AS num_dishes,\n       ROUND(AVG(price), 2) AS avg_price\nFROM menu_items\nGROUP BY category\nORDER BY avg_price DESC;"),
    ("Menu", "Cheapest and most expensive items",
     "(SELECT item_name, category, price FROM menu_items ORDER BY price LIMIT 1)\nUNION ALL\n(SELECT item_name, category, price FROM menu_items ORDER BY price DESC LIMIT 1);"),
    ("Orders", "What date range does the data cover, and how many orders?",
     "SELECT MIN(order_date) AS first_day,\n       MAX(order_date) AS last_day,\n       COUNT(DISTINCT order_id) AS orders,\n       COUNT(*) AS items_ordered\nFROM order_details;"),
    ("Orders", "Orders with more than 12 items",
     "SELECT COUNT(*) AS big_orders\nFROM (\n    SELECT order_id, COUNT(item_id) AS num_items\n    FROM order_details\n    GROUP BY order_id\n    HAVING num_items > 12\n) AS t;"),
    ("Behaviour", "Most and least ordered items",
     "SELECT item_name, category, COUNT(order_details_id) AS num_purchases\nFROM order_details od LEFT JOIN menu_items mi\n  ON od.item_id = mi.menu_item_id\nWHERE item_name IS NOT NULL\nGROUP BY item_name, category\nORDER BY num_purchases DESC;"),
    ("Behaviour", "Top 5 orders by total spend",
     "SELECT order_id, SUM(price) AS total_spend\nFROM order_details od LEFT JOIN menu_items mi\n  ON od.item_id = mi.menu_item_id\nGROUP BY order_id\nORDER BY total_spend DESC\nLIMIT 5;"),
    ("Behaviour", "What did the top 5 orders contain?",
     "SELECT category, COUNT(item_id) AS num_items\nFROM order_details od LEFT JOIN menu_items mi\n  ON od.item_id = mi.menu_item_id\nWHERE order_id IN (440, 2075, 1957, 330, 2675)\nGROUP BY category\nORDER BY num_items DESC;"),
]


def run_queries(con):
    return [(stage, title, sql, con.sql(sql).df()) for stage, title, sql in QUERIES]


# --------------------------------------------------------------- analysis ----
def items(con) -> pd.DataFrame:
    return con.sql(
        """
        SELECT item_name, category, price, sold, sold * price AS revenue
        FROM (
            SELECT mi.item_name, mi.category, CAST(mi.price AS DOUBLE) AS price, COUNT(od.order_details_id) AS sold
            FROM menu_items mi LEFT JOIN order_details od ON od.item_id = mi.menu_item_id
            GROUP BY mi.item_name, mi.category, mi.price
        ) ORDER BY sold DESC
        """
    ).df()


def menu_engineering(it: pd.DataFrame) -> pd.DataFrame:
    """Classic menu-engineering quadrants.

    Popularity threshold: 70% of an equal share of sales (Kasavana & Smith).
    Value threshold: the average price, weighted by how often items sell.
    (The data has prices but no food costs, so price stands in for contribution.)
    """
    t = it.copy()
    t["mix"] = t["sold"] / t["sold"].sum()
    pop_line = 0.7 / len(t)
    price_line = (t["price"] * t["sold"]).sum() / t["sold"].sum()
    popular = t["mix"] >= pop_line
    pricey = t["price"] >= price_line
    t["class"] = pd.Series(pd.NA, index=t.index, dtype="object")
    t.loc[popular & pricey, "class"] = "Star"
    t.loc[popular & ~pricey, "class"] = "Plowhorse"
    t.loc[~popular & pricey, "class"] = "Puzzle"
    t.loc[~popular & ~pricey, "class"] = "Dog"
    t.attrs.update(pop_line=pop_line, price_line=price_line)
    return t


def pairs(con, min_orders: int = 30) -> pd.DataFrame:
    """Items bought in the same order: support, confidence and lift for every pair."""
    lines = con.sql("SELECT order_id, item_name FROM orders WHERE item_name IS NOT NULL").df()
    baskets = lines.groupby("order_id")["item_name"].apply(lambda s: sorted(set(s)))
    n = len(baskets)
    item_count = lines.drop_duplicates(["order_id", "item_name"])["item_name"].value_counts()
    counts: dict[tuple[str, str], int] = {}
    for basket in baskets:
        for a, b in combinations(basket, 2):
            counts[(a, b)] = counts.get((a, b), 0) + 1
    rows = []
    for (a, b), together in counts.items():
        if together < min_orders:
            continue
        pa, pb, pab = item_count[a] / n, item_count[b] / n, together / n
        rows.append({"item_a": a, "item_b": b, "orders_together": together, "support": pab,
                     "conf_a_to_b": pab / pa, "conf_b_to_a": pab / pb, "lift": pab / (pa * pb)})
    return pd.DataFrame(rows).sort_values("lift", ascending=False).reset_index(drop=True)


def basket_sizes(con) -> pd.DataFrame:
    return con.sql(
        """
        SELECT items, COUNT(*) AS orders FROM (
            SELECT order_id, COUNT(item_id) AS items FROM order_details GROUP BY order_id
        ) GROUP BY items ORDER BY items
        """
    ).df()


def busy(con) -> pd.DataFrame:
    """Average orders per hour for each weekday."""
    return con.sql(
        """
        WITH o AS (
            SELECT DISTINCT order_id, order_date, EXTRACT(HOUR FROM order_time) AS hour FROM order_details
        ), days AS (
            SELECT dayofweek(order_date) AS dow, COUNT(DISTINCT order_date) AS n_days FROM o GROUP BY 1
        )
        SELECT dayname(o.order_date) AS weekday, dayofweek(o.order_date) AS dow, hour,
               COUNT(*) / ANY_VALUE(n_days) AS avg_orders
        FROM o JOIN days d ON dayofweek(o.order_date) = d.dow
        GROUP BY ALL ORDER BY dow, hour
        """
    ).df()


def daily(con) -> pd.DataFrame:
    return con.sql(
        """
        SELECT order_date, COUNT(DISTINCT order_id) AS orders, SUM(price) AS revenue
        FROM orders GROUP BY 1 ORDER BY 1
        """
    ).df()


def explorer_payload(p: pd.DataFrame) -> dict:
    """For each item, the items most often in the same order, by lift."""
    out: dict[str, list] = {}
    for r in p.itertuples():
        out.setdefault(r.item_a, []).append([r.item_b, round(r.conf_a_to_b, 4), round(r.lift, 3), r.orders_together])
        out.setdefault(r.item_b, []).append([r.item_a, round(r.conf_b_to_a, 4), round(r.lift, 3), r.orders_together])
    return {k: sorted(v, key=lambda x: -x[2])[:8] for k, v in sorted(out.items())}
