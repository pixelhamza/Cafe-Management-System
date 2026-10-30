"""White-box tests for Module 2 (Order and Billing).

Unlike test_menu_items.py, which only goes through the HTTP layer, these
call the internal functions directly - validators, model properties, the
DecimalText column, and the error-flattening helpers - so each test targets
a specific statement or branch in the source rather than an API response.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app import crud, errors
from app.models import DecimalText, Order, OrderItem
from app.schemas import OrderCreate, OrderLineCreate

# --- OrderCreate.blank_name_means_none (schemas.py) -------------------------


def test_blank_customer_name_becomes_none():
    order = OrderCreate(customer_name="   ", items=[{"menu_item_id": 1, "quantity": 1}])
    assert order.customer_name is None


def test_customer_name_is_trimmed():
    order = OrderCreate(customer_name="  Bob  ", items=[{"menu_item_id": 1, "quantity": 1}])
    assert order.customer_name == "Bob"


def test_customer_name_none_is_left_as_none():
    """Covers the `not isinstance(value, str)` branch - None skips .strip()."""
    order = OrderCreate(customer_name=None, items=[{"menu_item_id": 1, "quantity": 1}])
    assert order.customer_name is None


# --- OrderCreate.one_line_per_menu_item (schemas.py) -------------------------


def test_duplicate_menu_item_ids_are_rejected():
    with pytest.raises(ValidationError, match="only once"):
        OrderCreate(
            items=[
                {"menu_item_id": 1, "quantity": 1},
                {"menu_item_id": 1, "quantity": 2},
            ]
        )


# --- OrderLineCreate quantity bounds (schemas.py) ----------------------------


@pytest.mark.parametrize("quantity", [1, 99])
def test_quantity_at_the_valid_boundaries_is_accepted(quantity):
    line = OrderLineCreate(menu_item_id=1, quantity=quantity)
    assert line.quantity == quantity


@pytest.mark.parametrize("quantity", [0, 100])
def test_quantity_outside_the_valid_boundaries_is_rejected(quantity):
    with pytest.raises(ValidationError):
        OrderLineCreate(menu_item_id=1, quantity=quantity)


# --- Order / OrderItem computed properties (models.py) ----------------------


def test_line_total_multiplies_unit_price_by_quantity():
    item = OrderItem(menu_item_id=1, item_name="Tea", unit_price=Decimal("30.00"), quantity=3)
    assert item.line_total == Decimal("90.00")


def test_subtotal_sums_every_line_with_exact_decimal_arithmetic():
    """0.10 + 0.20 is the classic float casualty; Decimal must get 0.30 exactly."""
    order = Order(
        tax_percent=Decimal("5.00"),
        items=[
            OrderItem(menu_item_id=1, item_name="A", unit_price=Decimal("0.10"), quantity=1),
            OrderItem(menu_item_id=2, item_name="B", unit_price=Decimal("0.20"), quantity=1),
        ],
    )
    assert order.subtotal == Decimal("0.30")


def test_subtotal_is_zero_for_an_order_with_no_lines():
    """Covers sum()'s empty-sequence branch via its Decimal('0.00') start value."""
    order = Order(tax_percent=Decimal("5.00"), items=[])
    assert order.subtotal == Decimal("0.00")


def test_tax_rounds_half_up_not_half_to_even():
    """361.30 at 5% is exactly 18.065 - Decimal's default (half-to-even) rounds
    that to 18.06; models.Order.tax must round it up to 18.07 instead."""
    order = Order(
        tax_percent=Decimal("5.00"),
        items=[OrderItem(menu_item_id=1, item_name="X", unit_price=Decimal("361.30"), quantity=1)],
    )
    assert order.tax == Decimal("18.07")


def test_tax_uses_the_order_own_tax_percent():
    """A bill must use the rate it was charged at, not whatever GST_PERCENT is now."""
    order = Order(
        tax_percent=Decimal("10.00"),
        items=[OrderItem(menu_item_id=1, item_name="X", unit_price=Decimal("50.00"), quantity=2)],
    )
    assert order.tax == Decimal("10.00")


def test_total_is_subtotal_plus_tax():
    order = Order(
        tax_percent=Decimal("5.00"),
        items=[OrderItem(menu_item_id=1, item_name="X", unit_price=Decimal("200.00"), quantity=1)],
    )
    assert order.total == order.subtotal + order.tax == Decimal("210.00")


# --- DecimalText column type (models.py) -------------------------------------


def test_decimaltext_bind_param_returns_none_for_none():
    column_type = DecimalText()
    assert column_type.process_bind_param(None, dialect=None) is None


def test_decimaltext_bind_param_quantizes_to_two_places():
    column_type = DecimalText()
    assert column_type.process_bind_param(Decimal("10"), dialect=None) == "10.00"


def test_decimaltext_result_value_returns_none_for_none():
    column_type = DecimalText()
    assert column_type.process_result_value(None, dialect=None) is None


