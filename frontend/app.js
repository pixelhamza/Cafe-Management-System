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
const resetButton = document.getElementById("reset-button");
const cancelEditButton = document.getElementById("cancel-edit-button");
const formHeading = document.getElementById("form-heading");
const editingNote = document.getElementById("editing-note");
const listStatus = document.getElementById("list-status");
const menuTable = document.getElementById("menu-table");
const menuTableBody = document.getElementById("menu-table-body");
const confirmDialog = document.getElementById("confirm-delete");
const confirmMessage = document.getElementById("confirm-delete-message");

// Maps a server error key back to the matching form field id.
const FIELD_IDS = {
  name: "item-name",
  category: "item-category",
  price: "item-price",
};

let submitting = false;
// null means the form is adding; an id means it is editing that item.
let editingId = null;

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

const REQUEST_TIMEOUT_MS = 10000;

function formatPrice(value) {
  return `\u20b9${Number(value).toFixed(2)}`;
}

// Wraps fetch with a timeout so a hung request cannot leave the form
// disabled forever. Network and timeout failures surface as exceptions;
// HTTP errors come back normally for the caller to classify.
async function requestJson(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
    });
    const body = await response.json().catch(() => ({}));
    return { response, body };
  } finally {
    clearTimeout(timer);
  }
}

// The request never reached the server, or no reply came back in time.
// timeoutNote adds caller-specific advice when the request timed out.
function describeNetworkFailure(error, timeoutNote = "") {
  if (error.name === "AbortError") {
    const note = timeoutNote ? ` ${timeoutNote}` : "";
    return `The server took too long to respond.${note}`;
  }
  return (
    "Could not reach the server. Check that the API is running on " +
    "http://localhost:8000 and try again."
  );
}

// The server replied, but with an error status.
function describeServerFailure(response, body) {
  if (response.status === 503) {
    return (
      body.detail ||
      "The database is unavailable right now. Your item was not saved."
    );
  }
  if (response.status >= 500) {
    return `The server hit an error (${response.status}). Your item was not saved.`;
  }
  if (response.status === 404) {
    return (
      body.detail ||
      "The API endpoint was not found. Is the server running the current code?"
    );
  }
  return body.detail || `The request was rejected (${response.status}).`;
}

function renderMenuItems(items, newItemId) {
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

    const actions = document.createElement("td");
    actions.className = "row-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "link-button";
    edit.textContent = "Edit";
    // Name the item so the purpose is clear out of context.
    edit.setAttribute("aria-label", `Edit ${item.name}`);
    edit.addEventListener("click", () => startEditing(item));

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "link-button danger";
    remove.textContent = "Delete";
    remove.setAttribute("aria-label", `Delete ${item.name}`);
    remove.addEventListener("click", () => askToDelete(item));

    actions.append(edit, remove);

    row.append(name, category, price, actions);
    if (item.id === newItemId) {
      // Briefly mark the row that was just added so it is easy to spot.
      row.classList.add("row-new");
    }
    menuTableBody.append(row);
  }

  menuTable.hidden = false;
  listStatus.hidden = true;
}

async function loadMenuItems(newItemId) {
  try {
    const { response, body } = await requestJson("/api/menu-items");
    if (!response.ok) {
      throw Object.assign(new Error("http"), { response, body });
    }
    renderMenuItems(body, newItemId);
  } catch (error) {
    const message = error.response
      ? `Could not load the menu. ${describeServerFailure(error.response, error.body)}`
      : describeNetworkFailure(error);
    menuTable.hidden = true;
    listStatus.textContent = message;
    listStatus.className = "status error";
    listStatus.hidden = false;
  }
}

// The item waiting on a confirmation, or null when the dialogue is closed.
let pendingDelete = null;

function askToDelete(item) {
  if (submitting) {
    return;
  }
  pendingDelete = item;
  confirmMessage.textContent = `Delete "${item.name}"? This cannot be undone.`;
  // Escape leaves returnValue untouched, so a stale "delete" from a previous
  // confirmation would count as a fresh one. Clear it before opening.
  confirmDialog.returnValue = "";
  confirmDialog.showModal();
}

// The dialogue's buttons submit a method="dialog" form, so the choice
// arrives as returnValue. Escape and the backdrop leave it empty, which
// means cancel: the item is only deleted on an explicit confirmation.
confirmDialog.addEventListener("close", () => {
  const item = pendingDelete;
  pendingDelete = null;
  if (item && confirmDialog.returnValue === "delete") {
    deleteItem(item);
  }
});

