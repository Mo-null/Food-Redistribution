# Food Redistribution Platform – Backend API

A REST API that connects food **donors** (restaurants, shops, households) with **recipients** (charities, shelters, individuals) before the food expires. Donors post surplus food, the system proposes the best-fitting recipient, and a **coordinator** oversees organizations and disputes.

**Stack:** Python 3.11+ (developed on 3.14) · FastAPI · SQLAlchemy 2 · PostgreSQL · JWT auth · APScheduler · scikit-learn / SciPy · Google Gemini (optional)

## Quick start

Requires Python 3.11+ and a running PostgreSQL server.

```bash
# 1. Create the database
psql -U postgres -c "CREATE DATABASE food_platform;"

# 2. Create a virtual environment and install dependencies
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
python -m pip install -r requirements.txt

# 3. Configure
copy .env.example .env           # macOS/Linux: cp .env.example .env
# then edit .env: set DATABASE_URL and SECRET_KEY (see below)

# 4. Create the tables and the first coordinator account
python create_tables.py
python create_coordinator.py

# 5. (Optional) train the matching model, see "Matching model"
python train_match_model.py

# 6. Run the API
python -m uvicorn main:app --reload
```

The interactive API docs are then at <http://127.0.0.1:8000/docs>.

### Configuration (`.env`)

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | PostgreSQL connection string |
| `SECRET_KEY` | yes | Signs login tokens. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `CORS_ORIGINS` | no | Allowed frontend origins, comma-separated (default `http://localhost:5173`) |
| `GEMINI_API_KEY` | no | Enables free-text donation parsing |
| `GEMINI_MODEL` | no | Gemini model name (default `gemini-2.5-flash`) |
| `LLM_MOCK` | no | `true` uses a fake parser, so no API key is needed |

## How it works

### Roles

- **Donor** – posts, edits and cancels donations, and confirms or reports pickups.
- **Recipient** – receives match proposals and accepts or declines them.
- **Coordinator** – verifies organizations, runs matching manually, and resolves disputes. Created only with `create_coordinator.py`, never through public registration.

Organizations (`is_organization`) register as *pending*. Until a coordinator approves them, an organization cannot post donations or be matched as a recipient.

### Lifecycle

```
Donation:  active → matched → fulfilled
                  ↘ expired / cancelled

Match:     proposed → accepted → fulfilled
                  ↘ rejected (declined · ignored · no_show · withdrawn)
```

- A proposal not answered within **30 minutes** closes as *ignored* and the donation returns to the pool.
- A recipient has at most one open match at a time, and a donation is never re-offered to a recipient who declined, ignored, no-showed, or was withdrawn from it.
- If an accepted pickup is never confirmed, the match auto-closes as *withdrawn* **24 hours after the donation expires**. Nobody is penalised, because the system cannot tell whether the pickup happened. Both sides are notified.
- A donor who reports a failed pickup must state whether the recipient was at fault (*no_show*, which lowers their reliability) or not (*withdrawn*, no penalty).

### Matching

A matching round runs every 10 minutes, right after each new donation, and on demand (`POST /matching/run`, coordinator only). A database advisory lock ensures only one round runs at a time.

1. Eligible pairs are donation/recipient pairs within **10 km**.
2. Each pair gets a **rule score**: urgency 0.40 + proximity 0.25 + capacity fit 0.15 + recipient reliability 0.20.
3. If a trained model exists, its predicted success probability is blended 50/50 with the rule score. Without a model, the rule score alone is used.
4. The **Hungarian algorithm** (`scipy.optimize.linear_sum_assignment`) picks the assignment that maximises the total score across all pairs, so one recipient is never given several donations at once.

### Reliability

A recipient's reliability is derived from their match outcomes (there is no separate counter to drift out of sync): the share of fulfilled pickups among fulfilled + no-show, shrunk toward a neutral 0.5 until they have about 10 resolved pickups. Declines do not count against anyone. The same match history also feeds the ML features.

### Privacy

