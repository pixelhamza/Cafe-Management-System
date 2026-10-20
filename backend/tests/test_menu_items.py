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


# --- updating an item ------------------------------------------------------


def _create(client, **overrides) -> dict:
    """Creates one item and returns it, so update and delete tests
    start from a row that really exists."""
    payload = {"name": "Cappuccino", "category": "Beverages", "price": "180.50"}
    payload.update(overrides)
    response = client.post(ENDPOINT, json=payload)

    assert response.status_code == 201
    return response.json()


NEW_VALUES = {"name": "Flat White", "category": "Beverages", "price": "210.00"}


def test_update_returns_200_with_the_new_values(client):
    item = _create(client)

    response = client.put(f"{ENDPOINT}/{item['id']}", json=NEW_VALUES)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == item["id"]
    assert body["name"] == "Flat White"
    assert body["price"] == "210.00"


def test_update_changes_what_the_list_returns(client):
    item = _create(client)

    client.put(f"{ENDPOINT}/{item['id']}", json=NEW_VALUES)

    assert [row["name"] for row in client.get(ENDPOINT).json()] == ["Flat White"]


def test_update_edits_in_place_without_adding_a_row(client):
    item = _create(client)

    client.put(f"{ENDPOINT}/{item['id']}", json=NEW_VALUES)

    assert len(client.get(ENDPOINT).json()) == 1


def test_update_can_move_an_item_to_another_category(client):
    item = _create(client)

    response = client.put(
        f"{ENDPOINT}/{item['id']}",
        json={"name": "Cappuccino", "category": "Desserts", "price": "180.50"},
    )

    assert response.status_code == 200
    assert response.json()["category"] == "Desserts"


def test_updating_a_missing_item_returns_404(client):
    response = client.put(f"{ENDPOINT}/999", json=NEW_VALUES)

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "That menu item no longer exists. It may have been deleted."
    )


def test_updating_a_deleted_item_returns_404(client):
    """The case the edit form hits when another tab removes the row."""
    item = _create(client)
    client.delete(f"{ENDPOINT}/{item['id']}")

    response = client.put(f"{ENDPOINT}/{item['id']}", json=NEW_VALUES)

    assert response.status_code == 404


@pytest.mark.parametrize("price", ["0.10", "0.01", "99999.99", "100000.00"])
def test_updated_prices_survive_a_round_trip_exactly(client, price):
    item = _create(client)

    response = client.put(
        f"{ENDPOINT}/{item['id']}",
        json={"name": "Cappuccino", "category": "Beverages", "price": price},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["price"]) == Decimal(price)


@pytest.mark.parametrize(
    ("payload", "field", "expected"),
    [
        (
            {"name": "", "category": "Food", "price": "10"},
            "name",
            "Item name is required",
        ),
        (
            {"name": "x" * 101, "category": "Food", "price": "10"},
            "name",
            "Item name must be 100 characters or fewer",
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
            {"name": "Tea", "category": "Cocktails", "price": "10"},
            "category",
            "Choose a valid category",
        ),
    ],
)
def test_update_enforces_the_same_rules_as_creation(client, payload, field, expected):
    """Subtask 2 claimed the shared schema already covered updates.
    This is the evidence for that claim."""
    item = _create(client)

    response = client.put(f"{ENDPOINT}/{item['id']}", json=payload)

    assert response.status_code == 422
    assert response.json()["errors"][field] == expected


def test_a_rejected_update_leaves_the_item_unchanged(client):
    item = _create(client)

    response = client.put(
        f"{ENDPOINT}/{item['id']}",
        json={"name": "", "category": "Food", "price": "10"},
    )

    assert response.status_code == 422
    assert client.get(ENDPOINT).json() == [item]


# --- deleting an item ------------------------------------------------------


def test_delete_returns_204_with_no_body(client):
    item = _create(client)

    response = client.delete(f"{ENDPOINT}/{item['id']}")

    assert response.status_code == 204
    assert response.content == b""


def test_deleted_item_disappears_from_the_list(client):
    item = _create(client)

    client.delete(f"{ENDPOINT}/{item['id']}")

    assert client.get(ENDPOINT).json() == []


