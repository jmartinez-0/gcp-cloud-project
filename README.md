# Firebase-authenticated Flask API on Cloud Run

This guide documents the repeatable deployment pattern for a Flask API that:

- authenticates requests with Firebase Authentication;
- reads and writes JSON data in a Google Cloud Storage bucket; and
- runs as a container on Cloud Run.

The frontend obtains a Firebase ID token and sends it to the API as a bearer token:

```text
Authorization: Bearer <firebase-id-token>
```

The API verifies the token before allowing access to its routes.

## Architecture

The deployment can use separate Google Cloud projects:

| Component | Project or service |
| --- | --- |
| Frontend Firebase application | Firebase project |
| Cloud Run service and runtime identity | Compute project |
| User data bucket | Bucket project, which may be the compute project |

The Cloud Run service account does not need to belong to the Firebase project. It needs permission to access the required resources in each project.

The distinction between identity and project is important:

- The **Cloud Run service account** is the identity used by the backend.
- `FIREBASE_PROJECT_ID` identifies the Firebase project whose tokens the backend accepts.
- `GCS_BUCKET_NAME` identifies the bucket containing the API data.

## Repository layout

The cloud API is under `gcs-flask-api/`:

```text
gcs-flask-api/
  app.py
  Dockerfile
  requirements.txt
```

The local file-backed API is separate:

```text
gcs-flask-api/
  app_local.py
  Dockerfile.local
  requirements-local.txt
```

Use `app.py` for Cloud Storage and `app_local.py` for local JSON-file testing.

## Backend configuration

The cloud API reads these environment variables:

| Variable | Required | Purpose |
| --- | --- | --- |
| `FIREBASE_PROJECT_ID` | Yes | Firebase project that issues the frontend ID tokens |
| `GCS_BUCKET_NAME` | Yes | Cloud Storage bucket used by the API |
| `PORT` | Provided by Cloud Run | Port the container should listen on |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Local only | Optional path to a service-account JSON file |
| `GOOGLE_APPLICATION_CREDENTIALS` | Local only | Alternative local credentials path |

For Cloud Run, do not put a service-account JSON key in the image or source repository. When neither local credentials variable is set, the Firebase Admin SDK and the Google Cloud Storage client use Application Default Credentials from the Cloud Run runtime service account.

The Firebase initialization uses the attached Cloud Run identity for credentials while explicitly validating tokens against the Firebase project:

```python
firebase_admin.initialize_app(
    options={"projectId": os.environ["FIREBASE_PROJECT_ID"]}
)
```

The service account's home project and the Firebase project may be different.

## Prerequisites

Install and authenticate the Google Cloud CLI:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project <COMPUTE_PROJECT_ID>
```

Enable the services needed by the deployment:

```bash
gcloud services enable run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  --project=<COMPUTE_PROJECT_ID>
```

Create or identify:

- a Firebase project with Authentication enabled;
- a Cloud Run runtime service account;
- a Cloud Storage bucket containing the JSON data; and
- an Artifact Registry Docker repository.

## IAM configuration

Use the Cloud Run runtime service account for both Firebase Admin and Cloud Storage access. Replace every placeholder with a real value:

```text
<RUNTIME_SERVICE_ACCOUNT>@<COMPUTE_PROJECT_ID>.iam.gserviceaccount.com
```

Grant the runtime identity access to the Firebase project if required by the project policy:

```bash
gcloud projects add-iam-policy-binding <FIREBASE_PROJECT_ID> \
  --member="serviceAccount:<RUNTIME_SERVICE_ACCOUNT>@<COMPUTE_PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/firebaseauth.admin"
```

Grant the least-privilege bucket role needed by the API. Because this API reads and writes the JSON object, `roles/storage.objectAdmin` is a suitable starting point:

```bash
gcloud storage buckets add-iam-policy-binding gs://<GCS_BUCKET_NAME> \
  --member="serviceAccount:<RUNTIME_SERVICE_ACCOUNT>@<COMPUTE_PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

`roles/iam.serviceAccountTokenCreator` is usually granted to a human, CI/CD identity, or deployment identity that impersonates the runtime service account. It is not normally needed by the runtime service account to validate Firebase tokens or read the bucket:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  <RUNTIME_SERVICE_ACCOUNT>@<COMPUTE_PROJECT_ID>.iam.gserviceaccount.com \
  --member="user:<DEPLOYER_EMAIL>" \
  --role="roles/iam.serviceAccountTokenCreator"
```

Avoid adding `roles/firebase.sdkAdminServiceAgent` to a user-managed runtime service account unless a specific Firebase workflow requires it. That role is generally intended for the Firebase-managed service agent.

Verify project-level access:

```bash
gcloud projects get-iam-policy <FIREBASE_PROJECT_ID> \
  --flatten="bindings[].members" \
  --filter="bindings.members:<RUNTIME_SERVICE_ACCOUNT>@<COMPUTE_PROJECT_ID>.iam.gserviceaccount.com" \
  --format="table(bindings.role)"
```

Verify bucket-level access:

```bash
gcloud storage buckets get-iam-policy gs://<GCS_BUCKET_NAME> \
  --format="yaml(bindings)"
