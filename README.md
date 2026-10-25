# Farm2Home — Direct Farm-to-Home Platform

Farm2Home is a full-stack college-project demonstration that connects fictional farms around Mira-Bhayandar with nearby households. It uses a responsive vanilla-JavaScript storefront, a Flask JSON REST API and a MySQL 8 database. The app can use the project's configured MySQL-compatible development database or local MySQL; SQLite is available as an automatic local smoke-test fallback only.

**Payments, customer GPS coordinates and delivery tracking are simulated.** There are no real charges or live vehicle tracking. The route planner is explainable, rule-based optimization; it is not machine learning.

## Features

- Consumer, farmer and admin accounts with password hashing, cookie sessions and role/ownership checks.
- Marketplace with search, category/organic filters, sorting, farmer profiles, product details, ratings and stock badges.
- Persistent basket, quantity changes, stock validation, delivery slot capacity checks, subscriber discounts, loyalty redemption and simulated payment.
- Orders, order status flow, delivery route grouping, approximate map markers/ETA and in-app notifications.
- Weekly, bi-weekly and monthly baskets with pause/resume/cancel, manual renewal and a local APScheduler recurring-order job.
- Verified-purchaser reviews with customer edit/delete controls, one-to-five-star ratings and average product ratings.
- Consumer dashboards include Dashboard, Products, Orders, Subscriptions, Deliveries, Rewards, Reviews and Settings; the profile settings panel shows the account snapshot. Farmer dashboards show relevant subscription deliveries and product reviews.
- Consumer, farmer and admin dashboards with Chart.js metrics; farmer full product edits plus order accept/reject/status controls.
- Farmers can upload or replace JPG/PNG/WEBP product photos (maximum 5 MB); images are validated and served from the local uploads folder.
- Admin management tools for users, farmers, products, categories, orders, subscriptions, deliveries and slot capacities.
- In the admin-only **Farmers** review table, the registered mobile number is visible before an application is approved; public farmer profiles do not expose it.
- Rule-based local delivery planning with Leaflet/OpenStreetMap; no ML claim.
- Responsive custom CSS design using the requested Farm2Home palette and student-readable modules.

## Stack

| Layer | Technology |
| --- | --- |
| Browser | HTML5, CSS3, vanilla JavaScript, Fetch API |
| Icons/charts/maps | Bootstrap Icons, Chart.js, Leaflet.js + OpenStreetMap |
| API | Python 3.11, Flask, Flask-CORS |
| Image handling | Pillow validates and re-encodes local product-photo uploads |
| ORM/driver | SQLAlchemy 2, PyMySQL |
| Database | MySQL 8 (or managed MySQL-compatible project DB) |
| Scheduled work | APScheduler in the local Flask process |

No React, Firebase, MongoDB, paid checkout service or real payment credentials are used.

## Project structure

```text
farm2home/
├── app.py                    Flask app factory, seed data and local scheduler
├── api.py                    REST routes, roles, validation and JSON serialization
├── config.py                 environment-backed settings
├── db.py                     SQLAlchemy engine/session/schema setup
├── models.py                 normalized ORM models and relationships
├── services.py               checkout, route grouping and renewal business rules
├── requirements.txt
├── .env.example
├── database/
│   ├── schema.sql            MySQL 8 DDL
│   ├── seed.sql              fictional, rerunnable sample data
│   └── sample_queries.sql    SELECT/JOIN/GROUP/HAVING/subquery/UPDATE/DELETE examples
├── templates/index.html      responsive multi-view storefront and dashboards
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   ├── uploads/                runtime farmer photos; user uploads are not in the source ZIP
│   └── manus-routes.json
└── tests/test_app.py
```

## Database setup

Database name: **`farm2home`**. The schema contains users, farmers, categories, products, carts/cart_items, delivery slots/capacities, subscription plans/subscriptions/items, orders/items, deliveries, payments, reviews, loyalty balances/transactions and notifications. Foreign keys, unique constraints, indexes and checks protect key relationships and values.

### MySQL 8

