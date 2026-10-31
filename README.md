# Cafe Management System

A simple cafe management system built as a college PBL project.

- **Frontend:** HTML, CSS, vanilla JavaScript
- **Backend:** Python + FastAPI
- **Database:** SQLite (via SQLAlchemy)
- **Tests:** pytest

## Modules

1. **Menu Management** — add, view, edit and delete menu items
2. **Order and Billing Management** — build a customer order, calculate GST and the total, save it, and look its bill up again later

## Project structure

```
backend/
  app/        FastAPI app: routes, validation, models, database
  tests/      pytest suite
frontend/
  index.html, app.js        Menu Management page
  orders.html, orders.js    Order and Billing page
```

## Running it

Two servers, both from the repository root.

```bash
# API -> http://localhost:8000
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
# Web -> http://localhost:5500
python3 -m http.server 5500 --directory frontend
```

Then open <http://localhost:5500> in a browser.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```
