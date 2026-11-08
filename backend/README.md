# Wedding Memories API

FastAPI backend with MongoDB Atlas connectivity, single-administrator authentication, album/event management, and public guest uploads. Guest upload sessions are short-lived and separate from administrator JWTs.

## Configure environment

From `backend`, make a local ignored environment file:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

This preserves an existing `.env` file.

Create a JWT secret with Python:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the generated value in `JWT_SECRET` in `backend/.env`. Authentication refuses to operate unless the secret has at least 32 bytes. Keep it private and never commit it. Configure `MONGODB_URI` with your MongoDB Atlas driver URI and `MONGODB_DATABASE=wedding_memories`. In Atlas, create a database user and allow the development machine's public IP in Network Access. The database URI is read from the environment; credentials are not stored in source or logged.

`FRONTEND_ORIGINS` is a comma-separated list of explicit browser origins. Its local default is `http://localhost:5173`; do not use a wildcard origin.

`PHOTO_STORAGE_PROVIDER` selects the initial provider (`local` or `google_drive`); an administrator's saved selection in MongoDB takes precedence after one is made. `PHOTO_STORAGE_LOCAL_PATH` configures local files. New uploads use the selected provider, while each photo continues to use its saved provider for delivery and deletion. Existing local photographs are not migrated. Local files are stored outside the frontend and are never publicly served. `VITE_PUBLIC_APP_URL` configures QR links, and file/rate limits are configurable with the `UPLOAD_*` variables shown in `.env.example`.

## Install and run (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8011
```

If PowerShell blocks activation, use `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8011`.

## Create the one administrator

After configuring `MONGODB_URI`, run from `backend`:

```powershell
python -m app.utils.create_admin
```

The command pings MongoDB, ensures the collections and indexes exist, refuses if any administrator already exists, prompts for email and a password using hidden input, requires at least 12 password characters, hashes the password with Argon2, and inserts the single `owner` account slot. Do not pass passwords as command-line arguments. The unique database index on `account_slot`, unique email index, and service-side existence check protect against repeat and concurrent creation attempts. There is no HTTP registration route.

To reset the owner's password securely, run:

```powershell
python -m app.utils.reset_admin_password
```

This command also prompts without echoing the password, enforces the 12-character minimum, stores only an Argon2 hash, increments `token_version`, and thereby revokes existing access tokens.

## Authentication API

- `POST /api/v1/auth/login` accepts JSON `{ "email": "owner@example.com", "password": "…" }` and returns a 30-minute signed access token and public administrator email.
- `GET /api/v1/auth/me` returns the authenticated administrator's public information.
- `POST /api/v1/auth/logout` increments `token_version`, invalidating the current token and all older tokens.

Tokens require `sub`, `exp`, `iat`, `jti`, and `token_version`; inactive accounts, expired tokens, and outdated token versions are rejected. No refresh tokens are implemented. `GET /health` reports MongoDB readiness. Interactive API documentation is at <http://localhost:8011/docs>.

## Frontend and browser token storage

In a separate PowerShell window:

```powershell
cd frontend
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm install
npm run dev
```

Set `VITE_API_BASE_URL` to the backend API base URL (local default: `http://localhost:8011/api/v1`) and `VITE_PUBLIC_APP_URL` to the public frontend origin (local default: `http://localhost:5173`). Open <http://localhost:5173/admin/login> and sign in with the owner account created by the CLI.

The browser keeps the bearer token in `sessionStorage`, attaches it to API requests, and clears it on logout or HTTP 401. `sessionStorage` is scoped to the browser tab session and is accessible to JavaScript running in the page, so an XSS vulnerability could expose it. Keep dependencies current and serve the deployed site only over HTTPS. Logout revokes server-side tokens; there are no refresh tokens.

## Album and event management API

All management endpoints require the existing administrator bearer token.

Albums:

