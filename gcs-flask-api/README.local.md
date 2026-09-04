# Local Firebase-authenticated API

This local API reads and writes a file-backed copy of `backend-data/users.json`.
The existing `app.py` and `Dockerfile` remain available for the GCS deployment.

## Configure a service account

In PowerShell, point the API at the Firebase service-account JSON file:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\firebase-service-account.json"
$env:USERS_FILE = "C:\path\to\users.json"
py -3 gcs-flask-api/app_local.py
```

`FIREBASE_SERVICE_ACCOUNT_PATH` can be used instead. Relative paths are resolved
from the repository root. Never commit the service-account JSON file.

## Run with Docker

Build from the repository root so the Dockerfile can copy `backend-data/users.json`:

```powershell
docker build -f gcs-flask-api/Dockerfile.local -t gcs-flask-api-local .
docker run --rm -p 5000:8080 `
  -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/firebase-service-account.json `
  -v "C:\path\to\firebase-service-account.json:/run/secrets/firebase-service-account.json:ro" `
  gcs-flask-api-local
```

The container uses `/app/backend-data/users.json`, leaving the repository file
unchanged.

## Call the API

Every endpoint requires a Firebase ID token, including health:

```powershell
$headers = @{ Authorization = "Bearer $firebaseIdToken" }
curl.exe -i http://localhost:5000/api/health -H "Authorization: Bearer $firebaseIdToken"
curl.exe -i http://localhost:5000/api/users -H "Authorization: Bearer $firebaseIdToken"
```

The frontend already obtains and sends this token for `/api/users`. New users
store the authenticated Firebase `uid`. Existing records do not have a UID
because there is no trustworthy mapping for them; they still work under the
configured policy that any authenticated user can manage all records.