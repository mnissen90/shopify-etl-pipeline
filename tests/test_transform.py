"""Unit tests for the transform layer. No database or API needed."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.transform import (  # noqa: E402
    COLUMNS,
    compute_line_items_price,
    dedupe_records,
    flatten_order,
    to_insert_tuples,
)


@pytest.fixture
def sample_order() -> dict:
    return {
        "name": "#1001",
        "created_at": "2024-05-01T10:00:00-04:00",
        "source_name": "web",
        "customer": {"id": 123},
        "billing_address": {
            "latitude": 34.05,
            "longitude": -118.24,
            "province": "California",
            "city": "Los Angeles",
        },
        "discount_codes": [{"code": "SPRING10"}],
        "line_items": [
            {
                "title": "Widget",
                "sku": "W-1",
                "quantity": 2,
                "price": "25.00",
                "discount_allocations": [{"amount": "5.00"}],
                "tax_lines": [{"price": "2.00"}],
            }
        ],
        "shipping_lines": [
            {
                "code": "Standard",
                "discounted_price": "4.99",
                "discount_allocations": [],
                "tax_lines": [],
            }
        ],
        "refunds": [],
    }


def test_flatten_order_line_item(sample_order):
    rows = flatten_order(sample_order, "acme")
    item_rows = [r for r in rows if r["Product_SKU"] == "W-1"]
    assert len(item_rows) == 1
    row = item_rows[0]
    assert row["ClientName"] == "acme"
    assert row["gross_sales"] == pytest.approx(50.00)
    assert row["total_discount"] == pytest.approx(5.00)
    assert row["tax"] == pytest.approx(2.00)
    assert row["discount_codes"] == "SPRING10"
    assert row["city"] == "Los Angeles"


def test_flatten_order_shipping_row(sample_order):
    rows = flatten_order(sample_order, "acme")
    ship_rows = [r for r in rows if r["Product_Title"] == "Standard"]
    assert len(ship_rows) == 1
    assert ship_rows[0]["shipping"] == pytest.approx(4.99)


def test_flatten_order_refund_is_negative():
    order = {
        "name": "#1002",
        "created_at": "2024-05-02T10:00:00-04:00",
        "source_name": "web",
        "customer": {"id": 456},
        "billing_address": {},
        "discount_codes": [],
        "line_items": [],
        "shipping_lines": [],
        "refunds": [
            {
                "created_at": "2024-05-03T10:00:00-04:00",
                "refund_line_items": [
                    {"subtotal": "25.00", "total_tax": "2.00"}
                ],
            }
        ],
    }
    rows = flatten_order(order, "acme")
    assert len(rows) == 1
    assert rows[0]["returns"] == pytest.approx(-25.00)
    assert rows[0]["tax"] == pytest.approx(-2.00)


def test_compute_line_items_price():
    row = {
        "gross_sales": 50.0,
        "total_discount": 5.0,
        "returns": 0,
        "shipping": 4.99,
        "tax": 2.0,
    }
    assert compute_line_items_price(row) == pytest.approx(51.99)


def test_dedupe_records_removes_exact_dupes(sample_order):
    rows = flatten_order(sample_order, "acme")
    doubled = rows + [dict(r) for r in rows]
    assert len(dedupe_records(doubled)) == len(rows)


def test_to_insert_tuples_column_order(sample_order):
    rows = flatten_order(sample_order, "acme")
    tuples = to_insert_tuples(rows)
    assert len(tuples[0]) == len(COLUMNS)
    # ClientName is the first column
    assert all(t[0] == "acme" for t in tuples)