```

## Build and deploy

Run these commands from the repository root. Set the image location and service values first:

```bash
COMPUTE_PROJECT_ID="<COMPUTE_PROJECT_ID>"
REGION="<CLOUD_RUN_REGION>"
REPOSITORY="<ARTIFACT_REGISTRY_REPOSITORY>"
IMAGE="$REGION-docker.pkg.dev/$COMPUTE_PROJECT_ID/$REPOSITORY/backend-api"
SERVICE="<CLOUD_RUN_SERVICE_NAME>"
RUNTIME_SERVICE_ACCOUNT="<RUNTIME_SERVICE_ACCOUNT>@$COMPUTE_PROJECT_ID.iam.gserviceaccount.com"
FIREBASE_PROJECT_ID="<FIREBASE_PROJECT_ID>"
GCS_BUCKET_NAME="<GCS_BUCKET_NAME>"
TAG="$(git rev-parse --short HEAD)"
```

Create the Artifact Registry repository once if it does not already exist:

```bash
gcloud artifacts repositories create "$REPOSITORY" \
  --repository-format=docker \
  --location="$REGION" \
  --project=$COMPUTE_PROJECT_ID
```

Build and push the image. A unique tag makes it clear which source revision is deployed:

```bash
gcloud builds submit . \
  --project="$COMPUTE_PROJECT_ID" \
  --tag="$IMAGE:$TAG"
```

Deploy the image to Cloud Run:

```bash
gcloud run deploy "$SERVICE" \
  --project="$COMPUTE_PROJECT_ID" \
  --region="$REGION" \
  --image="$IMAGE:$TAG" \
  --service-account="$RUNTIME_SERVICE_ACCOUNT" \
  --set-env-vars="FIREBASE_PROJECT_ID=$FIREBASE_PROJECT_ID,GCS_BUCKET_NAME=$GCS_BUCKET_NAME" \
  --allow-unauthenticated
```

`--allow-unauthenticated` controls access to the Cloud Run HTTP endpoint. It does not disable application-level Firebase authentication; the Flask decorators still require a valid Firebase ID token.

When only environment variables or Cloud Run settings change, rebuilding is unnecessary:

```bash
gcloud run services update "$SERVICE" \
  --project="$COMPUTE_PROJECT_ID" \
  --region="$REGION" \
  --update-env-vars="FIREBASE_PROJECT_ID=$FIREBASE_PROJECT_ID,GCS_BUCKET_NAME=$GCS_BUCKET_NAME"
```

When Python code, dependencies, or the Dockerfile changes, build and deploy a new image.

## Container port

Cloud Run sends traffic to the port configured for the container. The production Dockerfile uses Gunicorn on port `8080`:

```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "app:app"]
```

Therefore Cloud Run should be configured with `--port=8080`. The `app.run(..., port=5000)` block is for direct local execution and is not used when Gunicorn starts the container.

## Frontend configuration

The frontend must use the same Firebase project as the backend's `FIREBASE_PROJECT_ID`:

```javascript
const firebaseConfig = {
  projectId: "<FIREBASE_PROJECT_ID>"
};

const BACKEND_URL = "<CLOUD_RUN_SERVICE_URL>";
```

After sign-in, the frontend should get the current ID token and send it with every protected request:

```javascript
const token = await auth.currentUser.getIdToken();

fetch(`${BACKEND_URL}/api/users`, {
  headers: {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json"
  }
});
```

Do not hard-code service-account credentials in frontend configuration. Firebase web configuration values such as the API key and project ID are not replacements for backend credentials.

## API behavior

All API routes require a Firebase ID token, including health:

```text
GET    /api/health
GET    /api/users
GET    /api/users/<id>
POST   /api/users
PUT    /api/users/<id>
DELETE /api/users/<id>
```

Example request:

```bash
curl -i "https://<CLOUD_RUN_SERVICE_URL>/api/health" \
  -H "Authorization: Bearer <FIREBASE_ID_TOKEN>"
```

Expected authentication failures:

- `401 Missing Bearer token`: the `Authorization` header is absent or malformed.
- `401 Invalid or expired Firebase token`: Firebase rejected the token.

## Local development

For local file-backed testing, follow [gcs-flask-api/README.local.md](gcs-flask-api/README.local.md). That mode uses a service-account JSON file and `USERS_FILE`; it does not use the GCS bucket.

For local testing of the cloud version, use Application Default Credentials or set a local service-account path:

```bash
export FIREBASE_PROJECT_ID="<FIREBASE_PROJECT_ID>"
export GCS_BUCKET_NAME="<GCS_BUCKET_NAME>"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
py -3 gcs-flask-api/app.py
```

Never commit the JSON key. Add local credential paths and environment files to `.gitignore`.

## Troubleshooting

### 401 invalid or expired Firebase token

1. Confirm the frontend and backend use the same Firebase project ID.
2. Sign out and sign in again so the frontend obtains a fresh token.
3. Confirm the request contains `Authorization: Bearer <token>`.
4. Confirm the deployed revision has `FIREBASE_PROJECT_ID` set.
5. Inspect Cloud Run logs for the underlying Admin SDK error:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="<CLOUD_RUN_SERVICE_NAME>"' \
  --project=<COMPUTE_PROJECT_ID> \
  --limit=50 \
  --format="value(textPayload)"
```

Do not log or share the complete token.

### GCS permission errors

Confirm that:

- `GCS_BUCKET_NAME` contains the bucket name without `gs://`;
- the Cloud Run service is using the expected runtime service account; and
- the bucket IAM policy grants that service account the required object permissions.

### Container fails to start

Confirm that:

- Gunicorn imports the correct module, `app:app`;
- the process listens on `0.0.0.0`, not `127.0.0.1`;
- the container listens on Cloud Run's configured port; and
- all packages in `requirements.txt` are installed during the image build.

### Check the deployed configuration

```bash
gcloud run services describe <CLOUD_RUN_SERVICE_NAME> \
  --project=<COMPUTE_PROJECT_ID> \
  --region=<CLOUD_RUN_REGION> \
  --format="yaml(spec.template.spec.serviceAccountName,spec.template.spec.containers[0].env,spec.template.spec.containers[0].ports)"
```

Do not include secret values in logs or documentation.