def test_deleting_one_item_leaves_the_others(client):
    keep = _create(client, name="Veg Sandwich", category="Food", price="120.00")
    remove = _create(client)

    client.delete(f"{ENDPOINT}/{remove['id']}")

    assert client.get(ENDPOINT).json() == [keep]


def test_deleting_a_missing_item_returns_404(client):
    response = client.delete(f"{ENDPOINT}/999")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "That menu item no longer exists. It may have been deleted."
    )


def test_deleting_twice_returns_404_the_second_time(client):
    """The server is right to 404 here, but the browser paints that 404 as an
    error even though the delete succeeded -- the double-click defect, which
    reproduces against commit 223df9b."""
    item = _create(client)

    first = client.delete(f"{ENDPOINT}/{item['id']}")
    second = client.delete(f"{ENDPOINT}/{item['id']}")

    assert first.status_code == 204
    assert second.status_code == 404


def test_delete_removes_the_row_from_the_database_file(client):
    """Reads the file directly, bypassing the app, to prove it was removed."""
    item = _create(client)

    client.delete(f"{ENDPOINT}/{item['id']}")

    with sqlite3.connect(settings.database_file) as connection:
        rows = connection.execute("SELECT id FROM menu_items").fetchall()

    assert rows == []


# --- boundary values on update ---------------------------------------------
# Boundary value analysis: each rule is probed just inside and just outside
# its limit, since that is where off-by-one mistakes live.


@pytest.mark.parametrize(
    ("price", "status"),
    [("0.01", 200), ("0.00", 422), ("100000.00", 200), ("100000.01", 422)],
)
def test_update_price_boundaries(client, price, status):
    item = _create(client)

    response = client.put(
        f"{ENDPOINT}/{item['id']}",
        json={"name": "Cappuccino", "category": "Beverages", "price": price},
    )

    assert response.status_code == status


@pytest.mark.parametrize(("length", "status"), [(99, 200), (100, 200), (101, 422)])
def test_update_name_length_boundaries(client, length, status):
    item = _create(client)

    response = client.put(
        f"{ENDPOINT}/{item['id']}",
        json={"name": "A" * length, "category": "Food", "price": "10.00"},
    )

    assert response.status_code == status


# --- known defects ---------------------------------------------------------
# These two fail against the current code. Each is tracked as a bug and
# should pass once its fix lands.


def test_a_name_that_fits_after_trimming_is_accepted_on_update(client):
    """max_length is applied to the raw string before the validator strips it,
    so a name that is exactly at the limit once trimmed is wrongly rejected."""
    item = _create(client)
    name = "A" * 100

    response = client.put(
        f"{ENDPOINT}/{item['id']}",
        json={"name": f"{name}  ", "category": "Food", "price": "10.00"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == name


def test_adding_an_item_with_a_name_already_in_use_is_rejected(client):
    _create(client, name="Masala Chai", category="Beverages", price="40.00")

    response = client.post(
        ENDPOINT,
        json={"name": "Masala Chai", "category": "Beverages", "price": "40.00"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == 'A menu item named "Masala Chai" already exists.'


def test_saving_an_item_without_renaming_it_is_allowed(client):
    """The duplicate check must not treat an item as a clash with itself,
    or editing only the price would be impossible."""
    item = _create(client)

    response = client.put(
        f"{ENDPOINT}/{item['id']}",
        json={"name": item["name"], "category": "Beverages", "price": "195.00"},
    )

    assert response.status_code == 200
    assert response.json()["price"] == "195.00"


def test_renaming_onto_an_existing_name_is_rejected(client):
    """Nothing enforces unique names, so an edit can leave the menu holding
    two rows a customer cannot tell apart."""
    _create(client, name="Masala Chai", category="Beverages", price="40.00")
    other = _create(client, name="Veg Sandwich", category="Food", price="120.00")

    response = client.put(
        f"{ENDPOINT}/{other['id']}",
        json={"name": "Masala Chai", "category": "Beverages", "price": "40.00"},
    )

    assert response.status_code == 409