async function deleteItem(item) {
  if (submitting) {
    return;
  }
  try {
    const { response, body } = await requestJson(`/api/menu-items/${item.id}`, {
      method: "DELETE",
    });
    if (response.status === 204) {
      // Editing the row that just vanished would PUT to a dead id.
      if (editingId === item.id) {
        form.reset();
        enterAddMode();
      }
      // After form.reset(), which clears the status on its way through.
      showStatus(`${item.name} was removed from the menu.`, "success");
      await loadMenuItems();
      return;
    }
    showStatus(describeServerFailure(response, body), "error");
  } catch (error) {
    showStatus(describeNetworkFailure(error), "error");
  }
}

function enterAddMode() {
  editingId = null;
  formHeading.textContent = "Add Menu Item";
  submitButton.textContent = "Add item";
  resetButton.hidden = false;
  cancelEditButton.hidden = true;
  editingNote.hidden = true;
  editingNote.textContent = "";
}

function startEditing(item) {
  if (submitting) {
    return;
  }
  editingId = item.id;
  document.getElementById("item-name").value = item.name;
  document.getElementById("item-category").value = item.category;
  // The API sends price as a string already formatted to two places.
  document.getElementById("item-price").value = item.price;

  clearAllErrors();
  clearStatus();
  formHeading.textContent = "Edit Menu Item";
  submitButton.textContent = "Update item";
  // Clearing the fields mid-edit is confusing; cancelling is the way out.
  resetButton.hidden = true;
  cancelEditButton.hidden = false;
  editingNote.textContent = `Editing "${item.name}". Save to apply your changes.`;
  editingNote.hidden = false;
  document.getElementById("item-name").focus();
}

cancelEditButton.addEventListener("click", () => {
  if (submitting) {
    return;
  }
  form.reset();
  clearAllErrors();
  clearStatus();
  enterAddMode();
  document.getElementById("item-name").focus();
});

function setSubmitting(active) {
  submitting = active;
  submitButton.disabled = active;
  resetButton.disabled = active;
  cancelEditButton.disabled = active;
  // Freeze the inputs too, so the values cannot drift from what is in flight.
  fields.forEach((fieldId) => {
    document.getElementById(fieldId).disabled = active;
  });
  submitButton.textContent = active
    ? "Saving\u2026"
    : editingId === null
      ? "Add item"
      : "Update item";
  submitButton.setAttribute("aria-busy", String(active));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  // Ignore repeat submits (double click, Enter key) while one is in flight.
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
  showStatus("Saving\u2026", null);
  let saved = false;

  try {
    const editing = editingId !== null;
    const { response, body } = await requestJson(
      editing ? `/api/menu-items/${editingId}` : "/api/menu-items",
      {
        method: editing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: values.name.trim(),
          category: values.category,
          price: values.price.trim(),
        }),
      }
    );

    if (response.status === (editing ? 200 : 201)) {
      saved = true;
      form.reset();
      clearAllErrors();
      enterAddMode();
      showStatus(
        editing
          ? `${body.name} (${formatPrice(body.price)}) was updated.`
          : `${body.name} (${formatPrice(body.price)}) was added to the menu.`,
        "success"
      );
      await loadMenuItems(body.id);
      return;
    }

    if (response.status === 422 && body.errors) {
      // The server found something the browser checks missed. Mirror its
      // per-field messages onto the form.
      let matched = 0;
      for (const [key, message] of Object.entries(body.errors)) {
        const fieldId = FIELD_IDS[key];
        if (fieldId) {
          showFieldError(fieldId, message);
          matched += 1;
        }
      }
      const unmatched = Object.entries(body.errors)
        .filter(([key]) => !FIELD_IDS[key])
        .map(([, message]) => message);
      showStatus(
        unmatched.length > 0
          ? unmatched.join(" ")
          : body.detail || "The menu item could not be saved.",
        "error"
      );
      if (matched > 0) {
        const firstInvalid = fields.find((fieldId) =>
          document.getElementById(fieldId).hasAttribute("aria-invalid")
        );
        if (firstInvalid) {
          document.getElementById(firstInvalid).focus();
        }
      }
      return;
    }

    showStatus(describeServerFailure(response, body), "error");
  } catch (error) {
    showStatus(
      describeNetworkFailure(
        error,
        "The item may not have been saved \u2014 check the list below before trying again."
      ),
      "error"
    );
  } finally {
    setSubmitting(false);
    if (saved) {
      // Ready for the next entry.
      document.getElementById("item-name").focus();
    }
  }
});

form.addEventListener("reset", () => {
  clearAllErrors();
  clearStatus();
});

loadMenuItems();
