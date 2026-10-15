# Tableau calculated fields: Restaurant Order Analysis

Create each one with **Analysis → Create Calculated Field**, name it exactly as shown, and paste the formula.
Tableau shows CSV columns in title case (`new_cases` becomes *New Cases*). If yours show the raw names, use those in the formulas.

## Connect the data

In the data source, double-click fact_order_line to open the physical layer and add dim_menu_item with a **left join** on `item_id = menu_item_id`. A join (not a relationship) is needed because revenue is the sum of the price on every order line. Then relate dim_date on `order_date = date`.

## Fields

### Revenue

```
SUM([Price])
```

Each order line carries its item's price after the join.

### Orders

```
COUNTD([Order Id])
```

### Average Order Value

```
SUM([Price]) / COUNTD([Order Id])
```

### Items per Order

```
COUNT([Item Id]) / COUNTD([Order Id])
```

### Basket Size

```
{ FIXED [Order Id] : COUNT([Item Id]) }
```

Use as a dimension (convert to discrete) for a basket-size histogram.

### Menu Quadrant

```
IF AVG([Price]) >= WINDOW_AVG(AVG([Price])) THEN
    IF COUNT([Item Id]) >= WINDOW_AVG(COUNT([Item Id])) THEN "Star" ELSE "Puzzle" END
ELSE
    IF COUNT([Item Id]) >= WINDOW_AVG(COUNT([Item Id])) THEN "Plowhorse" ELSE "Dog" END
END
```

Menu-engineering colour for the price vs popularity scatter (compute using Item Name).
