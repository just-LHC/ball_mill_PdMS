# Ball Mill Predictive Maintenance

## Local Development

The local workflow runs PostgreSQL in Docker and the API/frontend in the workspace. This keeps the complete development setup local and avoids requiring Google Cloud or PLC access.

Requirements: Docker Compose, Python 3.11+, Node.js/npm, and the backend/frontend dependencies installed.

1. Copy `.env.example` to `.env` and change `LOCAL_DB_PASSWORD` to a local-only password. `.env` is ignored by Git.
2. Start the local PostgreSQL container:

   ```sh
   docker compose up -d database
   ```

3. In a backend terminal, load the local password and start the API:

   ```sh
   cd /workspaces/ball_mill_PdMS
   set -a
   . ./.env
   set +a
   export DATABASE_URL="postgresql+psycopg2://pdm_app:${LOCAL_DB_PASSWORD}@127.0.0.1:5433/ball_mill_pdm"
   cd backend
   python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

   On API startup, the existing initializer creates the alert and servicing-feedback tables and indexes in the local database.

4. In a separate frontend terminal, start Vite:

   ```sh
   cd /workspaces/ball_mill_PdMS/frontend
   npm ci
   npm run dev -- --host 0.0.0.0 --port 5173
   ```

5. Open `http://localhost:5173`. Vite proxies `/api` and `/ws` to the local API on port 8000. The database is available to local tools on `127.0.0.1:5433`.

Local records persist in the `local_postgres_data` Docker volume. Stop PostgreSQL with `docker compose down`; this keeps the data. Do not use `docker compose down -v` unless you intend to permanently delete the local database.

To run the six-month cleanup manually against the local database, load the same `.env` and `DATABASE_URL` as above, then run `python3 backend/retention_job.py` from the repository root. This deletes alert and servicing-feedback records older than six calendar months.

All telemetry remains labeled demo data. No PLC, SIMATIC server, historian, or Google Cloud connection is made by this local setup.

For future Cloud SQL/Cloud Run deployment, see [backend/GOOGLE_CLOUD_DATABASE.md](backend/GOOGLE_CLOUD_DATABASE.md).