# Run Farm2Home in VS Code

## What you need

- VS Code with the Microsoft **Python** extension.
- Python 3.11 or newer (Python 3.12 recommended).
- Internet access for the web fonts, icons, charts and map tiles.
- **MySQL is optional for a local demo**: the app has a SQLite fallback.

## 1. Open the project

Extract `farm2home-vscode-project.zip`, then in VS Code choose **File → Open Folder…** and select the extracted `farm2home` folder. Open **Terminal → New Terminal** so commands run from the project root.

## 2. Create a virtual environment and install packages

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks environment activation, allow it only in the current terminal, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

In VS Code, press **Ctrl+Shift+P** (macOS: **Cmd+Shift+P**), choose **Python: Select Interpreter**, and select the interpreter inside this project's `.venv` folder.

## 3. Configure the local database

Open `.env` in VS Code. For the quickest local demo, use SQLite by setting:

```dotenv
DATABASE_URL=sqlite:///instance/farm2home.sqlite3
SECRET_KEY=replace-with-a-random-secret
PORT=5000
SCHEDULER_ENABLED=true
SESSION_COOKIE_SECURE=false
```

Generate a random session secret in the VS Code terminal with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the generated value into `SECRET_KEY` in `.env`. Keep `.env` private; it is excluded from the project ZIP's source list and ignored by Git.

### Optional: use MySQL 8

Start MySQL and create the database:

```sql
CREATE DATABASE farm2home CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Then set `DATABASE_URL` in `.env` to your local connection, for example:

```dotenv
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/farm2home
```

Replace the example credentials with your own. The application creates the tables and inserts the demo data on first startup when the database is empty; you do not need to import `database/schema.sql` or `database/seed.sql` to start the app.

## 4. Start the app

With the virtual environment active, run this from the project root:

```powershell
python app.py
```

Open **http://127.0.0.1:5000**. Leave that terminal running while you use the app. Stop it with **Ctrl+C**.

## 5. Sign in to a demo account

All sample accounts use the password `Farm2Home123!`.

| Role | Email |
| --- | --- |
| Consumer | `consumer@farm2home.test` |
| Farmer | `farmer1@farm2home.test` |
| Administrator | `admin@farm2home.test` |

These are fictional demo accounts. The local APScheduler renewal task runs in this app process; for a single-machine demo, keep one server process running.

In the admin dashboard, open **Farm applications** or **Marketplace management → Farmers** to see each applicant's registered mobile number before approving or rejecting the farm. This phone number is shown in admin-only views, not on the public farm directory.

## 6. Run the tests

```powershell
python -m pytest -q
```

The repository includes the MySQL schema, sample seed SQL and example queries under `database/` for manual inspection or database coursework. The bundled tile provider is intended for low-volume, noncommercial demonstration use; review the map-tile terms in `README.md` before changing how the app is deployed.


## 7. Upload product photos

Sign in as an approved farmer, open **Dashboard → Your produce**, and choose a JPG, PNG or WEBP file (maximum 5 MB) in **Upload product photo**. If you select a file and also enter an image URL, the file takes priority. Click **Upload photo** or **Replace photo** beside an existing product to change its image. Uploaded images are validated, re-encoded, and saved in `static/uploads/`; the application creates that folder automatically. The product image is served from the local Flask app, so you do not need an image-hosting account or a public URL. Locally uploaded photos are intentionally excluded from Git and the source ZIP; copy `static/uploads/` yourself if you want to move/back up those photos.