- Until a recipient **accepts** a match, they see the donor's location only as coordinates rounded to about 1 km plus the distance. The exact location is revealed on acceptance.
- Donors see the recipient's reliability score inside the match; recipients see the donor's name and verification status.
- `GET /reliability/{id}` is limited to the user themselves and coordinators.
- Passwords are hashed with bcrypt (max 72 bytes). Usernames and emails are stored lowercase.

### Donation text parsing

`POST /donations/parse` turns a free-text message ("20 portions of rice and curry, good until 9pm") into form fields using Gemini. It only suggests values; the donor reviews and submits the normal create request. Failures return a clear message and never block manual entry.

## API overview

All routes except register and login need `Authorization: Bearer <token>`.

| Area | Endpoints |
|---|---|
| Users | `POST /users/register` · `POST /users/login` · `GET/PATCH /users/me` · `POST /users/me/change-password` · `GET /users/pending-verifications` *(coordinator)* · `POST /users/{id}/verify` *(coordinator)* |
| Donations *(donor)* | `POST /donations/parse` · `POST /donations` · `GET /donations/mine` · `GET/PATCH/DELETE /donations/{id}` |
| Matches | `GET /matches` · `GET /matches/{id}` · `POST /matches/{id}/accept` and `/decline` *(recipient)* · `POST /matches/{id}/confirm` and `/reject` *(donor)* |
| Disputes | `POST /disputes` *(either party)* · `GET /disputes` *(coordinator)* · `POST /disputes/{id}/resolve` *(coordinator)* |
| Notifications | `GET /notifications` · `POST /notifications/{id}/read` |
| Other | `GET /reliability/{id}` · `POST /matching/run` *(coordinator)* |

## Matching model

`python train_match_model.py` trains a small model that predicts whether a proposed match will end in a completed pickup. It uses the real match history once there are at least 200 resolved matches. Otherwise it **falls back to a synthetic dataset**. It compares logistic regression and gradient boosting against the rule score on a time-ordered hold-out set, and saves a model only if it beats the rule score. Without a saved model the app simply uses the rule score.

**Important limitation:** the synthetic labels are generated by a formula I wrote using the same features, so the reported AUC on synthetic data demonstrates that the pipeline works. It is not evidence that the model predicts real-world behaviour. The 50/50 blend weight is likewise unvalidated. The intended workflow is to run the platform, collect real outcomes, and retrain. The saved model (`match_model.joblib`) is tied to the scikit-learn version, so it is git-ignored and should be retrained per environment.

## Development

```bash
python -m pip install -r requirements-dev.txt
ruff check .          # lint: unused imports, import order, modern typing
```

### Checks

The scripts below are end-to-end checks written during development. They need an **empty development database** and call the router code directly. `reset_db.py` **deletes all data**: never point it at a database you care about.

```bash
python reset_db.py && python phase1_checks.py     # validation rules, expiry handling
python reset_db.py && python phase2_checks.py     # reliability, privacy, access control
python reset_db.py && python smoke_test_step1.py  # full match lifecycle
python reset_db.py && python create_coordinator.py
```

### Project layout

```
main.py              app, CORS, scheduler
db/                  engine and session
models/              SQLAlchemy tables (users, donations, matches, disputes, notifications)
schemas/             Pydantic request/response models and validation
routers/             HTTP endpoints
services/            matching engine, features and model, reliability, notifications, LLM parsing
utils/               auth (JWT), password hashing, role dependencies
create_tables.py  reset_db.py  create_coordinator.py  train_match_model.py
```

## Known limitations and future work

- No database migrations yet: schema changes use `reset_db.py` during development. Alembic is the natural next step.
- The end-to-end checks should become a proper pytest suite with a dedicated test database.
- List endpoints are not paginated, and there is no rate limiting (login and the paid parsing endpoint are the first candidates).
- Login tokens last 60 minutes and cannot be revoked or refreshed.
- Donors have no reliability score; only recipients are scored.
- The platform does not exchange contact details or chat between matched parties; coordination happens outside the app.
- Notifications are plain messages without a link to the related match.
- The matching model features use the UTC hour of day, not local time.
- Models use the classic SQLAlchemy `Column` style, which still works in SQLAlchemy 2.