- `POST /api/v1/albums`, `GET /api/v1/albums` (supports `page`, `page_size`, `status`, and `search`)
- `GET /api/v1/albums/{album_id}`, `PATCH /api/v1/albums/{album_id}`
- `PATCH /api/v1/albums/{album_id}/archive`, `PATCH /api/v1/albums/{album_id}/restore`
- `DELETE /api/v1/albums/{album_id}`

Events are scoped under their parent album:

- `POST /api/v1/albums/{album_id}/events`, `GET /api/v1/albums/{album_id}/events`
- `GET /api/v1/albums/{album_id}/events/{event_id}`, `PATCH /api/v1/albums/{album_id}/events/{event_id}`
- `PATCH /api/v1/albums/{album_id}/events/{event_id}/archive`, `PATCH /api/v1/albums/{album_id}/events/{event_id}/restore`
- `DELETE /api/v1/albums/{album_id}/events/{event_id}`

Album slugs are globally unique. Event slugs are unique per album, enforced by the compound MongoDB index. Event operations filter by both the parent and event ObjectIds. Deletes return `409` if dependent events, photos, or contributors exist; no dependent records are cascaded. Use archive/restore for normal lifecycle management. Cover-image fields store URL/reference metadata only; no image upload is provided.

## Guest album, QR and upload APIs

Public reads are available at `GET /api/v1/public/albums/{album_slug}`, `GET /api/v1/public/albums/{album_slug}/events`, and `GET /api/v1/public/albums/{album_slug}/events/{event_slug}`. These return only active resources, validate event/album relationships, and omit database IDs and admin fields.

Create an upload session with `POST /api/v1/public/albums/{album_slug}/events/{event_slug}/upload-session`, then submit multipart `upload_token` and one or more `files` to `/api/v1/public/albums/{album_slug}/events/{event_slug}/photos`. Sessions use a separate audience and token purpose from admin access tokens. Pillow decodes JPEG/PNG/WebP files, enforces size/count limits, and re-encodes images to strip EXIF metadata. Photo metadata is stored as `pending` in the existing `photos` collection; a failed MongoDB insert triggers cleanup through the selected storage provider. Approved photos are streamed through the public API; pending and rejected images remain hidden. Admin moderation is available under `/admin/photos`.

QR buttons use `VITE_PUBLIC_APP_URL`; set it to the deployed frontend origin. Local default is `http://localhost:5173`. Guest pages use `/a/{album_slug}` and `/a/{album_slug}/e/{event_slug}`. Camera capture uses `getUserMedia` after the guest presses the camera button; camera access requires HTTPS in production. A mobile camera-picker fallback and independent gallery picker are provided.

## Google Drive setup

Google Drive is optional. Keep `PHOTO_STORAGE_PROVIDER=local` until OAuth is configured, the administrator has connected the Google account, and Storage settings reports Google Drive as operational. Provider changes affect new uploads only. Existing records retain their `storage_provider` and storage identifier. Disconnecting Drive selects local for future uploads and removes the stored OAuth credentials; existing Drive photos require reconnecting that account to be delivered.

### Google Cloud Console

1. Create or select a Google Cloud project and enable **Google Drive API**.
2. Configure the OAuth consent screen for the personal account. For local evaluation, choose External and add the administrator as a test user.
3. Create an OAuth client with application type **Web application**.
4. Add this exact local authorized redirect URI:

   `http://localhost:8011/api/v1/integrations/google-drive/callback`

   For deployment, use the public HTTPS backend URL with `/api/v1/integrations/google-drive/callback` and register that exact URI too.

