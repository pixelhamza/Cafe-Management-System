// Create Customer Order form.
// The form builds a running order and placing it saves the order through
// POST /api/orders. The checks below mirror backend/app/schemas.py so the
// user hears about a problem immediately; the server re-validates regardless
// and its per-field messages are painted back onto the form. The printable
// bill arrives in the next subtask; for now a saved order is confirmed in the
// status banner.

const API_BASE = "http://localhost:8000";

// Mirrors of the limits in backend/app/schemas.py. Change a rule there and
// you must change it here too.
const MAX_QUANTITY = 99;
const MAX_CUSTOMER_NAME_LENGTH = 100;
// Mirrors schemas.GST_PERCENT. The server stamps its own rate onto the order
// and returns the figures it charged, so this is only for the running total
// shown while the order is being built.
const GST_PERCENT = 5;

// Maps a server error key back to the matching form field id. Keys with no
// field here (items, non_field) are shown in the status banner instead.
const FIELD_IDS = {
  customer_name: "order-customer",
};

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
const customerInput = document.getElementById("order-customer");
const formStatus = document.getElementById("form-status");
const orderTable = document.getElementById("order-table");
const orderTableBody = document.getElementById("order-table-body");
const orderSubtotal = document.getElementById("order-subtotal");
const orderTax = document.getElementById("order-tax");
const orderTaxLabel = document.getElementById("order-tax-label");
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

// Guards against a second request while the first is still in flight, which
// would otherwise save the same order twice.
let submitting = false;

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

// The three figures the summary shows, mirroring the subtotal / tax / total
// properties on models.Order. Math.round is half-up for positive values, which
// is the rounding the server applies, so 361.30 is taxed 18.07 on both sides.
function charges() {
  const subtotal = lines.reduce(
    (sum, line) => sum + line.unitPaise * line.quantity,
    0
  );
  const tax = Math.round((subtotal * GST_PERCENT) / 100);
  return { subtotal, tax, total: subtotal + tax };
}

// --- validation, mirroring backend/app/schemas.py ------------------------

// OrderLineCreate.menu_item_id: must name an item the menu actually has.
function validateMenuItemChoice(value) {
  if (!value) {
    return "Choose a menu item";
  }
  if (!menuItems.has(Number(value))) {
    return "That item is no longer on the menu. Reload the page.";
  }
  return null;
}

// OrderLineCreate.quantity: an integer from 1 to MAX_QUANTITY.
function validateQuantity(value) {
  const quantity = value.trim();
  if (!quantity) {
    return "Quantity is required";
  }
  // A leading + is allowed because the server's int parsing accepts it, and
  // the two sides must agree on what counts as a whole number.
  if (!/^\+?\d+$/.test(quantity)) {
    return `Quantity must be a whole number between 1 and ${MAX_QUANTITY}`;
  }
  const parsed = Number(quantity);
  if (parsed < 1) {
    return "Quantity must be at least 1";
  }
  if (parsed > MAX_QUANTITY) {
    return `Quantity must not exceed ${MAX_QUANTITY}`;
  }
  return null;
}

// OrderCreate.customer_name: optional, and short enough to label a bill.
function validateCustomerName(value) {
  if (value.trim().length > MAX_CUSTOMER_NAME_LENGTH) {
    return `Customer name must be ${MAX_CUSTOMER_NAME_LENGTH} characters or fewer`;
  }
  return null;
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
  placeOrderButton.disabled = !hasLines || submitting;
  clearOrderButton.disabled = !hasLines || submitting;
  const { subtotal, tax, total } = charges();
  orderSubtotal.textContent = formatPaise(subtotal);
  orderTaxLabel.textContent = `GST (${GST_PERCENT}%)`;
  orderTax.textContent = formatPaise(tax);
  orderTotal.textContent = formatPaise(total);
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

  const choiceError = validateMenuItemChoice(itemSelect.value);
  if (choiceError) {
    showFieldError("order-item", choiceError);
    itemSelect.focus();
    return;
  }

  const quantityError = validateQuantity(quantityInput.value);
  if (quantityError) {
    showFieldError("order-quantity", quantityError);
    quantityInput.focus();
    return;
  }

  const menuItem = menuItems.get(Number(itemSelect.value));
  if (!addLine(menuItem, Number(quantityInput.value))) {
    quantityInput.focus();
    return;
  }

  // Ready for the next item.
  addLineForm.reset();
  itemSelect.focus();
});

