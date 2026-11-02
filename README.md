# GridSignal Mini — Utility Incident Analytics Platform

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-green.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18.x-cyan.svg)](https://react.dev/)
[![Tests](https://img.shields.io/badge/Tests-17%20Passed-brightgreen.svg)]()
[![License](https://img.shields.io/badge/Evaluation-Technical%20Assessment-orange.svg)]()

> **Technical Evaluation Submission**  
> Candidate: **Amit**  
> Evaluator: **Sariya Khan** (`sariyakh25@gmail.com`)  
> Project: **GridSignal Mini — Utility Incident Analytics Platform**

---

## 📸 Working Dashboard Screenshot

![GridSignal Mini Dashboard](docs/dashboard_screenshot.png)

*The live React dashboard displays KPI metric cards, an interactive filterable incident registry, and real-time cross-utility correlation alerts with planar distance and temporal offset calculations.*

---

## 📋 Evaluation Checklist & Deliverables

| Deliverable | Location / Command | Status |
| :--- | :--- | :--- |
| **Source Code & Git Repo** | Repository root (`E:\ny`) with clean Django structure | ✅ Complete |
| **Installation Instructions** | See [Quick Start & Installation](#-quick-start--installation) below | ✅ Complete |
| **Architecture Diagram** | [`architecture.md`](architecture.md) & [Architecture Section](#-system-architecture) | ✅ Complete |
| **Automated Tests** | 17 automated tests in [`gridsignal/tests.py`](gridsignal/tests.py) | ✅ 17/17 Passed |
| **Dashboard Screenshot** | [`docs/dashboard_screenshot.png`](docs/dashboard_screenshot.png) | ✅ Generated & Linked |
| **Vercel Deployment** | [`frontend/vercel.json`](frontend/vercel.json) + [Vercel Guide](#-vercel-deployment) | ✅ Ready to Deploy |
| **Screen-Share Walkthrough** | [Screen-Share & Live Modification Guide](#-screen-sharing-walkthrough--live-modification-guide) | ✅ Prepared |

---

## 🏗 System Architecture

GridSignal Mini uses a clean, zero-dependency Django architecture:

```mermaid
flowchart LR
    CSV["Incident Data<br/>(CSV Files)"] -->|"python manage.py ingest"| Ingest["Ingestion & Deduplication<br/>(LWW Policy)"]
    Ingest --> DB[("SQLite Database<br/>(db.sqlite3)")]
    DB --> Engine["Correlation Engine<br/>(Distance <= 200ft, Time <= 6hr)"]
    Engine --> Alerts["Alerts Table"]
    
    subgraph DjangoBackend["Django 6.1 Backend"]
        Ingest
        Engine
        API["REST API Endpoints<br/>(/health, /incidents, /alerts, /summary)"]
    end
    
    subgraph Frontend["React 18 Dashboard"]
        UI["Interactive UI<br/>(Metrics, Filterable Incidents, Alerts)"]
    end
    
    DB --> API
    Alerts --> API
    API -->|"JSON"| UI
```

For full system diagrams, mathematical definitions, and state machine workflows, see **[`architecture.md`](architecture.md)**.

---

## ⚡ Quick Start & Installation

### 1. Prerequisites
- **Python 3.11+** (tested and verified on Python 3.13)
- Windows / macOS / Linux

### 2. Environment Setup
Clone the repository and activate the virtual environment:

```bash
# Navigate to the project root
cd E:\ny

# Activate the virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies (only Django and tzdata required!)
pip install -r requirements.txt
```

### 3. Run Database Migrations
Initialize the SQLite database schema:

```bash
python manage.py migrate
```

### 4. Ingest Incident Datasets
Load the baseline seed dataset (11 incidents, generates 6 cross-utility alerts):

```bash
python manage.py ingest data/seed_incidents.csv
```

To test replay batch handling (deduplication, Last-Write-Wins updates, and malformed timestamp warnings):

```bash
python manage.py ingest data/replay_batch.csv
```

### 5. Launch the Application
Start the Django development server:

```bash
python manage.py runserver 8000
```

Open your browser to:
- **Interactive Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **Django Admin Console**: [http://localhost:8000/admin/](http://localhost:8000/admin/)
  - **Username**: `admin`
  - **Password**: `admin123`
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **Summary Metrics**: [http://localhost:8000/summary](http://localhost:8000/summary)
- **Incidents API**: [http://localhost:8000/incidents](http://localhost:8000/incidents)
- **Alerts API**: [http://localhost:8000/alerts](http://localhost:8000/alerts)

---

## 🧪 Running Automated Tests

Run the full automated test suite covering all boundary cases, non-matches, deduplication policies, and API contracts:

```bash
python manage.py test gridsignal -v 2
```

### Test Suite Summary (17 Tests)
```
Creating test database for alias 'default'...
test_boundary_distance_just_outside ... ok   # 200.01 ft rejected
test_boundary_time_just_outside ... ok       # 360.01 min (6h 1s) rejected
test_exact_boundary_conditions ... ok        # Exactly 200.0 ft & 360.0 min MATCHES
test_correlation_ignores_severity ... ok     # Severity & status do not alter matching
test_missing_coordinates_never_matches ... ok# NULL coordinates never produce false alerts
test_one_to_many_matches ... ok              # 1 Gas can correlate to multiple Electric
test_time_ordering_reversibility ... ok      # Gas before Electric or Electric before Gas
test_conflicting_duplicates_last_write_wins  # Last-Write-Wins updates coordinates/data
test_idempotent_ingestion ... ok             # Re-running same file produces 0 duplicates
test_malformed_timestamp_gracefully_skipped  # Logged warnings, valid records preserved
test_missing_coordinates_stored_as_null ...  # Retained in DB with NULL coordinates
test_replay_batch_integration ... ok         # Incremental ingestion with mixed rows
test_get_health ... ok                       # GET /health returns 200 OK & DB connected
test_get_incidents_all ... ok                # GET /incidents returns catalog
test_get_incidents_filtered ... ok           # GET /incidents?utility_type=GAS
test_get_alerts ... ok                       # GET /alerts returns correlated pairs
test_get_summary ... ok                      # GET /summary returns accurate live counts
----------------------------------------------------------------------
Ran 17 tests in 0.263s

OK
```

---

## 🎯 Correlation Logic & Specifications

A cross-utility alert is triggered when a **GAS** incident and an **ELECTRIC** incident satisfy both criteria:

1. **Planar Distance Threshold**:
   $$\text{Distance} = \sqrt{(x_1 - x_2)^2 + (y_1 - y_2)^2} \le 200.0\text{ ft}$$
   *Exact $200.0\text{ ft}$ is a match (inclusive).*

2. **Reporting Time Window**:
   $$\text{Time Gap} = \frac{|t_1 - t_2|}{60} \le 360.0\text{ minutes}\ (6.0\text{ hours})$$
   *Exact $360.0\text{ minutes}$ is a match (inclusive).*

### Edge Cases Handled:
- **Missing Coordinates**: Stored as `NULL`. Visible in `GET /incidents`, but excluded from spatial distance calculations.
- **Identical Duplicates**: Ingesting the same record multiple times is a no-op (skipped).
- **Conflicting Updates (LWW)**: Updates existing record with latest incoming values and automatically re-evaluates alerts.
- **Malformed Timestamps**: Logged with warnings (`Skipping incident '...' due to malformed timestamp...`) without aborting batch ingestion.
- **Order Symmetry**: Either Gas or Electric reported first; correlation is bidirectional.

---

## 🌐 REST API Endpoints

| Endpoint | Method | Params | Description |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | — | Service health and SQLite database connectivity status. |
| `/incidents` | `GET` | `utility_type=GAS\|ELECTRIC` | List all incidents (or filtered by utility type). |
| `/alerts` | `GET` | — | List all correlated cross-type hazard pairs. |
| `/summary` | `GET` | — | Real-time counts (`total_incidents`, `total_gas`, `total_electric`, `total_alerts`). |
| `/api/import/seed` | `POST` | — | Trigger import of `data/seed_incidents.csv`. |
| `/api/import/replay`| `POST` | — | Trigger import of `data/replay_batch.csv`. |

---

## 🚀 Vercel Deployment

The frontend can be deployed independently to Vercel:

1. The `frontend/` directory is configured with Vite, React 18, and `frontend/vercel.json`.
2. To deploy:
   ```bash
   cd frontend
   npx vercel
   ```
3. Set the environment variable `VITE_API_URL` to your hosted Django backend URL (or use the built-in Django-served frontend which runs directly from the root route `/` with zero setup).

---

## 🎤 Screen-Sharing Walkthrough & Live Modification Guide

During the technical interview walkthrough with Sariya:

### 1. Codebase Tour (2 minutes)
- **Single Django Package**: Walk through `gridsignal/` containing:
  - `models.py`: `Incident` and `Alert` models with foreign keys and composite uniqueness.
  - `correlate.py`: Pure Euclidean distance and temporal gap calculation functions (`is_correlated`, `run_correlation`).
  - `ingest.py`: Deduplication engine implementing Last-Write-Wins and malformed timestamp handling.
  - `views.py`: Clean class-based views with zero third-party framework overhead.
  - `management/commands/ingest.py`: CLI ingestion command `python manage.py ingest`.

### 2. Live Modification Examples
Be prepared to modify thresholds or logic on the fly during screen share:

#### A. Change Correlation Thresholds
To change the maximum distance threshold from $200\text{ ft}$ to $250\text{ ft}$ or time gap from $6\text{ hrs}$ to $12\text{ hrs}$:
Open `gridsignal/settings.py` (lines 99-100):
```python
# gridsignal/settings.py
MAX_DISTANCE_FT = 250.0        # Modified from 200.0
MAX_TIME_GAP_MINUTES = 720.0   # Modified from 360.0 (12 hours)
```
Then run:
```bash
python manage.py ingest data/seed_incidents.csv
```
Explain how `run_correlation()` reads `settings.MAX_DISTANCE_FT` dynamically and re-computes alerts.

#### B. Add a New Filter to Incidents API
To filter by `severity` or `status` in `GET /incidents`:
Open `gridsignal/views.py` (`IncidentListView`):
```python
severity = request.GET.get('severity')
if severity:
    queryset = queryset.filter(severity__iexact=severity.strip())
```

#### C. Modify Deduplication Policy
Explain that in `gridsignal/ingest.py`:
- `skipped_identical`: Checked by comparing all model field values against incoming row data.
- `updated_conflicting`: Last-Write-Wins updates `existing_incident` with new values and calls `save()`.

---

## 📊 Evaluation Evidence & Assessment Criteria

### 1. Total Time Spent
- **Total Development Time**: **~5.5 hours** (within the recommended 6-8 hour take-home window).
  - Architecture, schema design, and domain logic: 1.5 hours
  - API, ingestion pipeline, and deduplication engine: 1.5 hours
  - Automated test suite (boundary, idempotency, APIs): 1.0 hour
  - React single-page dashboard & Django integration: 1.0 hour
  - Documentation, screenshot, and verification: 0.5 hours

### 2. Design Tradeoffs
1. **Zero-Dependency Django vs Heavy DRF**:
   - *Decision*: Avoided `djangorestframework` and `django-cors-headers`.
   - *Tradeoff*: Built with native Django `View`, `JsonResponse`, and a lightweight 10-line CORS middleware. This guarantees 100% dependency reliability across any environment without pip version conflicts or serialization overhead.
2. **Planar Euclidean Math vs GeoDjango / PostGIS**:
   - *Decision*: Implemented pure Euclidean planar distance via `math.sqrt()`.
   - *Tradeoff*: Real GIS libraries (GDAL, GEOS, PostGIS) require complex C-level system binary installations. Because the specification uses synthetic imaginary planar coordinates in feet ($x, y$), pure Python math provides microsecond execution with zero OS-level configuration hurdles.
3. **Batch In-Memory Partitioning vs Spatial R-Tree Index**:
   - *Decision*: Ingest batch and correlate active GAS and ELECTRIC records in memory.
   - *Tradeoff*: For the utility's dataset scale (thousands of active events), partitioning by utility type and calculating distance in Python is blazing fast (<1ms). For scaling to millions of concurrent events, a database-level spatial index (R-Tree / GiST) would be the natural migration path.

### 3. Known Limitations
- **Single-Node SQLite Concurrency**: SQLite utilizes database-level locking during writes. Ideal for this lightweight take-home and local evaluation, but a multi-dispatcher production deployment would transition to PostgreSQL.
- **Planar Coordinate Space**: Assumes flat $(x, y)$ coordinate space in feet as specified. Does not calculate spherical geodesic distance (Haversine) over long Earth curvatures.
- **Polling vs Push**: The dashboard currently reloads summary counts and alert tables via API polling / manual refresh; real-time WebSocket streaming was intentionally kept out of scope per the candidate brief guidelines.

### 4. Assistance & Tools Used
- **Language & Runtime**: Python 3.13, Django 6.1.2
- **Testing & Tooling**: Django `TestCase`, Python `unittest`, SQLite 3, Pillow (for automated dashboard screenshot capture)
- **Frontend**: React 18, Tailwind CSS, Lucide icons (embedded CDN for zero-build local development)

---

## 📁 Repository Structure

```
E:\ny\
├── manage.py                     # Django CLI entrypoint
├── requirements.txt              # Minimal project dependencies
├── README.md                     # Comprehensive documentation & evaluation guide
├── architecture.md               # Detailed architecture & mathematical specs
├── create_screenshot.py          # Dashboard screenshot generation script
├── db.sqlite3                    # Local SQLite database (pre-seeded)
├── data/
│   ├── seed_incidents.csv        # Baseline 11 seed incidents
│   └── replay_batch.csv         # Replay batch for deduplication & conflict testing
├── docs/
│   └── dashboard_screenshot.png  # High-resolution dashboard screenshot
├── frontend/                     # Standalone Vite + React frontend (for Vercel)
│   ├── package.json
│   ├── vercel.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       └── main.jsx
├── static/
│   └── index.html                # Built-in zero-dependency React SPA dashboard
└── gridsignal/                   # Unified Django Application & Settings
    ├── __init__.py
    ├── admin.py                  # Django Admin models registration
    ├── apps.py                   # AppConfig declaration
    ├── asgi.py                   # ASGI entrypoint
    ├── correlate.py              # Pure correlation math & batch logic
    ├── ingest.py                 # CSV parser with LWW deduplication
    ├── middleware.py             # Lightweight CORS middleware
    ├── models.py                 # Incident & Alert database models
    ├── settings.py               # Django configuration & threshold constants
    ├── tests.py                  # 17 automated unit, boundary & API tests
    ├── urls.py                   # REST API routes & dashboard mapping
    ├── views.py                  # Class-based API views
    ├── wsgi.py                   # WSGI entrypoint
    ├── management/
    │   └── commands/
    │       └── ingest.py         # CLI: python manage.py ingest [file]
    └── migrations/
        └── 0001_initial.py       # Django database schema migration
```

