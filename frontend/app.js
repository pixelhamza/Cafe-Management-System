// Add Menu Item form.
// These checks mirror backend/app/schemas.py so the user gets immediate
// feedback. The server re-validates everything regardless.
// Saving to the API is the next subtask; submitting does not persist yet.

const MAX_NAME_LENGTH = 100;
const MAX_PRICE = 100000;
const CATEGORIES = ["Beverages", "Food", "Desserts", "Snacks"];

const form = document.getElementById("menu-item-form");
const status = document.getElementById("form-status");

const fields = ["item-name", "item-category", "item-price"];

function showStatus(message, kind) {
  status.textContent = message;
  status.className = kind ? `status ${kind}` : "status";
  status.hidden = false;
}

function clearStatus() {
  status.hidden = true;
  status.textContent = "";
}

// Shows a message under a single field and marks the input invalid,
// so both sighted users and screen readers get the same information.
function showFieldError(fieldId, message) {
  const input = document.getElementById(fieldId);
  const error = document.getElementById(`${fieldId}-error`);
  input.setAttribute("aria-invalid", "true");
  error.textContent = message;
  error.hidden = false;
}

function clearFieldError(fieldId) {
  const input = document.getElementById(fieldId);
  const error = document.getElementById(`${fieldId}-error`);
  input.removeAttribute("aria-invalid");
  error.textContent = "";
  error.hidden = true;
}

function clearAllErrors() {
  fields.forEach(clearFieldError);
}

function validateName(raw) {
  const name = raw.trim();
  if (!name) {
    return "Item name is required";
  }
  if (name.length > MAX_NAME_LENGTH) {
    return `Item name must be ${MAX_NAME_LENGTH} characters or fewer`;
  }
  return null;
}

function validateCategory(raw) {
  if (!raw) {
    return "Category is required";
  }
  if (!CATEGORIES.includes(raw)) {
    return "Choose a valid category";
  }
  return null;
}

function validatePrice(raw) {
  const price = raw.trim();
  if (!price) {
    return "Price is required";
  }
  // Reject anything that is not a plain number with up to two decimals.
  // This catches "12.345", "1e5", "abc" and "12-" before they reach the server.
  if (!/^\d+(\.\d{1,2})?$/.test(price)) {
    if (/^-/.test(price)) {
      return "Price must be greater than 0";
    }
    if (/^\d+\.\d{3,}$/.test(price)) {
      return "Price can have at most 2 decimal places";
    }
    return "Price must be a valid number";
  }
  const value = Number(price);
  if (value <= 0) {
    return "Price must be greater than 0";
  }
  if (value > MAX_PRICE) {
    return `Price must not exceed ${MAX_PRICE.toFixed(2)}`;
  }
  return null;
}

// Returns a field id -> message map, empty when the form is valid.
function validateForm(values) {
  const errors = {};
  const nameError = validateName(values.name);
  const categoryError = validateCategory(values.category);
  const priceError = validatePrice(values.price);

  if (nameError) errors["item-name"] = nameError;
  if (categoryError) errors["item-category"] = categoryError;
  if (priceError) errors["item-price"] = priceError;
  return errors;
}

function readValues() {
  return {
    name: document.getElementById("item-name").value,
    category: document.getElementById("item-category").value,
    price: document.getElementById("item-price").value,
  };
}

// Clear a field's error as soon as the user starts correcting it.
fields.forEach((fieldId) => {
  const input = document.getElementById(fieldId);
  input.addEventListener("input", () => clearFieldError(fieldId));
  input.addEventListener("change", () => clearFieldError(fieldId));
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  clearAllErrors();
  clearStatus();

  const values = readValues();
  const errors = validateForm(values);
  const invalidFields = fields.filter((fieldId) => errors[fieldId]);

  if (invalidFields.length > 0) {
    invalidFields.forEach((fieldId) => showFieldError(fieldId, errors[fieldId]));
    const count = invalidFields.length;
    showStatus(
      `Please fix ${count} ${count === 1 ? "field" : "fields"} below.`,
      "error"
    );
    // Move focus to the first problem so keyboard users land on it directly.
    document.getElementById(invalidFields[0]).focus();
    return;
  }

  showStatus("Looks good. Saving to the server is not wired up yet.", null);
});

form.addEventListener("reset", () => {
  clearAllErrors();
  clearStatus();
});
