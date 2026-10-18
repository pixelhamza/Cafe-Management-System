# Cafe-Management-System

A simple cafe management system built as a college PBL project.

- **Frontend:** HTML, CSS, vanilla JavaScript
- **Backend:** Python + FastAPI *(not implemented yet)*
- **Database:** PostgreSQL *(not implemented yet)*
- **Tests:** pytest *(not implemented yet)*

## Modules

1. **Menu Management** — add, view, edit and delete menu items (in progress)
2. **Order and Billing Management** — create orders and generate bills (not started)

## Project structure

```
frontend/
  index.html    Add Menu Item form
  styles.css    Styling
  app.js        Form behaviour
```

## Running the frontend

The frontend is plain static files. From the repository root:

```bash
python3 -m http.server 5500 --directory frontend
```

Then open <http://localhost:5500> in a browser. You can also open
`frontend/index.html` directly in a browser.

## Current status

The Add Menu Item form is built, but submitting it does not save anything yet.
Input validation and the FastAPI/PostgreSQL backend are the next steps.