async function placeOrder() {
  const payload = {
    customer_name: customerInput.value.trim(),
    items: lines.map((line) => ({
      menu_item_id: line.menuItemId,
      quantity: line.quantity,
    })),
  };

  const { response, body } = await requestJson("/api/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (response.status === 201) {
    return body;
  }
  if (response.status === 422 && body.errors) {
    throw Object.assign(new Error("validation"), { response, body });
  }
  throw Object.assign(new Error("http"), { response, body });
}

orderForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  // Ignore repeat submits (double click, Enter key) while one is in flight.
  if (submitting) {
    return;
  }

  clearFieldError("order-customer");
  clearStatus(formStatus);

  // OrderCreate.items: an order must have something on it.
  if (lines.length === 0) {
    showStatus(formStatus, "Add at least one item to the order.", "error");
    itemSelect.focus();
    return;
  }

  const customerError = validateCustomerName(customerInput.value);
  if (customerError) {
    showFieldError("order-customer", customerError);
    showStatus(formStatus, "Please fix the field below.", "error");
    customerInput.focus();
    return;
  }

  submitting = true;
  placeOrderButton.disabled = true;
  placeOrderButton.textContent = "Placing order…";

  try {
    const order = await placeOrder();
    // Clearing the lines also re-disables the buttons, so the saved order
    // cannot be placed a second time by accident.
    lines = [];
    customerInput.value = "";
    renderOrder();
    const who = order.customer_name ? ` for ${order.customer_name}` : "";
    // The server's own figures, not the browser's, so the confirmation quotes
    // what was actually charged.
    showStatus(
      formStatus,
      `Order #${order.id}${who} saved. ₹${order.subtotal} plus ` +
        `₹${order.tax} GST at ${Number(order.tax_percent)}% — ` +
        `total ₹${order.total}.`,
      "success"
    );
  } catch (error) {
    if (!error.response) {
      showStatus(formStatus, describeNetworkFailure(error), "error");
    } else if (error.message === "validation") {
      // The server found something the browser checks missed. Mirror its
      // per-field messages onto the form, and show anything that belongs to
      // the order as a whole in the banner.
      const unmatched = [];
      let firstInvalid = null;
      for (const [key, message] of Object.entries(error.body.errors)) {
        const fieldId = FIELD_IDS[key];
        if (fieldId) {
          showFieldError(fieldId, message);
          firstInvalid = firstInvalid || fieldId;
        } else {
          unmatched.push(message);
        }
      }
      showStatus(
        formStatus,
        unmatched.length > 0
          ? unmatched.join(" ")
          : error.body.detail || "The order could not be saved.",
        "error"
      );
      if (firstInvalid) {
        document.getElementById(firstInvalid).focus();
      }
    } else {
      showStatus(
        formStatus,
        describeServerFailure(error.response, error.body),
        "error"
      );
      if (error.response.status === 404) {
        // The menu changed under us; reload the picker so the stale option
        // cannot be chosen again.
        loadMenuItems();
      }
    }
  } finally {
    submitting = false;
    placeOrderButton.textContent = "Place order";
    renderOrder();
  }
});

customerInput.addEventListener("input", () => {
  clearFieldError("order-customer");
});

orderForm.addEventListener("reset", () => {
  lines = [];
  clearFieldError("order-customer");
  clearStatus(formStatus);
  renderOrder();
});

renderOrder();
loadMenuItems();
