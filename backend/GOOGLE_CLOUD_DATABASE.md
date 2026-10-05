# Google Cloud Database and Retention

## Database

Use Cloud SQL for PostgreSQL. The application already uses PostgreSQL through SQLAlchemy, so this avoids changing the database model or alert APIs.

Configure the Cloud Run API service and retention job to attach the same Cloud SQL instance. Grant each runtime service account the Cloud SQL Client role. Provide `DATABASE_URL` from Secret Manager, never from a checked-in file. With a Cloud SQL Unix socket attachment, the URL format is:

Use these default resource names unless you prefer different ones:

- Cloud SQL instance: `ball-mill-pdm-db`
- Database: `ball_mill_pdm`
- Application database user: `pdm_app`
- Secret Manager secret: `pdm-database-url`

The connection URL format is:

```text
postgresql+psycopg2://pdm_app:URL_ENCODED_PASSWORD@/ball_mill_pdm?host=/cloudsql/PROJECT_ID:REGION:ball-mill-pdm-db
```

URL-encode the password before storing the URL as a secret. The existing backend initializer creates the alert and servicing-feedback tables and the indexes needed for time-based retention; no manual schema migration is required.

## Six-Month Retention

Build the backend image once and use it for both the API service and a Cloud Run Job. Configure the job to run `python retention_job.py`, attach it to the same Cloud SQL instance, and grant it access to the same `DATABASE_URL` secret.

Create an authenticated Cloud Scheduler job that invokes the Cloud Run Job once per hour. The retention task uses the database clock and the cutoff `CURRENT_TIMESTAMP - INTERVAL '6 months'`. It transactionally deletes expired servicing feedback and alert rows. The first run also removes any existing rows already older than six months. The current application does not persist telemetry samples separately; websocket samples exist only in application memory.

The schedule means expired rows are removed within approximately one hour of crossing the six-month cutoff. Monitor Cloud Scheduler and Cloud Run Job failures so a failed run is visible and can be retried.

## Storage Capacity

Six-month retention limits how long records remain, but it cannot guarantee the disk never fills: a high enough incoming alert rate can exhaust storage within six months. Enable Cloud SQL storage auto-increase and configure Cloud Monitoring alerts for storage utilization, failed scheduled jobs, and database availability. Choose disk capacity and alert thresholds based on measured ingestion volume.

The application does not connect to Google Cloud until the Cloud SQL instance, Cloud Run attachment, runtime identity permissions, and Secret Manager value are configured. Local development can continue using a PostgreSQL `DATABASE_URL` supplied through the environment.

## Container Build and Deployment

The backend Dockerfile listens on Cloud Run's `PORT` (default 8080) and runs as a non-root user. Build from the repository root so the backend directory is the Docker context:

```sh
PROJECT_ID="your-project-id"
REGION="your-region"
DATABASE_INSTANCE_NAME="ball-mill-pdm-db"
DATABASE_NAME="ball_mill_pdm"
DATABASE_USER="pdm_app"
DATABASE_SECRET="pdm-database-url"
INSTANCE_CONNECTION_NAME="${PROJECT_ID}:${REGION}:${DATABASE_INSTANCE_NAME}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/pdm-images/ball-mill-pdm:latest"
API_SERVICE_ACCOUNT="pdm-api@${PROJECT_ID}.iam.gserviceaccount.com"
RETENTION_SERVICE_ACCOUNT="pdm-retention@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_SERVICE_ACCOUNT="pdm-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud services enable \
	artifactregistry.googleapis.com \
	run.googleapis.com \
	sqladmin.googleapis.com \
	secretmanager.googleapis.com \
	cloudscheduler.googleapis.com

gcloud artifacts repositories create pdm-images \
	--repository-format=docker \
	--location="$REGION"

gcloud auth configure-docker "${REGION}-docker.pkg.dev"
docker build -t "$IMAGE" backend
docker push "$IMAGE"
```

Create the Cloud SQL instance, database, database user, three service accounts, and `DATABASE_URL` secret before deploying. Use the names above for the database objects. Add the URL value through Secret Manager; do not put it in a shell command, manifest, or source file. Grant the API and retention service accounts `roles/cloudsql.client` and `roles/secretmanager.secretAccessor`. Grant the Scheduler service account `roles/run.invoker` on the retention job after creating it.

Deploy the API privately by default. The app currently has no user authentication flow, so do not expose it publicly until you choose and configure an appropriate access layer (for example, an authenticated gateway or identity-aware proxy).

```sh
gcloud run deploy ball-mill-pdm-api \
	--image="$IMAGE" \
	--region="$REGION" \
	--service-account="$API_SERVICE_ACCOUNT" \
	--add-cloudsql-instances="$INSTANCE_CONNECTION_NAME" \
	--set-secrets="DATABASE_URL=${DATABASE_SECRET}:latest" \
	--port=8080 \
	--no-allow-unauthenticated

gcloud run jobs deploy ball-mill-pdm-retention \
	--image="$IMAGE" \
	--region="$REGION" \
	--service-account="$RETENTION_SERVICE_ACCOUNT" \
	--set-cloudsql-instances="$INSTANCE_CONNECTION_NAME" \
	--set-secrets="DATABASE_URL=${DATABASE_SECRET}:latest" \
	--command=python \
	--args=retention_job.py \
	--tasks=1 \
	--parallelism=1 \
	--max-retries=1 \
	--task-timeout=5m

gcloud run jobs execute ball-mill-pdm-retention --region="$REGION" --wait

gcloud scheduler jobs create http ball-mill-retention-hourly \
	--location="$REGION" \
	--schedule="0 * * * *" \
	--time-zone="UTC" \
	--uri="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/ball-mill-pdm-retention:run" \
	--http-method=POST \
	--oauth-service-account="$SCHEDULER_SERVICE_ACCOUNT" \
	--oauth-token-scope="https://www.googleapis.com/auth/cloud-platform"
```

Cloud Run service invocation remains private in this example; frontend-to-API authentication and deployment are separate configuration decisions and must be completed before users can access the deployed UI.