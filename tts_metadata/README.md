# TTS Metadata Management System (Level 1–3)

A lightweight, robust metadata exploration system built with **FastAPI**, **PostgreSQL**, **SQLAlchemy**, and **Gradio**.

---

## 1. System Architecture

```text
               USER
                 │
                 ▼
          GRADIO FRONTEND (Port 7860)
                 │
                 │ HTTP Requests
                 ▼
          FASTAPI BACKEND (Port 8000)
                 │
                 ▼
          SQLALCHEMY QUERIES (Psycopg)
                 │
                 ▼
        POSTGRESQL DATABASE (Existing Table: tts_metadata)
```

### Architectural Principles
- **Separation of Concerns:** Gradio communicates exclusively with FastAPI via HTTP requests. It never connects directly to PostgreSQL.
- **Read-Only Operation:** Only `SELECT` queries are executed. No records are created, altered, or deleted.
- **Credential Protection:** Database credentials reside only in `backend/.env` and are never exposed to the frontend or in logs.

---

## 2. Directory Structure

```text
tts_metadata/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py         # Safe env loading & URL construction
│   │   ├── database.py       # SQLAlchemy engine & connection pool
│   │   ├── metadata.py       # Metadata router (/api/v1/metadata)
│   │   └── main.py           # FastAPI app & health endpoints
│   ├── .env                  # Local DB credentials (ignored by git)
│   ├── .env.example          # Sample environment template
│   └── requirements.txt      # Backend Python dependencies
│
├── frontend/
│   ├── app.py                # Gradio UI application
│   └── requirements.txt      # Frontend Python dependencies
│
├── check_connection.ipynb    # Diagnostic notebook to test DB & API
├── .gitignore
└── README.md
```

---

## 3. Configuration

Navigate to `tts_metadata/backend/` and configure your database parameters in `.env`:

```env
# Database Connection Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tts_db
DB_USER=postgres
DB_PASSWORD=your_password_here

# Schema & Table Configuration
METADATA_SCHEMA=public
METADATA_TABLE=tts_metadata
```

> **Note:** A template is provided in `backend/.env.example`.

---

## 4. Installation & Execution Guide

### Step 1: Install Backend Dependencies

From the project root:
```bash
pip install -r backend/requirements.txt
```

### Step 2: Start FastAPI Backend

From the `backend` directory:
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API Base URL: `http://127.0.0.1:8000`
- Interactive Swagger UI: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/health`
- DB Health Check: `http://127.0.0.1:8000/health/database`

### Step 3: Install Frontend Dependencies

From the project root:
```bash
pip install -r frontend/requirements.txt
```

### Step 4: Start Gradio Frontend

From the `frontend` directory:
```bash
python app.py
```

- Gradio Interface URL: `http://127.0.0.1:7860`

---

## 5. Verifying Database Connection

To test and verify the database connection without running FastAPI:
1. Open the provided Jupyter Notebook: `check_connection.ipynb`.
2. Run the cells sequentially to:
   - Check environment variables.
   - Verify PostgreSQL connectivity (`SELECT version()`).
   - Confirm table `tts_metadata` exists in schema `public`.
   - Count records and preview the top rows.
   - Test FastAPI endpoints if the backend server is running.

---

## 6. API Endpoints Specification

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Confirms API is operational |
| `GET` | `/health` | API service health check |
| `GET` | `/health/database` | Database connectivity status |
| `GET` | `/api/v1/metadata` | Paginated records (`limit` 1–100, `offset` >= 0) |
| `GET` | `/api/v1/metadata/count` | Total count directly from PostgreSQL |
| `GET` | `/api/v1/metadata/columns` | List of column names in metadata table |

### Example Metadata Request
```http
GET /api/v1/metadata?limit=25&offset=0
```

### Response
```json
{
  "items": [
    {
      "id": 1,
      "sr_no": 1,
      "record_date": "2026-12-08",
      "language": "Sanskrit",
      "gender": "Male",
      "source": "You Tube",
      "status": "Done"
    }
  ],
  "limit": 25,
  "offset": 0,
  "returned": 1
}
```

---

## 7. Frontend Features

- **Dashboard Summary:** Displays total database record count, displayed records count, pagination status, and real-time backend/database connection status.
- **Read-Only Dataframe:** Safely displays paginated records as a clean table.
- **Pagination Controls:** Navigate with `Previous Page` and `Next Page` buttons, and adjust page size (10, 25, 50, 100).
- **Search & Filtering:** Fast in-memory search and dropdown filters (Language, Gender, Status) for records on the currently loaded page.
- **One-Click Refresh:** Refreshes data and syncs with the database without page reload.