1. Install and start MySQL 8. Create a schema:

   ```sql
   CREATE DATABASE farm2home CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

2. Copy `.env.example` to `.env`; set `DATABASE_URL` to your local MySQL DSN and generate a private `SECRET_KEY`:

   ```text
   DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/farm2home
   SECRET_KEY=<a random private value>
   ```

   Do not commit `.env`. The local application creates tables from the ORM on first launch. It seeds fictional records once when the user table is empty (`SEED_DEMO_DATA=true`).

3. Optional manual SQL import (for a fresh schema):

   ```bash
   mysql -u root -p < database/schema.sql
   mysql -u root -p farm2home < database/seed.sql
   ```

   Set `SEED_DEMO_DATA=false` if you prefer to manage all sample records exclusively through SQL. The app's ORM seed also checks for existing user rows and will not overwrite an initialized database.

The initialized Manus Preview injects its database DSN into the development process; no `.env` with real credentials should be committed. Local setup still requires MySQL to be running and a local database to exist.

### SQLite fallback

If no `DATABASE_URL` is set, the app writes to `instance/farm2home.sqlite3`. This is useful for local demos/tests; the requested deliverable SQL schema and sample seed are MySQL 8. Do not use the fallback as production storage.

## Install and run

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit the MySQL DSN and SECRET_KEY
python app.py
```

### Windows PowerShell

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit DATABASE_URL and set SECRET_KEY in .env
python app.py
```

Open `http://127.0.0.1:5000` for a local run using the provided `.env.example` (`PORT=5000`). In the managed Preview the server listens on `0.0.0.0:3000` as configured for the managed Preview. If MySQL cannot be reached, check the DSN, make sure MySQL is running, and ensure the named database has already been created. The app starts the optional renewal scheduler unless `SCHEDULER_ENABLED=false`.

## Demo accounts

Password for each account: **`Farm2Home123!`**

| Role | Email |
| --- | --- |
| Admin | `admin@farm2home.test` |
| Consumer | `consumer@farm2home.test` |
| Farmer (Green Valley Farm) | `farmer1@farm2home.test` |
| Additional customer | `consumer2@farm2home.test` |
| Additional farmer | `farmer2@farm2home.test` |

Other seeded users follow `consumer3`–`consumer6` and `farmer3`–`farmer5` at `farm2home.test`. Demo profiles and locations are fictional. The registration flow creates farmer profiles in pending state; an administrator approves them before public product listings become visible.

## API overview

All endpoints are same-origin under `/api` and return JSON. Successful responses use `{ "success": true, "message": "...", "data": ... }`; errors use `{ "success": false, "message": "..." }`. Login state is held in an HTTP-only Flask session cookie.

