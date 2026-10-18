// Add Menu Item form.
// The validation here mirrors backend/app/schemas.py so the user gets
// immediate feedback. The server re-validates everything regardless.

const API_BASE = "http://localhost:8000";

const MAX_NAME_LENGTH = 100;
const MAX_PRICE = 100000;
const CATEGORIES = ["Beverages", "Food", "Desserts", "Snacks"];

const form = document.getElementById("menu-item-form");
const status = document.getElementById("form-status");
const submitButton = document.getElementById("submit-button");
const listStatus = document.getElementById("list-status");
const menuTable = document.getElementById("menu-table");
const menuTableBody = document.getElementById("menu-table-body");

// Maps a server error key back to the matching form field id.
const FIELD_IDS = {
  name: "item-name",
  category: "item-category",
  price: "item-price",
};

let submitting = false;

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

function formatPrice(value) {
  return `\u20b9${Number(value).toFixed(2)}`;
}

function renderMenuItems(items) {
  menuTableBody.replaceChildren();

  if (items.length === 0) {
    menuTable.hidden = true;
    listStatus.textContent = "No menu items yet. Add one above.";
    listStatus.className = "status";
    listStatus.hidden = false;
    return;
  }

  for (const item of items) {
    const row = document.createElement("tr");
    const name = document.createElement("td");
    const category = document.createElement("td");
    const price = document.createElement("td");

    // textContent, not innerHTML, so item names cannot inject markup.
    name.textContent = item.name;
    category.textContent = item.category;
    price.textContent = formatPrice(item.price);
    price.className = "numeric";

    row.append(name, category, price);
    menuTableBody.append(row);
  }

  menuTable.hidden = false;
  listStatus.hidden = true;
}

async function loadMenuItems() {
  try {
    const response = await fetch(`${API_BASE}/api/menu-items`);
    if (!response.ok) {
      throw new Error(`Server responded with ${response.status}`);
    }
    renderMenuItems(await response.json());
  } catch {
    menuTable.hidden = true;
    listStatus.textContent =
      "Could not load the menu. Is the API running on port 8000?";
    listStatus.className = "status error";
    listStatus.hidden = false;
  }
}

function setSubmitting(active) {
  submitting = active;
  submitButton.disabled = active;
  submitButton.textContent = active ? "Saving..." : "Add item";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submitting) {
    return;
  }

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

  setSubmitting(true);
  try {
    const response = await fetch(`${API_BASE}/api/menu-items`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: values.name.trim(),
        category: values.category,
        price: values.price.trim(),
      }),
    });

    const body = await response.json().catch(() => ({}));

    if (response.status === 201) {
      form.reset();
      showStatus(`"${body.name}" was added to the menu.`, "success");
      await loadMenuItems();
      return;
    }

    if (response.status === 422 && body.errors) {
      // Mirror the server's per-field messages onto the form.
      for (const [key, message] of Object.entries(body.errors)) {
        const fieldId = FIELD_IDS[key];
        if (fieldId) {
          showFieldError(fieldId, message);
        }
      }
      showStatus(body.detail || "The menu item could not be saved.", "error");
      return;
    }

    showStatus(
      body.detail || `The server returned an error (${response.status}).`,
      "error"
    );
  } catch {
    showStatus(
      "Could not reach the server. Check that the API is running on port 8000.",
      "error"
    );
  } finally {
    setSubmitting(false);
  }
});

loadMenuItems();

form.addEventListener("reset", () => {
  clearAllErrors();
  clearStatus();
});
