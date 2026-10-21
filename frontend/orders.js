// Create Customer Order form.
// This subtask builds the form and the running order only. Nothing is saved
// yet: placing the order is wired up in the next subtask, and the full
// validation rules (mirroring backend/app/schemas.py) arrive in the one after.

const API_BASE = "http://localhost:8000";

const MAX_QUANTITY = 99;

// These helpers are deliberate copies of the ones in app.js. Extracting them
// into a shared common.js would touch Module 1 code, which has no automated
// tests, so it is left as a separate cleanup.
const REQUEST_TIMEOUT_MS = 10000;

const addLineForm = document.getElementById("add-line-form");
const itemSelect = document.getElementById("order-item");
const quantityInput = document.getElementById("order-quantity");
const addLineButton = document.getElementById("add-line-button");
const menuStatus = document.getElementById("menu-status");
const orderForm = document.getElementById("order-form");
const formStatus = document.getElementById("form-status");
const orderTable = document.getElementById("order-table");
const orderTableBody = document.getElementById("order-table-body");
const orderTotal = document.getElementById("order-total");
const emptyOrderNote = document.getElementById("empty-order-note");
const placeOrderButton = document.getElementById("place-order-button");
const clearOrderButton = document.getElementById("clear-order-button");

const lineFields = ["order-item", "order-quantity"];

// The menu items available to pick, keyed by id.
const menuItems = new Map();

// The order being built, one entry per distinct menu item:
// { menuItemId, name, unitPaise, quantity }
let lines = [];

function showStatus(element, message, kind) {
  element.textContent = message;
  element.className = kind ? `status ${kind}` : "status";
  element.hidden = false;
}

function clearStatus(element) {
  element.hidden = true;
  element.textContent = "";
}

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

// Money is handled in whole paise. Prices arrive as strings with at most two
// decimal places, so scaling by 100 and rounding is exact, and every total
// below is integer arithmetic rather than floating point.
function toPaise(price) {
  return Math.round(Number(price) * 100);
}

function formatPaise(paise) {
  return `₹${(paise / 100).toFixed(2)}`;
}

function totalPaise() {
  return lines.reduce((sum, line) => sum + line.unitPaise * line.quantity, 0);
}

// Wraps fetch with a timeout so a hung request cannot leave the page waiting
// forever. Network and timeout failures surface as exceptions; HTTP errors
// come back normally for the caller to classify.
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

function describeNetworkFailure(error) {
  if (error.name === "AbortError") {
    return "The server took too long to respond.";
  }
  return (
    "Could not reach the server. Check that the API is running on " +
    "http://localhost:8000 and try again."
  );
}

function describeServerFailure(response, body) {
  if (response.status === 503) {
    return body.detail || "The database is unavailable right now.";
  }
  if (response.status >= 500) {
    return `The server hit an error (${response.status}).`;
  }
  return body.detail || `The request was rejected (${response.status}).`;
}

function renderOrder() {
  orderTableBody.replaceChildren();

  for (const line of lines) {
    const row = document.createElement("tr");
    const name = document.createElement("td");
    const unitPrice = document.createElement("td");
    const quantity = document.createElement("td");
    const lineTotal = document.createElement("td");
    const actions = document.createElement("td");

    // textContent, not innerHTML, so item names cannot inject markup.
    name.textContent = line.name;
    unitPrice.textContent = formatPaise(line.unitPaise);
    unitPrice.className = "numeric";
    quantity.textContent = String(line.quantity);
    quantity.className = "numeric";
    lineTotal.textContent = formatPaise(line.unitPaise * line.quantity);
    lineTotal.className = "numeric";

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "link-button danger";
    remove.textContent = "Remove";
    // Name the item so the purpose is clear out of context.
    remove.setAttribute("aria-label", `Remove ${line.name} from the order`);
    remove.addEventListener("click", () => removeLine(line.menuItemId));
    actions.className = "row-actions";
    actions.append(remove);

    row.append(name, unitPrice, quantity, lineTotal, actions);
    orderTableBody.append(row);
  }

  const hasLines = lines.length > 0;
  orderTable.hidden = !hasLines;
  emptyOrderNote.hidden = hasLines;
  placeOrderButton.disabled = !hasLines;
  clearOrderButton.disabled = !hasLines;
  orderTotal.textContent = formatPaise(totalPaise());
}