| Method | Endpoint | Access / purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Public registration (consumer/farmer) |
| POST | `/api/auth/login` | Public login |
| POST | `/api/auth/logout` | Clear session |
| GET | `/api/auth/me` | Current session |
| GET | `/api/health` | API health |
| GET | `/api/categories` | Public categories |
| GET | `/api/products` | Public search/filter/sort catalog |
| GET | `/api/products/<id>` | Product detail |
| POST/PUT/DELETE | `/api/products[/<id>]` | Approved farmer's own products; admin may manage |
| POST | `/api/products/<id>/image` | Approved farmer uploads/replaces their product image using multipart field `product_image` |
| GET | `/api/farmers[/<id>]` | Approved farms and details |
| GET/POST | `/api/cart`, `/api/cart/add` | Consumer basket |
| PUT/DELETE | `/api/cart/update`, `/api/cart/remove` | Consumer basket mutations |
| GET | `/api/delivery-slots?date=YYYY-MM-DD` | Public slot availability |
| POST/GET | `/api/orders` | Consumer checkout / role-filtered order list |
| GET | `/api/orders/<id>` | Owner/admin/farmer order detail |
| GET | `/api/subscriptions/plans` | Public plans |
| GET/POST | `/api/subscriptions` | Consumer subscriptions |
| PUT/DELETE/POST | `/api/subscriptions/<id>/pause`, `/resume`, `/renew`, `/<id>` | Subscription lifecycle |
| GET | `/api/delivery/<order_id>` | Authorized route tracking |
| PUT | `/api/delivery/<id>/status` | Authorized farmer/admin delivery status |
| GET | `/api/reviews/<product_id>`, `/api/reviews/mine` | Public product reviews / signed-in customer's reviews |
| POST | `/api/reviews` | Verified-purchase review |
| PUT/DELETE | `/api/reviews/<review_id>` | Own review maintenance |
| GET/PUT | `/api/notifications`, `/api/notifications/<id>/read` | Notification center |
| PUT | `/api/notifications/read-all` | Mark own notices read |
| GET | `/api/loyalty` | Consumer balance and history |
| GET | `/api/consumer/dashboard` | Consumer metrics |
| GET | `/api/farmer/dashboard` | Farmer metrics/listings/orders |
| GET | `/api/admin/dashboard` | Admin marketplace metrics |
| GET/PUT | `/api/admin/farmers`, `/api/admin/farmers/<id>` | Admin-only farmer review; list includes applicant mobile before approval |
| GET | `/api/admin/subscriptions` | Admin subscription management list |
| GET/POST | `/api/admin/categories` | Admin category list/create |
| PUT/DELETE | `/api/admin/categories/<id>` | Admin category maintenance (delete is blocked while products use it) |
| GET | `/api/admin/products` | Admin product listing and moderation source |
| GET | `/api/admin/deliveries` | Admin delivery list and route details |
| GET/PUT | `/api/admin/slots`, `/api/admin/slots/<id>` | Slot capacities/status |
| POST | `/api/admin/run-subscriptions` | Admin/demo renewal job run |

## Subscription behavior

Plans: Weekly Fresh Basket, Bi-Weekly Family Basket and Monthly Organic Basket (plus two catalog options). Each subscription copies a plan name, frequency, amount, subscriber discount, delivery slot and address, and includes produce items. A due-period marker plus transaction guard prevents the same subscription delivery period from being generated twice. The manual demo renewal creates a linked order and advances the cadence. APScheduler checks once per hour while `python app.py` remains running. It pauses when the process stops; a multi-worker production deployment would need an external single-owner scheduler/lock rather than starting one in every worker.

## Smart Delivery Optimization

This is transparent rule-based planning, not a machine-learning system:

1. Group deliveries by service date, pincode and selected time window.
2. Assign the active delivery slot and lock/check its per-date capacity before checkout commits.
3. Map the supported Mira-Bhayandar areas to approximate demonstration coordinates.
4. Apply a greedy nearest-neighbor order from the farm hub using Haversine distance.
5. Estimate arrival time using a simple 22 km/h urban average plus 12 minutes per stop, and store the sequence/group for tracking.

Leaflet uses the OpenStreetMap.de raster tile endpoint. Attribution is displayed on the map as © OpenStreetMap contributors (ODbL) and OpenStreetMap.de. Demonstration coordinates are approximate and do not represent a live driver. The tile provider requires internet access. OpenStreetMap.de permits website embedding for noncommercial use, rate-limits by IP, and discourages bulk download/offline use; choose a separately authorized provider or host tiles yourself before a commercial or high-traffic launch.

## Order status rules

Orders advance through `Placed → Confirmed → Preparing → Out for Delivery → Delivered`. Only an unconfirmed `Placed` order may be `Rejected`; cancellation is allowed before dispatch, while `Delivered`, `Cancelled` and `Rejected` are terminal states. A skipped or repeated status transition is rejected with HTTP 409 before inventory or delivery side effects occur.

## Loyalty, reviews and simulated payments

- Delivered purchases earn 10 points for each ₹100 in the order total; an active subscriber receives a 10-point delivered-order bonus. At checkout, 100 points reduce the total by ₹10. Loyalty event keys prevent duplicate completion awards.
- A customer may review an item only after a delivered order containing that product. One review per customer/product is enforced; endpoints support edit/delete and average ratings.
- Cash on Delivery remains pending until delivery/status handling. Demo Online Payment marks the order as paid in the simulation and stores a `simulated_success` payment row. No card, gateway, or payment credential is collected.

