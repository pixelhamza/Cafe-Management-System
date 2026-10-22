"""Turns Pydantic's nested validation output into a flat field -> message map.

The default FastAPI 422 body is accurate but awkward to render next to a form
field. This produces {"detail": ..., "errors": {"price": "..."}} instead, which
maps straight onto the per-field error slots in the frontend.

Two endpoints post a body, so the labels and the summary line depend on which
form was submitted: see MENU_ITEM_FORM and ORDER_FORM below.
"""

from dataclasses import dataclass

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .schemas import MAX_NAME_LENGTH, MAX_PRICE, MAX_QUANTITY


@dataclass(frozen=True)
class Form:
    """What a rejected body of one shape should be called."""

    detail: str
    labels: dict[str, str]
    generic: str


MENU_ITEM_FORM = Form(
    detail="The menu item could not be saved.",
    labels={"name": "Item name", "category": "Category", "price": "Price"},
    generic="The request body must be a menu item object.",
)

ORDER_FORM = Form(
    detail="The order could not be saved.",
    labels={"customer_name": "Customer name", "items": "Order items"},
    generic="The request body must be an order object.",
)

# Fields inside one line of an order. Their errors are reported against
# "items", because the order form has no input per line to paint them on.
ORDER_LINE_LABELS = {"menu_item_id": "Menu item", "quantity": "Quantity"}

FORMS_BY_PATH = {"/api/orders": ORDER_FORM}


def _message(field: str, error: dict, form: Form) -> str:
    error_type = error.get("type", "")

    if field not in form.labels:
        # Structural problems with the body as a whole, not with one field.
        return form.generic

    label = form.labels[field]

    if error_type == "missing":
        return f"{label} is required"
    if error_type == "string_too_long":
        # The limit differs per field, so take the one Pydantic applied.
        limit = error.get("ctx", {}).get("max_length", MAX_NAME_LENGTH)
        return f"{label} must be {limit} characters or fewer"
    if error_type == "too_short":
        return "Add at least one item to the order"
    if error_type == "greater_than":
        return f"{label} must be greater than 0"
    if error_type == "less_than_equal":
        return f"{label} must not exceed {MAX_PRICE}"
    if error_type == "decimal_max_places":
        return f"{label} can have at most 2 decimal places"
    if error_type in {"decimal_parsing", "float_parsing", "int_parsing"}:
        return f"{label} must be a valid number"
    if error_type == "list_type":
        return f"{label} must be a list of items"
    if error_type in {"dict_type", "model_attributes_type"}:
        return form.generic
    if error_type == "enum":
        return f"Choose a valid {label.lower()}"
    if error_type == "value_error":
        # Messages raised by our own field validators arrive prefixed.
        return error.get("msg", "").removeprefix("Value error, ")

    return error.get("msg", f"{label} is invalid")


def _line_message(position: int, field: str, error: dict) -> str:
    """Describes a problem with one line of an order.

    The line is named by its position because the browser builds the lines
    itself, so there is no input to attach the message to.
    """
    where = f"item {position}"
    error_type = error.get("type", "")

    if field not in ORDER_LINE_LABELS:
        return f"The {where} in this order is not a valid order line."

    if field == "quantity":
        if error_type == "missing":
            return f"Quantity is required for {where}"
        return f"Quantity for {where} must be a whole number from 1 to {MAX_QUANTITY}"

    if error_type == "missing":
        return f"A menu item is required for {where}"
    return f"The menu item for {where} is not valid"


def validation_error_response(
    errors: list[dict], form: Form = MENU_ITEM_FORM
) -> JSONResponse:
    flat: dict[str, str] = {}
    for error in errors:
        if error.get("type") == "json_invalid":
            # loc is a character offset here, not a field name.
            flat.setdefault("non_field", "The request body was not valid JSON.")
            continue

        loc = list(error.get("loc", []))
        if loc and loc[0] == "path":
            flat.setdefault("non_field", "The menu item id in the address is not valid.")
            continue

        location = [part for part in loc if part != "body"]

        # ("items", 0, "quantity") -> the quantity of the first line.
        if (
            len(location) >= 3
            and location[0] == "items"
            and isinstance(location[1], int)
        ):
            flat.setdefault(
                "items",
                _line_message(location[1] + 1, str(location[2]), error),
            )
            continue

        field = str(location[0]) if location else "non_field"
        if field not in form.labels:
            field = "non_field"
        # Keep the first problem reported per field; it is the most relevant.
        flat.setdefault(field, _message(field, error, form))

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": form.detail, "errors": flat},
    )


async def request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    form = FORMS_BY_PATH.get(request.url.path, MENU_ITEM_FORM)
    return validation_error_response(exc.errors(), form)
