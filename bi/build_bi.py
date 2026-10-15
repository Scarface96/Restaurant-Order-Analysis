"""Export model-ready tables for Tableau and Power BI.

    python -m bi.build_bi

Writes bi/data/*.csv (a small star schema) and bi/kpis.json (the headline numbers your
dashboard should show, so you can check a Tableau or Power BI build against this repo).
Uses the same DuckDB database as the live report, so every figure matches it.
"""

import json
from pathlib import Path

from analysis import data as d

OUT = Path(__file__).resolve().parent


def tables(con) -> dict:
    dim_menu_item = con.sql(
        "SELECT menu_item_id, item_name, category, CAST(price AS DOUBLE) AS price FROM menu_items ORDER BY menu_item_id"
    ).df()
    # One row per item ordered. Lines with no item_id (a known gap in the source) are kept,
    # so order counts match the SQL, and flagged so they can be filtered out of item views.
    fact_order_line = con.sql(
        """
        SELECT order_details_id, order_id, order_date,
               CAST(order_time AS VARCHAR) AS order_time,
               EXTRACT(HOUR FROM order_time) AS order_hour,
               item_id,
               CASE WHEN item_id IS NULL THEN 1 ELSE 0 END AS missing_item
        FROM order_details ORDER BY order_details_id
        """
    ).df()
    dim_date = con.sql(
        """
        SELECT DISTINCT order_date AS date,
               dayname(order_date) AS weekday, isodow(order_date) AS weekday_no,
               monthname(order_date) AS month, month(order_date) AS month_no,
               CAST(date_trunc('week', order_date) AS DATE) AS week_start
        FROM order_details ORDER BY 1
        """
    ).df()
    return {"dim_menu_item": dim_menu_item, "dim_date": dim_date, "fact_order_line": fact_order_line}


def kpis(con) -> dict:
    q = d.quality(con)
    revenue = float(con.sql("SELECT SUM(price) FROM orders").fetchone()[0])
    items_sold = int(con.sql("SELECT COUNT(item_id) FROM order_details").fetchone()[0])
    top = d.items(con).iloc[0]
    return {
        "Revenue": round(revenue, 2),
        "Orders": int(q["orders"]),
        "Items sold": items_sold,
        "Average order value": round(revenue / q["orders"], 2),
        "Items per order": round(items_sold / q["orders"], 2),
        "Order lines with no item (data gap)": int(q["lines_without_item"]),
        "Menu items": int(q["menu_items"]),
        "Most ordered item": f"{top['item_name']} ({int(top['sold']):,})",
        "Date range": f"{q['first_day']:%Y-%m-%d} to {q['last_day']:%Y-%m-%d}",
    }


def build(out: Path = OUT) -> dict:
    con = d.connect()
    t = tables(con)
    (out / "data").mkdir(parents=True, exist_ok=True)
    for name, df in t.items():
        df.to_csv(out / "data" / f"{name}.csv", index=False, date_format="%Y-%m-%d")
    k = kpis(con)
    (out / "kpis.json").write_text(json.dumps(k, indent=2) + "\n")
    return {"tables": t, "kpis": k}


if __name__ == "__main__":
    res = build()
    for name, df in res["tables"].items():
        print(f"{name}: {len(df):,} rows")
    print(json.dumps(res["kpis"], indent=2))