// Adding an item already in the order raises its quantity instead of opening
// a second line, so a bill never lists the same item twice.
function addLine(menuItem, quantity) {
  const existing = lines.find((line) => line.menuItemId === menuItem.id);
  if (existing) {
    const combined = existing.quantity + quantity;
    if (combined > MAX_QUANTITY) {
      showFieldError(
        "order-quantity",
        `${menuItem.name} is already in the order ${existing.quantity} ` +
          `${existing.quantity === 1 ? "time" : "times"}. The most you can ` +
          `order of one item is ${MAX_QUANTITY}.`
      );
      return false;
    }
    existing.quantity = combined;
  } else {
    lines.push({
      menuItemId: menuItem.id,
      name: menuItem.name,
      unitPaise: toPaise(menuItem.price),
      quantity,
    });
  }
  renderOrder();
  return true;
}

function removeLine(menuItemId) {
  lines = lines.filter((line) => line.menuItemId !== menuItemId);
  clearStatus(formStatus);
  renderOrder();
}

function renderMenuOptions(items) {
  menuItems.clear();
  itemSelect.replaceChildren();

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = items.length > 0 ? "Select an item" : "No menu items";
  itemSelect.append(placeholder);

  // The API returns newest first, which is the wrong order for a picker.
  const sorted = [...items].sort((a, b) => a.name.localeCompare(b.name));

  for (const item of sorted) {
    menuItems.set(item.id, item);
    const option = document.createElement("option");
    option.value = String(item.id);
    option.textContent = `${item.name} — ${formatPaise(toPaise(item.price))}`;
    itemSelect.append(option);
  }

  const empty = items.length === 0;
  itemSelect.disabled = empty;
  quantityInput.disabled = empty;
  addLineButton.disabled = empty;

  if (empty) {
    showStatus(
      menuStatus,
      "There are no menu items to order yet. Add some on the Menu page first.",
      null
    );
  } else {
    clearStatus(menuStatus);
  }
}

async function loadMenuItems() {
  try {
    const { response, body } = await requestJson("/api/menu-items");
    if (!response.ok) {
      throw Object.assign(new Error("http"), { response, body });
    }
    renderMenuOptions(body);
  } catch (error) {
    renderMenuOptions([]);
    const message = error.response
      ? `Could not load the menu. ${describeServerFailure(error.response, error.body)}`
      : describeNetworkFailure(error);
    showStatus(menuStatus, message, "error");
  }
}

addLineForm.addEventListener("submit", (event) => {
  event.preventDefault();
  lineFields.forEach(clearFieldError);
  clearStatus(formStatus);

  // Just enough checking to keep unusable values out of the order. The full
  // rules, shared with the server, belong to the validation subtask.
  const menuItem = menuItems.get(Number(itemSelect.value));
  if (!menuItem) {
    showFieldError("order-item", "Choose a menu item");
    itemSelect.focus();
    return;
  }

  const quantity = Number(quantityInput.value);
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > MAX_QUANTITY) {
    showFieldError(
      "order-quantity",
      `Quantity must be a whole number between 1 and ${MAX_QUANTITY}`
    );
    quantityInput.focus();
    return;
  }

  if (!addLine(menuItem, quantity)) {
    quantityInput.focus();
    return;
  }

  // Ready for the next item.
  addLineForm.reset();
  itemSelect.focus();
});

orderForm.addEventListener("submit", (event) => {
  event.preventDefault();
  showStatus(
    formStatus,
    "This order is not saved yet — saving arrives in the next subtask.",
    null
  );
});

orderForm.addEventListener("reset", () => {
  lines = [];
  clearFieldError("order-customer");
  clearStatus(formStatus);
  renderOrder();
});

renderOrder();
loadMenuItems();
