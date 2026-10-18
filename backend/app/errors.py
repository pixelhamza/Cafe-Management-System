"""Turns Pydantic's nested validation output into a flat field -> message map.

The default FastAPI 422 body is accurate but awkward to render next to a form
field. This produces {"detail": ..., "errors": {"price": "..."}} instead, which
maps straight onto the per-field error slots in the frontend.
"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .schemas import MAX_NAME_LENGTH, MAX_PRICE

FIELD_LABELS = {
    "name": "Item name",
    "category": "Category",
    "price": "Price",
}


GENERIC_BODY_ERROR = "The request body must be a menu item object."


def _message(field: str, error: dict) -> str:
    error_type = error.get("type", "")

    if field not in FIELD_LABELS:
        # Structural problems with the body as a whole, not with one field.
        return GENERIC_BODY_ERROR

    label = FIELD_LABELS[field]

    if error_type == "missing":
        return f"{label} is required"
    if error_type == "string_too_long":
        return f"{label} must be {MAX_NAME_LENGTH} characters or fewer"
    if error_type == "greater_than":
        return f"{label} must be greater than 0"
    if error_type == "less_than_equal":
        return f"{label} must not exceed {MAX_PRICE}"
    if error_type == "decimal_max_places":
        return f"{label} can have at most 2 decimal places"
    if error_type in {"decimal_parsing", "float_parsing", "int_parsing"}:
        return f"{label} must be a valid number"
    if error_type == "enum":
        return f"Choose a valid {label.lower()}"
    if error_type == "value_error":
        # Messages raised by our own field validators arrive prefixed.
        return error.get("msg", "").removeprefix("Value error, ")

    return error.get("msg", f"{label} is invalid")


def validation_error_response(errors: list[dict]) -> JSONResponse:
    flat: dict[str, str] = {}
    for error in errors:
        if error.get("type") == "json_invalid":
            # loc is a character offset here, not a field name.
            flat.setdefault("non_field", "The request body was not valid JSON.")
            continue

        location = [part for part in error.get("loc", []) if part != "body"]
        field = str(location[0]) if location else "non_field"
        if field not in FIELD_LABELS:
            field = "non_field"
        # Keep the first problem reported per field; it is the most relevant.
        flat.setdefault(field, _message(field, error))

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "The menu item could not be saved.", "errors": flat},
    )


async def request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return validation_error_response(exc.errors())
