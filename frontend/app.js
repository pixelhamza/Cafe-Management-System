// Add Menu Item form — UI behaviour only.
// Input validation (Task 2) and saving to the API (Task 3) are not wired up yet.

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

// Clear a field's error as soon as the user starts correcting it.
fields.forEach((fieldId) => {
  document.getElementById(fieldId).addEventListener("input", () => {
    clearFieldError(fieldId);
  });
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  clearAllErrors();
  showStatus("Form is not connected to the server yet.", null);
});

form.addEventListener("reset", () => {
  clearAllErrors();
  clearStatus();
});
