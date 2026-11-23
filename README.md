# Field & Fork — FarmFresh Market

A full-stack farmer-products marketplace built for the Full Stack Developer assessment. Customers can browse seasonal produce, search and filter, manage a stock-aware basket, and place a demo order. Admins can sign in to manage products, stock and availability, and review orders.

## Technology

- **Frontend:** React 18, React Router, Axios, Vite, Lucide icons
- **Backend:** Python 3.12, FastAPI, SQLAlchemy, Pydantic, JWT admin authentication
- **Database:** PostgreSQL 16
- **Local orchestration:** Docker Compose

## Run with Docker (recommended)

1. Install Docker Desktop and start it.
2. Copy `.env.example` to `.env`. Change `JWT_SECRET` and the admin password for any non-demo deployment.
3. From the project root, run:

   ```bash
   docker compose up --build
   ```

4. Open the customer shop at [http://localhost:5173](http://localhost:5173). The API docs are at [http://localhost:8000/docs](http://localhost:8000/docs).

The API creates the relational tables and inserts six sample products on first startup. PostgreSQL data persists in the `postgres_data` Docker volume.

### Demo admin login

- Email: `admin@farmfresh.com`
- Password: `FarmFresh123!`

These defaults are for local assessment/demo use. Set your own values in `.env` before sharing or deploying.

## Run locally without Docker

### Database

Create a PostgreSQL database and user, then set `DATABASE_URL` in your environment. The default expected local connection is:

```text
postgresql+psycopg://farmcart:farmcart@localhost:5432/farmcart
```

### Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Set `DATABASE_URL`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `CORS_ORIGINS` as needed. The API listens on port 8000.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite serves the app at [http://localhost:5173](http://localhost:5173). Set `VITE_API_URL` if the API is hosted somewhere else; its default is `http://localhost:8000/api`.

## Database schema

The SQL reference/migration is in `backend/migrations/001_initial.sql`. The API currently creates tables from the SQLAlchemy models at startup. The schema contains:

- `products`: product details, price, available stock and active status
- `cart_items`: session-scoped cart lines, unique per cart and product
- `orders`: customer and delivery details, order total and order number
- `order_items`: immutable product name/price/quantity snapshots linked to an order

## API overview

All routes are under `/api`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login` | Admin login; returns a bearer token |
| GET | `/products` | Public active products; supports `search` and `category` |
| GET | `/products/categories` | Active product categories |
| GET | `/products/{id}` | Active product details |
| GET/POST/PUT/DELETE | `/products` and `/products/{id}` | Admin product management (bearer token) |
| GET | `/cart` | View current session cart |
| POST | `/cart/items/{product_id}` | Add quantity to cart |
| PUT/DELETE | `/cart/items/{item_id}` | Change/remove cart line |
| POST | `/orders/checkout` | Place order and decrement stock in one transaction |
| GET | `/orders` | Admin order history (bearer token) |

The browser stores a random cart session ID locally and sends it as `X-Cart-Id`. Admin authentication uses a signed JWT. FastAPI validates product and checkout fields; checkout rechecks stock while holding row locks so concurrent orders cannot oversell inventory.

## Assumptions

- Product prices are displayed in Indian rupees (INR), and inventory quantities are measured in kilograms.
- Customer accounts and online payment are outside the assessment scope. Checkout records delivery details and creates an order without collecting payment data.
- The customer cart is anonymous and tied to the current browser. Admin login credentials come from environment variables.
- Product photos use image URLs; uploads are not included.
- API-startup schema creation is used for this compact assessment. The SQL file is included as a reference for migration tooling.

## Project layout

```text
backend/       FastAPI application, models, validation and SQL schema
frontend/      React customer shop and admin portal
docker-compose.yml
.env.example
```
