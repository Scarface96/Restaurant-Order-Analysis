"""Run the restaurant analysis and write the website to site/index.html.

    python -m analysis.build
"""

import html

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import data
from .report import AXIS, BLUE, GRID, INK_2, MUTED, ORANGE, SEQUENTIAL, SERIES, Report, money, style, table_html, to_json

REPO = "Scarface96/Restaurant-Order-Analysis"
CLASSES = [("Star", "circle"), ("Plowhorse", "square"), ("Puzzle", "diamond"), ("Dog", "x")]
CUISINES = ["American", "Asian", "Mexican", "Italian"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def daily_figure(d: pd.DataFrame) -> go.Figure:
    d = d.copy()
    d["avg7"] = d["orders"].rolling(7, center=True).mean()
    fig = go.Figure()
    fig.add_bar(x=d["order_date"], y=d["orders"], name="Orders that day", marker_color="#c9dcf4",
                hovertemplate="%{x|%a %d %b}<br>%{y} orders<extra></extra>")
    fig.add_scatter(x=d["order_date"], y=d["avg7"], name="7-day average", mode="lines", line=dict(color=BLUE, width=2),
                    hovertemplate="%{x|%d %b}<br>7-day average %{y:.0f}<extra></extra>")
    style(fig, height=340)
    fig.update_yaxes(title="Orders", rangemode="tozero")
    fig.update_layout(bargap=0.15)
    return fig


def busy_figure(b: pd.DataFrame) -> go.Figure:
    p = b.pivot(index="weekday", columns="hour", values="avg_orders").reindex(DAYS).fillna(0)
    p = p.loc[:, [h for h in p.columns if 11 <= h <= 22]]
    fig = go.Figure(go.Heatmap(
        z=p.values, x=[f"{h}:00" for h in p.columns], y=p.index,
        colorscale=[[i / (len(SEQUENTIAL) - 1), c] for i, c in enumerate(SEQUENTIAL)], xgap=2, ygap=2,
        colorbar=dict(title=dict(text="Orders<br>per hour"), thickness=12, outlinewidth=0),
        hovertemplate="%{y} %{x}<br>%{z:.1f} orders on average<extra></extra>",
    ))
    style(fig, height=360, legend=False)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(side="top")
    return fig


def menu_figure(me: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for i, (cls, symbol) in enumerate(CLASSES):
        g = me[me["class"] == cls]
        fig.add_scatter(
            x=g["sold"], y=g["price"], mode="markers", name=f"{cls}s ({len(g)})",
            marker=dict(color=SERIES[i], symbol=symbol, size=13, line=dict(color="#fcfcfb" if symbol != "x" else SERIES[i], width=2)),
            customdata=np.stack([g["item_name"], g["category"], g["revenue"]], axis=1),
            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>%{x} sold at $%{y:.2f}<br>Revenue $%{customdata[2]:,.0f}<extra>" + cls + "</extra>",
        )
    pop_x = me.attrs["pop_line"] * me["sold"].sum()
    fig.add_vline(x=pop_x, line=dict(color=AXIS, dash="dot", width=1.5))
    fig.add_hline(y=me.attrs["price_line"], line=dict(color=AXIS, dash="dot", width=1.5))
    corners = [("Puzzles: pricey, slow", 0.01, 0.99, "left", "top"), ("Stars: pricey, popular", 0.99, 0.99, "right", "top"),
               ("Dogs: cheap, slow", 0.01, 0.01, "left", "bottom"), ("Plowhorses: cheap, popular", 0.99, 0.01, "right", "bottom")]
    for text, x, y, xa, ya in corners:
        fig.add_annotation(text=text, x=x, y=y, xref="paper", yref="paper", xanchor=xa, yanchor=ya, showarrow=False, font=dict(size=12, color=MUTED))
    for name in ["Shrimp Scampi", "Chicken Tacos", "Hamburger", "Edamame", "Korean Beef Bowl"]:
        r = me[me["item_name"] == name].iloc[0]
        fig.add_annotation(x=r["sold"], y=r["price"], text=name, showarrow=False, yshift=14, font=dict(size=11, color=INK_2))
    style(fig, height=500)
    fig.update_xaxes(title="Times ordered, Jan–Mar 2023", showgrid=True, gridcolor=GRID)
    fig.update_yaxes(title="Price", tickprefix="$")
    return fig


def cuisine_figure(it: pd.DataFrame) -> go.Figure:
    c = it.groupby("category").agg(sold=("sold", "sum"), revenue=("revenue", "sum"), dishes=("item_name", "size"), avg_price=("price", "mean")).reindex(CUISINES)
    fig = go.Figure(go.Bar(x=c.index, y=c["revenue"], marker_color=BLUE,
                           customdata=np.stack([c["sold"], c["dishes"], c["avg_price"]], axis=1),
                           hovertemplate="%{x}<br>Revenue $%{y:,.0f}<br>%{customdata[0]:,} items from %{customdata[1]} dishes<br>Average menu price $%{customdata[2]:.2f}<extra></extra>"))
    style(fig, height=320, legend=False)
    fig.update_yaxes(tickprefix="$", title="Revenue, Jan–Mar 2023")
    return fig


def basket_figure(bs: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(x=bs["items"], y=bs["orders"], marker_color=BLUE, hovertemplate="%{y:,} orders with %{x} items<extra></extra>"))
    style(fig, height=300, legend=False)
    fig.update_xaxes(title="Items in the order", dtick=1)
    fig.update_yaxes(title="Orders")
    return fig


def pairs_figure(p: pd.DataFrame) -> go.Figure:
    t = p.head(12).iloc[::-1]
    labels = t["item_a"] + " + " + t["item_b"]
    fig = go.Figure(go.Bar(x=t["lift"] - 1, y=labels, orientation="h", marker_color=BLUE, base=1,
                           customdata=np.stack([t["lift"], t["orders_together"]], axis=1),
                           hovertemplate="%{y}<br>%{customdata[0]:.2f}× as often as chance<br>Together in %{customdata[1]} orders<extra></extra>"))
    fig.add_vline(x=1, line=dict(color=INK_2, width=1.5), annotation_text="Chance", annotation_position="top", annotation_font_color=MUTED)
    style(fig, height=440, legend=False)
    fig.update_xaxes(title="Lift: how much more often than chance the pair appears together", showgrid=True, gridcolor=GRID, range=[0.7, 1.7])
    fig.update_yaxes(showgrid=False, tickfont=dict(size=12))
    return fig


def queries_html(results) -> str:
    out = []
    for stage, title, sql, df in results:
        shown = df.head(8).copy()
        for col in shown.columns:
            if pd.api.types.is_datetime64_any_dtype(shown[col]):
                shown[col] = shown[col].dt.strftime("%Y-%m-%d")
        rows = f'<p class="note">{len(df):,} rows; first 8 shown.</p>' if len(df) > 8 else ""
        out.append(f'<div class="qa"><h3>{html.escape(stage)}: {html.escape(title)}</h3><pre class="sql">{html.escape(sql)}</pre><div>{table_html(shown)}{rows}</div></div>')
    return "".join(out)


EXPLORER = """
<form class="controls" onsubmit="return false"><label>Dish<select id="pair-item"></select></label></form>
<figure class="chart"><div id="pair-chart" style="height:360px"></div></figure>
"""


def explorer_js(payload: dict) -> str:
    return f"""
(function(){{
const P={to_json(payload)};
const sel=document.getElementById('pair-item');
Object.keys(P).forEach(k=>sel.add(new Option(k,k)));
sel.value=P['Hamburger']?'Hamburger':Object.keys(P)[0];
function draw(){{
  const rows=P[sel.value].slice().reverse();
  Plotly.react('pair-chart',[{{type:'bar',orientation:'h',y:rows.map(r=>r[0]),x:rows.map(r=>r[2]-1),base:1,marker:{{color:rows.map(r=>r[2]>=1?'{BLUE}':'#b9b8b1')}},
    customdata:rows.map(r=>[r[1],r[3],r[2]]),hovertemplate:'%{{y}}<br>In %{{customdata[0]:.0%}} of orders with '+sel.value+'<br>%{{customdata[2]:.2f}}× chance, %{{customdata[1]}} orders together<extra></extra>'}}],
   {{height:360,margin:{{l:8,r:16,t:28,b:8}},paper_bgcolor:'#fcfcfb',plot_bgcolor:'#fcfcfb',font:{{family:'"Public Sans",system-ui,sans-serif',size:13,color:'{INK_2}'}},
    title:{{text:'Dishes most often ordered with '+sel.value,font:{{size:14}},x:0,xanchor:'left'}},
    xaxis:{{title:{{text:'Lift (1 = chance)'}},gridcolor:'{GRID}',range:[0.7,1.7],automargin:true}},yaxis:{{automargin:true}},
    shapes:[{{type:'line',x0:1,x1:1,y0:0,y1:1,yref:'paper',line:{{color:'{INK_2}',width:1.5}}}}]}},{{displaylogo:false,responsive:true}});
}}
sel.addEventListener('input',draw); draw();
}})();
"""


def main(out="site/index.html"):
    con = data.connect()
    q = data.quality(con)
    results = data.run_queries(con)
    it = data.items(con)
    me = data.menu_engineering(it)
    p = data.pairs(con)
    bs = data.basket_sizes(con)
    b = data.busy(con)
    d = data.daily(con)
    rev = it["revenue"].sum()
    cz = it.groupby("category")[["revenue", "sold"]].sum()
    dogs = me[me["class"] == "Dog"].sort_values("sold")
    puzzles = me[me["class"] == "Puzzle"].sort_values("sold")
    noon = b[b["hour"] == 12].set_index("weekday")["avg_orders"]
    midweek = noon[["Tuesday", "Wednesday"]].mean()
    others = noon.drop(["Tuesday", "Wednesday"]).mean()
    top5 = results[6][3].set_index("category")["num_items"]
    small = bs.loc[bs["items"].between(1, 2), "orders"].sum() / bs["orders"].sum()
    real_orders = int(bs.loc[bs["items"] > 0, "orders"].sum())

    r = Report(
        title=f"{len(dogs)} of {int(q['menu_items'])} dishes are both cheap and rarely ordered. They're the first candidates for the new menu to drop.",
        project="Restaurant Order Analysis",
        summary=(
            f"The restaurant served {real_orders:,} orders and {money(rev)} of food in the first quarter of 2023. "
            "The project's SQL questions are answered below with real results, and Python adds menu engineering, "
            "busy-hour patterns and a look at which dishes get ordered together."
        ),
        repo=REPO,
        accent=SERIES[1],
        source="create_restaurant_db.sql: 32 menu items and 12,234 ordered items across 5,370 orders, 1 January – 31 March 2023 (Maven Analytics sample).",
        method=(
            "Python runs the MySQL dump in DuckDB and executes the project's queries. Menu engineering uses the Kasavana–Smith method: an item is "
            "popular if it takes at least 70% of an equal share of sales, and high-value if its price beats the sales-weighted average "
            "(no food costs are recorded, so price stands in for contribution). Pairings use support, confidence and lift."
        ),
    )
    r.kpis([
        (money(rev), "food sold", "Jan–Mar 2023"),
        (f"{real_orders:,}", "orders", f"about {d['orders'].mean():.0f} a day"),
        (f"{len(dogs)}", "dishes to review", "cheap and rarely ordered"),
        (f"{midweek / others:.0%}", "of a normal lunch rush", "on Tuesdays and Wednesdays"),
    ])

    r.section(
        "The project's SQL questions, answered",
        "<p>The queries from <code>res.sql</code> and <code>restaurant analysis.sql</code>, run against the database. Italian is the most expensive "
        f"cuisine, Hamburger and Edamame are the best sellers, and the five biggest orders lean Italian ({int(top5['Italian'])} of {int(top5.sum())} items).</p>",
        html=queries_html(results),
        note=f"Data check: {int(q['lines_without_item'])} ordered items have no menu item recorded, and {int(bs.loc[bs['items'] == 0, 'orders'].sum())} orders contain only those. They're excluded from item-level analysis.",
    )
    r.section(
        "How busy is the restaurant?",
        f"<p>Steady: about {d['orders'].mean():.0f} orders a day with no trend up or down over the quarter. The rhythm within the week matters more.</p>",
        fig=daily_figure(d),
    )
    r.section(
        "When do the rushes come?",
        f"<p>Two rushes a day: lunch at noon to 1 pm and dinner from 5 to 7 pm. But <b>Tuesday and Wednesday lunches draw about half the usual crowd</b> "
        f"({midweek:.1f} orders in the noon hour against {others:.1f} on other days). That's the slot for a lunch special, or for lighter staffing.</p>",
        fig=busy_figure(b),
        table=b.pivot(index="weekday", columns="hour", values="avg_orders").reindex(DAYS).round(1).reset_index(),
    )
    me_t = me[["item_name", "category", "price", "sold", "revenue", "class"]].copy()
    r.section(
        "Which dishes earn their place on the menu?",
        f"<p>Every dish, placed by how often it's ordered and what it costs. Dotted lines mark the popularity and price thresholds.</p>"
        f"<p><b>Dogs</b> are cheap and slow: {', '.join(dogs['item_name'])}. They take menu space and kitchen time for little return. "
        f"<b>Puzzles</b> are pricey but slow ({', '.join(puzzles['item_name'])}); better placement or a server recommendation might lift them. "
        "Plowhorses like Hamburger and Edamame sell in volume at low prices, so a small price rise there would add up quickly.</p>",
        fig=menu_figure(me), table=me_t.sort_values(["class", "sold"], ascending=[True, False]),
        note="Shapes repeat the classes so they don't rely on colour. Hover any point for the dish.",
    )
    r.section(
        "Which cuisines bring in the money?",
        f"<p><b>Italian earns the most</b> ({money(cz.loc['Italian', 'revenue'])}) even though Asian dishes sell more often ({int(cz.loc['Asian', 'sold']):,} vs {int(cz.loc['Italian', 'sold']):,}), "
        "because Italian has the highest prices on the menu. That's why high-spending customers matter so much to it, and why its slow sellers (the Puzzles above) are worth promoting rather than cutting.</p>",
        fig=cuisine_figure(it),
    )
    r.section(
        "How big are orders?",
        f"<p>Small: <b>{small:.0%} of orders have one or two items</b>. A handful of big group orders (up to 14 items) make up the long tail.</p>",
        fig=basket_figure(bs[bs["items"] > 0]),
    )
    r.section(
        "Which dishes get ordered together?",
        f"<p>Honestly, not many. Across {len(p)} pairs that appear in at least 30 orders, the strongest is only <b>{p.loc[0, 'lift']:.2f}×</b> as likely as chance "
        f"({p.loc[0, 'item_a']} with {p.loc[0, 'item_b']}). People mostly choose dishes independently, so bundles and 'goes well with' prompts are "
        "a modest lever here.</p>",
        fig=pairs_figure(p),
        table=p.head(25).assign(support=lambda t: (t["support"] * 100).round(2), conf_a_to_b=lambda t: (t["conf_a_to_b"] * 100).round(1),
                                conf_b_to_a=lambda t: (t["conf_b_to_a"] * 100).round(1), lift=lambda t: t["lift"].round(2))
        .rename(columns={"item_a": "dish A", "item_b": "dish B", "orders_together": "orders together", "support": "% of orders", "conf_a_to_b": "% of A orders with B", "conf_b_to_a": "% of B orders with A"}),
        table_caption="Show the top 25 pairs",
    )
    r.section("What goes with each dish?", "<p>Pick a dish to see the dishes most often ordered with it. Bars past the line appear together more often than chance.</p>", html=EXPLORER)
    r.script(explorer_js(data.explorer_payload(p)))

    path = r.write(out)
    print(f"Wrote {path} ({path.stat().st_size / 1024:.0f} KB).")
    return r


if __name__ == "__main__":
    main()
