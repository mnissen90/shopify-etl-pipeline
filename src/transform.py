"""Transform: pure functions that flatten Shopify orders into load-ready rows.

Everything here operates on plain dicts/lists so it can be unit-tested
without a database or API credentials. Mirrors the production logic:
each order becomes one row per line item, one row per shipping line,
and one (negative) row per refund.
"""

from __future__ import annotations

import pandas as pd

# Columns of the warehouse table, in insert order.
COLUMNS = [
    "ClientName",
    "Date",
    "source_name",
    "order_name",
    "Product_Title",
    "Product_SKU",
    "item_quantity",
    "shipping",
    "returns",
    "gross_sales",
    "total_discount",
    "tax",
    "discount_codes",
    "customer_id",
    "latitude",
    "longitude",
    "province",
    "city",
]


def _sum_amounts(items: list[dict] | None, key: str = "amount") -> float:
    return sum(float(i.get(key) or 0) for i in (items or []))


def _tax_total(tax_lines: list[dict] | None) -> float:
    return sum(float(t.get("price") or 0) for t in (tax_lines or []))


def _discount_codes(row: dict) -> str:
    codes = row.get("discount_codes") or []
    return " ".join(c.get("code", "") for c in codes).strip()


def _address_parts(row: dict) -> dict:
    addr = row.get("billing_address") or {}
    return {
        "latitude": addr.get("latitude") or 0,
        "longitude": addr.get("longitude") or 0,
        "province": addr.get("province") or "",
        "city": addr.get("city") or "",
    }


def flatten_order(order: dict, client_name: str) -> list[dict]:
    """Flatten one Shopify order into warehouse rows.

    Returns a list of dicts keyed by COLUMNS: line-item rows, shipping
    rows, and negative-amount refund rows.
    """
    rows: list[dict] = []
    addr = _address_parts(order)
    codes = _discount_codes(order)
    customer = order.get("customer") or {}
    customer_id = customer.get("id") or ""

    for item in order.get("line_items") or []:
        rows.append(
            {
                "ClientName": client_name,
                "Date": order.get("created_at"),
                "source_name": order.get("source_name"),
                "order_name": order.get("name"),
                "Product_Title": item.get("title"),
                "Product_SKU": item.get("sku"),
                "item_quantity": item.get("quantity"),
                "shipping": 0,
                "returns": 0,
                "gross_sales": int(item.get("quantity") or 0)
                * float(item.get("price") or 0),
                "total_discount": _sum_amounts(item.get("discount_allocations")),
                "tax": _tax_total(item.get("tax_lines")),
                "discount_codes": codes,
                "customer_id": customer_id,
                **addr,
            }
        )

    for ship in order.get("shipping_lines") or []:
        discount = _sum_amounts(ship.get("discount_allocations"))
        rows.append(
            {
                "ClientName": client_name,
                "Date": order.get("created_at"),
                "source_name": order.get("source_name"),
                "order_name": order.get("name"),
                "Product_Title": ship.get("code"),
                "Product_SKU": None,
                "item_quantity": 0,
                "shipping": float(ship.get("discounted_price") or 0) - discount,
                "returns": 0,
                "gross_sales": 0,
                "total_discount": 0,
                "tax": _tax_total(ship.get("tax_lines")),
                "discount_codes": None,
                "customer_id": customer_id,
                **addr,
            }
        )

    for refund in order.get("refunds") or []:
        for r_item in refund.get("refund_line_items") or []:
            rows.append(
                {
                    "ClientName": client_name,
                    "Date": refund.get("created_at"),
                    "source_name": order.get("source_name"),
                    "order_name": order.get("name"),
                    "Product_Title": None,
                    "Product_SKU": None,
                    "item_quantity": 0,
                    "shipping": 0,
                    "returns": -(float(r_item.get("subtotal") or 0)),
                    "gross_sales": 0,
                    "total_discount": 0,
                    "tax": -(float(r_item.get("total_tax") or 0)),
                    "discount_codes": None,
                    "customer_id": customer_id,
                    **addr,
                }
            )

    return rows


def compute_line_items_price(row: dict) -> float:
    """Derived metric: net line revenue for one warehouse row."""
    return (
        float(row.get("gross_sales") or 0)
        - float(row.get("total_discount") or 0)
        + float(row.get("returns") or 0)
        + float(row.get("shipping") or 0)
        + float(row.get("tax") or 0)
    )


def dedupe_records(rows: list[dict]) -> list[dict]:
    """Drop exact-duplicate rows (mirrors the ROW_NUMBER() dedupe in sql/)."""
    if not rows:
        return []
    df = pd.DataFrame(rows)
    return df.drop_duplicates().to_dict(orient="records")


def to_insert_tuples(rows: list[dict]) -> list[tuple]:
    """Convert flattened rows to tuples in COLUMNS order for executemany."""
    return [tuple(r.get(c) for c in COLUMNS) for r in rows]