5. Set `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET`, `GOOGLE_DRIVE_REDIRECT_URI`, and `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY` in the backend runtime environment. Optionally set `GOOGLE_DRIVE_FOLDER_ID` to an accessible, writable Drive folder. Without one, the app creates and persists a private **Wedding Memories** folder in the connected account.
6. Generate a dedicated token encryption key:

   ```powershell
   cd backend
   .venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

7. Restart the backend, sign in at `/admin/login`, open **Storage settings**, choose **Connect Google Drive**, and complete Google's consent screen. Confirm status reads **Connected and ready**, then select **Google Drive** for new uploads.

The app requests the `drive.file` scope and offline access, stores access/refresh tokens encrypted with Fernet in the existing `photo_settings` collection, and refreshes access tokens on the server. Drive v3 resumable uploads use generated upload UUID filenames and album/event `appProperties`; no public permission is created. The encryption key is independent of `JWT_SECRET`; preserve it across deploys and backups. For key rotation, set a new `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY` and temporarily set the prior value as `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY_PREVIOUS`. Restart the backend and load Storage settings to validate and re-encrypt credentials, then remove the previous key and restart. If the only key is lost, the encrypted tokens cannot be recovered; reconnect the account with a new key.

OAuth apps in **Testing** mode can issue refresh tokens that expire after seven days when using Drive scopes. For persistent production use, configure the consent screen for the production audience and complete Google's publishing and verification requirements for the scopes and audience. Keep `drive.file` as the Drive access scope; do not add public permissions. Google API quota/rate limits and transient outages cause Drive operations to fail; the application does not silently fall back to local storage. Render (or another host) must keep OAuth client secrets and the encryption key in its server-side environment. MongoDB is the durable token store; preserve the same encryption key across restarts and instances. If using local storage in deployment, mount persistent storage at `PHOTO_STORAGE_LOCAL_PATH`.

For a Render Web Service, set the service root to `backend`, use `pip install -r requirements.txt` as the build command, and `uvicorn app.main:app --host 0.0.0.0 --port $PORT` as the start command. Add the `GOOGLE_DRIVE_*` values, `PHOTO_STORAGE_PROVIDER=local`, `MONGODB_URI`, `MONGODB_DATABASE`, `JWT_SECRET`, and production `FRONTEND_ORIGINS` in that service's Environment settings. Set `GOOGLE_DRIVE_REDIRECT_URI` to `https://<your-backend-host>/api/v1/integrations/google-drive/callback` and register that exact URL in Google Cloud Console. Keep `PHOTO_STORAGE_PROVIDER=local` until account connection is verified; then select Drive from the admin page. Do not use a client-side `VITE_*` variable for OAuth secrets or encryption keys.