## Tests

```bash
pytest -q
python -m compileall -q .
```

The suite uses isolated temporary SQLite databases for repeatable local behavior. A separate HTTP health check is `/healthz`; `/manus-routes.json` lists the browser page routes.

## Demonstration walkthrough

1. Log in as `consumer@farm2home.test`; browse, filter, open a product, add it to the basket and adjust quantity.
2. Place a COD or demo-online order, choose a date/window, then open Orders and Track Delivery.
3. Start/pause/resume/cancel a basket, view notifications and points, and use points on a future checkout.
4. Log in as `farmer1@farm2home.test`; add/edit product details and stock/remove listings, accept or reject incoming orders, and update preparation/delivery status.
5. Log in as `admin@farm2home.test`; review analytics, approve farmer applications, manage user access, listings, categories, subscriptions, deliveries and slot capacity, and run a due-renewal check.

## Limitations

- No permanent deployment is implied by the development Preview; no real payments, email/SMS notifications, uploaded product imagery, live GPS, address autocomplete or production tax/accounting workflow is included. Account Settings currently displays profile details but does not edit them.
- Map points and seed accounts are for demonstration only. The ORM seed is a compact app-start seed; the explicit MySQL `seed.sql` is also supplied.
- APScheduler is a single-process local demo. Use a separate scheduler with distributed locking for production/multi-worker operation.
- A stable `SECRET_KEY` must be configured in `.env` to retain sessions across restarts. Keep secrets out of source control.


## Browser assets and attribution

The custom Farm2Home icon and harvest hero artwork are bundled under `static/images/`. Browser-loaded third-party assets and map tiles are listed here so their origin remains clear in the source handoff:

- Inter and Manrope fonts: `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap`
- Bootstrap Icons 1.11.3: `https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css`
- Chart.js 4.4.4: `https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js`
- Leaflet 1.9.4 CSS/JavaScript: `https://unpkg.com/leaflet@1.9.4/dist/leaflet.css` and `https://unpkg.com/leaflet@1.9.4/dist/leaflet.js`
- OpenStreetMap.de German-style raster tiles: `https://tile.openstreetmap.de/{z}/{x}/{y}.png`; Leaflet displays linked `© OpenStreetMap contributors (ODbL) · OpenStreetMap.de` attribution. See the [tile terms](https://www.openstreetmap.de/germanstyle.html); this project's embedded use is a low-volume, noncommercial demo.
- Supplementary farmer-field photograph in the homepage markup: `https://images.unsplash.com/photo-1592982537447-7440770cbfc9?auto=format&fit=crop&w=1000&q=85`.

These external font, icon, chart, map and supplementary-photo services require internet access; the generated brand/hero artwork itself is local. The OpenStreetMap.de tile endpoint does not need a key, but its noncommercial-use and rate-limit terms still apply.


## Adding product photos

In the Farmer Dashboard's **Your produce** form, enter an optional direct, publicly reachable HTTP or HTTPS image URL. The storefront, product detail dialog and cart show that photo; if the URL is blank or the image cannot load, the produce illustration is used instead. Existing products can change or clear the image URL using **Edit product**. This demo stores image URLs; it does not upload image files. Avoid private links and links to web pages that are not direct images.

Sign in with an approved farmer account and open **Dashboard → Your produce**. In **Add produce**, select a JPG, PNG or WEBP file (up to 5 MB); if both a file and an image URL are provided, the selected file takes priority. Existing listings have an **Upload photo** or **Replace photo** button. The browser posts the image as multipart field `product_image` to `POST /api/products/<id>/image`. Pillow checks the actual format and dimensions, applies EXIF orientation, re-encodes the image, and stores it with a random filename under `static/uploads/`; the product record receives a local `/static/uploads/...` path, so the photo appears in the marketplace, details and cart. The folder is created automatically and user uploads are ignored by Git and omitted from the source ZIP. These demo uploads live on the app machine's disk: copy `static/uploads/` when moving the project or back up photos you want to keep. A temporary cloud workspace or deployment without persistent disk may not retain these files.
