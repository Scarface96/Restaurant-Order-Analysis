import pandas as pd
import pytest

from analysis import data


@pytest.fixture(scope="module")
def con():
    return data.connect()


def test_dump_loads(con):
    q = data.quality(con)
    assert q["order_lines"] == 12234 and q["orders"] == 5370 and q["menu_items"] == 32


def test_project_queries_run(con):
    res = data.run_queries(con)
    assert len(res) == len(data.QUERIES)
    best = res[4][3].iloc[0]
    assert best["item_name"] == "Hamburger" and best["num_purchases"] == 622


def test_menu_engineering_classes(con):
    me = data.menu_engineering(data.items(con))
    assert set(me["class"]) == {"Star", "Plowhorse", "Puzzle", "Dog"}
    assert me["mix"].sum() == pytest.approx(1)
    dog = me[me["class"] == "Dog"]
    assert (dog["price"] < me.attrs["price_line"]).all() and (dog["mix"] < me.attrs["pop_line"]).all()


def test_pair_metrics_are_consistent(con):
    p = data.pairs(con, min_orders=30)
    assert (p["orders_together"] >= 30).all()
    assert p["lift"].is_monotonic_decreasing
    # lift = confidence(A->B) / P(B), so the two directions agree
    r = p.iloc[0]
    assert r["conf_a_to_b"] / r["support"] == pytest.approx(r["conf_b_to_a"] / r["support"] * (r["conf_a_to_b"] / r["conf_b_to_a"]))


def test_explorer_payload_is_symmetric(con):
    payload = data.explorer_payload(data.pairs(con))
    a, partners = next(iter(payload.items()))
    b = partners[0][0]
    assert any(x[0] == a for x in payload[b])