def test_decimaltext_result_value_parses_the_stored_string():
    column_type = DecimalText()
    assert column_type.process_result_value("42.50", dialect=None) == Decimal("42.50")


# --- crud.find_menu_items (crud.py) ------------------------------------------


def test_find_menu_items_keys_the_result_by_id_and_drops_missing_ids(db_session):
    from app.schemas import MenuItemCreate

    coffee = crud.create_menu_item(
        db_session, MenuItemCreate(name="Coffee", category="Beverages", price=Decimal("50.00"))
    )

    found = crud.find_menu_items(db_session, [coffee.id, 9999])

    assert set(found) == {coffee.id}
    assert found[coffee.id].name == "Coffee"


# --- crud.create_order (crud.py) - the price/name snapshot rule -------------


def test_order_lines_snapshot_name_and_price_at_the_time_of_sale(db_session):
    from app.schemas import MenuItemCreate, OrderCreate as OrderCreateSchema

    menu_item = crud.create_menu_item(
        db_session, MenuItemCreate(name="Original Name", category="Food", price=Decimal("100.00"))
    )
    order_in = OrderCreateSchema(items=[{"menu_item_id": menu_item.id, "quantity": 1}])

    order = crud.create_order(db_session, order_in, {menu_item.id: menu_item})

    # The menu item changes after the sale; the bill must not follow it.
    menu_item.name = "Renamed"
    menu_item.price = Decimal("500.00")
    db_session.commit()

    assert order.items[0].item_name == "Original Name"
    assert order.items[0].unit_price == Decimal("100.00")


# --- errors._line_message (errors.py) - per-line validation messages --------


def test_line_message_for_a_missing_quantity():
    message = errors._line_message(1, "quantity", {"type": "missing"})
    assert message == "Quantity is required for item 1"


def test_line_message_for_a_quantity_outside_its_range():
    message = errors._line_message(2, "quantity", {"type": "greater_than_equal"})
    assert message == "Quantity for item 2 must be a whole number from 1 to 99"


def test_line_message_for_a_missing_menu_item():
    message = errors._line_message(1, "menu_item_id", {"type": "missing"})
    assert message == "A menu item is required for item 1"


def test_line_message_for_an_invalid_menu_item():
    message = errors._line_message(1, "menu_item_id", {"type": "greater_than"})
    assert message == "The menu item for item 1 is not valid"


def test_line_message_for_an_unrecognised_field_names_the_line():
    message = errors._line_message(3, "surprise_field", {"type": "missing"})
    assert message == "The item 3 in this order is not a valid order line."


# --- errors.validation_error_response (errors.py) - end to end on ORDER_FORM -


def test_validation_error_response_reports_an_empty_item_list():
    response = errors.validation_error_response(
        [{"type": "too_short", "loc": ["body", "items"]}], errors.ORDER_FORM
    )
    assert response.status_code == 422
    import json

    body = json.loads(response.body)
    assert body["errors"]["items"] == "Add at least one item to the order"


def test_validation_error_response_locates_a_nested_line_error():
    """loc = ("body", "items", 0, "quantity") must land on "items", naming line 1."""
    response = errors.validation_error_response(
        [{"type": "greater_than_equal", "loc": ["body", "items", 0, "quantity"]}],
        errors.ORDER_FORM,
    )
    import json

    body = json.loads(response.body)
    assert body["errors"]["items"] == "Quantity for item 1 must be a whole number from 1 to 99"


# --- main.create_order's missing-menu-item branch (main.py) -----------------
# The one branch above that only exists in the route handler, not in crud or
# schemas, so it has to be exercised through the HTTP layer.


def test_create_order_returns_404_when_a_menu_item_no_longer_exists(client):
    response = client.post("/api/orders", json={"items": [{"menu_item_id": 9999, "quantity": 1}]})

    assert response.status_code == 404
    assert "no longer exists" in response.json()["detail"]


def test_create_order_succeeds_when_every_menu_item_exists(client):
    item = client.post(
        "/api/menu-items", json={"name": "Cold Coffee", "category": "Beverages", "price": "120.00"}
    ).json()

    response = client.post(
        "/api/orders", json={"items": [{"menu_item_id": item["id"], "quantity": 2}]}
    )

    assert response.status_code == 201
    assert response.json()["subtotal"] == "240.00"


# --- GET /api/orders/{id} - crud.get_order and _get_order_or_404 (main.py) --


def test_get_order_returns_the_saved_bill(client):
    item = client.post(
        "/api/menu-items", json={"name": "Alfred", "category": "Food", "price": "400.00"}
    ).json()
    created = client.post(
        "/api/orders", json={"items": [{"menu_item_id": item["id"], "quantity": 1}]}
    ).json()

    response = client.get(f"/api/orders/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["total"] == created["total"]


def test_get_order_returns_404_for_an_id_that_does_not_exist(client):
    response = client.get("/api/orders/9999")

    assert response.status_code == 404
    assert "no longer exists" in response.json()["detail"]