Official references: [Google web-server OAuth and offline access](https://developers.google.com/identity/protocols/oauth2/web-server), [Google Drive v3 resumable uploads](https://developers.google.com/workspace/drive/api/guides/manage-uploads), [Fernet authenticated encryption and key rotation](https://cryptography.io/en/stable/fernet/).

The OAuth callback is bound to a one-time, ten-minute server-side state transaction associated with the administrator and their token version. Drive files remain private; public and admin image endpoints stream content through FastAPI according to each photo's stored provider. Existing photographs are not migrated.

## Reliability and deployment readiness

### Storage and deletion lifecycle

The photo record's `storage_provider` and `storage_file_id` select the adapter for preview, public delivery, download, and deletion. Changing the default provider affects new uploads only. Local files remain under `PHOTO_STORAGE_LOCAL_PATH`, outside the frontend; the local adapter writes into a temporary file, flushes it, and atomically renames it into place. Existing local filenames and files remain compatible.

Permanent deletion uses `deletion_state=pending`, independent of moderation `status`. Records without this field are treated as active. The backend claims deletion in MongoDB, hides the record from public gallery results, image delivery, and counts, removes the provider-backed object, then removes the MongoDB record. Storage or metadata failures leave the hidden photo in the admin **Deletion retry** queue. Retrying DELETE is safe; a five-minute claim lease allows recovery if a process exits during deletion. Local missing-file errors and a Google Drive API 404 confirm that the object is already absent. This lifecycle needs no photo migration or new index.

### Upload limits and Redis

Upload request, IP, and per-session limits currently use a process-local in-memory guard. No Redis dependency or Redis configuration exists in this project. This preserves local development and requires no additional service, but counters reset at restart and are not shared between Render instances. Before scaling to multiple backend instances, configure a shared Redis-compatible store and migrate the guard atomically; until then, production should run one backend instance if relying on these limits as abuse controls. Continue enforcing host-level request limits as defense in depth.

### OAuth logs and recovery

The backend redacts callback query strings from Uvicorn access-log records for `/api/v1/integrations/google-drive/callback`; application callback logs contain only result categories and exception types. Reverse-proxy or hosting access logs are outside the app's control. Configure any proxy that records URLs to omit or redact the callback query string. Do not paste callback URLs into support tickets. Preserve the Drive encryption key across restarts and backups. If the access token expires, the backend refreshes it with the encrypted refresh token. If refresh fails because the grant is invalid or expired, reconnect the same Google account from **Storage settings**; do not disconnect merely to test refresh. Drive-backed photographs become inaccessible while disconnected, so reconnect before restoring delivery.

### Phase 8 production configuration requirements

- **Render backend:** service root `backend`; install `pip install -r requirements.txt`; start with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set server-side `MONGODB_URI`, `MONGODB_DATABASE`, `JWT_SECRET` (32+ random bytes), `FRONTEND_ORIGINS` (exact HTTPS Vercel origin), `APP_ENV=production`, and `DEBUG=false`. Keep all OAuth client values and Fernet keys server-side. Never add secrets as `VITE_*` variables.
- **Vercel frontend:** set `VITE_API_BASE_URL` to the public HTTPS backend API base ending in `/api/v1`, and `VITE_PUBLIC_APP_URL` to the exact HTTPS frontend origin used for QR links. Redeploy after changing build-time variables.
- **CORS and HTTPS:** set explicit frontend origins only; wildcard origins are rejected. Terminate TLS at the hosting provider and use HTTPS for all public routes. Camera capture requires HTTPS. Keep the exact Google OAuth callback registered as `https://<backend-host>/api/v1/integrations/google-drive/callback` and set the identical server-side `GOOGLE_DRIVE_REDIRECT_URI`.
- **Google Drive:** enable Drive API; configure the OAuth audience and authorized users; satisfy Google's publishing and verification requirements for the intended audience/scopes; preserve `drive.file`; keep application files private; retain and back up the encryption key separately from JWT secrets. Verify connected/ready state before selecting Drive for new uploads.
- **Persistence:** Google Drive is the durable option on an ephemeral backend filesystem. If selecting local storage in production, attach a persistent Render disk and mount it at `PHOTO_STORAGE_LOCAL_PATH`; never point the frontend at this directory or expose it as a static route. Back up local photos and MongoDB metadata together.
- **Rate limits:** current upload counters are process-local. Use a single backend instance until a shared Redis-compatible guard is implemented and configured, or accept that current limits are not coordinated across instances. Redis is not currently required or consumed by the application.
- **Operations:** monitor `/health`, database connection errors, storage adapter failures, and the admin deletion-retry queue. Restrict access to logs, redact OAuth callback query parameters in host/proxy logs, rotate secrets through the hosting secret store, and validate backup/restore and Drive reconnection procedures before launch. Do not run production cleanup or migration scripts as part of deployment.

Current limitations: there is no automatic background worker for deletion retries; administrators retry failed deletions from Photo Moderation. Process-local rate limits are unsuitable as a shared multi-instance control. Hosting-level access logs may retain request URLs unless configured to redact callback queries. Live Atlas, Drive, OAuth refresh, and mobile device behavior must be verified in the target development account/device; mocked tests do not establish those external integrations.

## Tests

Run backend tests from `backend` with its virtual environment active:

```powershell
python -m pytest
```

Run frontend route and session tests from `frontend`:

```powershell
npm test
npm run build
```

Backend tests mock MongoDB and do not need a live Atlas connection. For a live database check, start the API with a valid local `.env` and check `/health`.
