"""Tests for the menu item endpoints."""

import sqlite3
from decimal import Decimal

import pytest
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.database import get_db
from app.main import app

ENDPOINT = "/api/menu-items"


# --- successful creation ---------------------------------------------------


def test_create_returns_201_with_the_saved_item(client, valid_item):
    response = client.post(ENDPOINT, json=valid_item)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Cappuccino"
    assert body["category"] == "Beverages"
    assert body["price"] == "180.50"
    assert isinstance(body["id"], int)


def test_created_item_appears_in_the_list(client, valid_item):
    client.post(ENDPOINT, json=valid_item)

    listed = client.get(ENDPOINT).json()

    assert len(listed) == 1
    assert listed[0]["name"] == "Cappuccino"


def test_list_is_empty_before_anything_is_added(client):
    assert client.get(ENDPOINT).json() == []


def test_surrounding_whitespace_is_stripped_from_the_name(client):
    response = client.post(
        ENDPOINT, json={"name": "  Veg Sandwich  ", "category": "Food", "price": "120"}
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Veg Sandwich"


def test_price_is_always_returned_with_two_decimal_places(client):
    response = client.post(
        ENDPOINT, json={"name": "Tea", "category": "Beverages", "price": "40"}
    )

    assert response.json()["price"] == "40.00"


@pytest.mark.parametrize("price", ["0.10", "0.01", "99999.99", "180.50"])
def test_prices_survive_a_round_trip_exactly(client, price):
    """Money must not drift. 0.10 is the classic float casualty."""
    client.post(ENDPOINT, json={"name": "Item", "category": "Food", "price": price})

    stored = client.get(ENDPOINT).json()[0]["price"]

    assert Decimal(stored) == Decimal(price)


def test_price_is_stored_as_text_not_a_float(client, valid_item):
    """Guards the DecimalText column against a regression to Numeric/float."""
    client.post(ENDPOINT, json=valid_item)

    with sqlite3.connect(settings.database_file) as connection:
        value, kind = connection.execute(
            "SELECT price, typeof(price) FROM menu_items"
        ).fetchone()

    assert kind == "text"
    assert value == "180.50"


def test_items_are_listed_newest_first(client):
    for name in ["First", "Second", "Third"]:
        client.post(ENDPOINT, json={"name": name, "category": "Food", "price": "10"})

    names = [item["name"] for item in client.get(ENDPOINT).json()]

    assert names == ["Third", "Second", "First"]


def test_every_category_is_accepted(client):
    for category in client.get("/api/categories").json():
        response = client.post(
            ENDPOINT, json={"name": f"Item {category}", "category": category, "price": "10"}
        )
        assert response.status_code == 201, category


def test_items_persist_in_the_database_file_beyond_the_request(client, valid_item):
    """Reads the file directly, bypassing the app, to prove it was written."""
    client.post(ENDPOINT, json=valid_item)

    with sqlite3.connect(settings.database_file) as connection:
        rows = connection.execute("SELECT name, category, price FROM menu_items").fetchall()

    assert rows == [("Cappuccino", "Beverages", "180.50")]


# --- invalid input ---------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "field", "expected"),
    [
        ({"name": "", "category": "Food", "price": "10"}, "name", "Item name is required"),
        ({"name": "   ", "category": "Food", "price": "10"}, "name", "Item name is required"),
        ({"category": "Food", "price": "10"}, "name", "Item name is required"),
        (
            {"name": "x" * 101, "category": "Food", "price": "10"},
            "name",
            "Item name must be 100 characters or fewer",
        ),
        (
            {"name": "Tea", "category": "Beverages", "price": "-5"},
            "price",
            "Price must be greater than 0",
        ),
        (
            {"name": "Tea", "category": "Beverages", "price": "0"},
            "price",
            "Price must be greater than 0",
        ),
        (
            {"name": "Tea", "category": "Beverages", "price": "12.345"},
            "price",
            "Price can have at most 2 decimal places",
        ),
        (
            {"name": "Tea", "category": "Beverages", "price": "abc"},
            "price",
            "Price must be a valid number",
        ),
        (
            {"name": "Tea", "category": "Beverages", "price": "999999"},
            "price",
            "Price must not exceed 100000.00",
        ),
        ({"name": "Tea", "category": "Beverages"}, "price", "Price is required"),
        (
            {"name": "Tea", "category": "Drinks", "price": "50"},
            "category",
            "Choose a valid category",
        ),
        ({"name": "Tea", "price": "50"}, "category", "Category is required"),
    ],
)
def test_invalid_input_is_rejected_with_a_clear_message(client, payload, field, expected):
    response = client.post(ENDPOINT, json=payload)

    assert response.status_code == 422
    assert response.json()["errors"][field] == expected


def test_all_bad_fields_are_reported_together(client):
    response = client.post(
        ENDPOINT, json={"name": "", "category": "Nope", "price": "-1"}
    )

    assert response.status_code == 422
    assert set(response.json()["errors"]) == {"name", "category", "price"}


def test_rejected_items_are_not_saved(client):
    client.post(ENDPOINT, json={"name": "", "category": "Food", "price": "-1"})

    assert client.get(ENDPOINT).json() == []


def test_malformed_json_is_reported_as_a_body_problem(client):
    response = client.post(
        ENDPOINT, content=b"{not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["errors"]["non_field"] == "The request body was not valid JSON."


@pytest.mark.parametrize("body", [[1, 2], "hello", 5])
def test_a_body_that_is_not_an_object_is_rejected(client, body):
    response = client.post(ENDPOINT, json=body)

    assert response.status_code == 422
    assert (
        response.json()["errors"]["non_field"]
        == "The request body must be a menu item object."
    )


def test_item_names_are_not_treated_as_markup(client):
    """The name is stored verbatim; escaping is the frontend's job."""
    response = client.post(
        ENDPOINT,
        json={"name": "<script>alert(1)</script>", "category": "Food", "price": "10"},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "<script>alert(1)</script>"


# --- error cases -----------------------------------------------------------


def test_database_failure_returns_503(client):
    def broken_db():
        raise OperationalError("SELECT 1", {}, Exception("database is locked"))

    app.dependency_overrides[get_db] = broken_db

    response = client.get(ENDPOINT)

    assert response.status_code == 503
    assert response.json()["detail"] == "Could not reach the database. Please try again."


def test_health_endpoint_reports_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_categories_endpoint_lists_the_valid_categories(client):
    response = client.get("/api/categories")

    assert response.status_code == 200
    assert response.json() == ["Beverages", "Food", "Desserts", "Snacks"]
