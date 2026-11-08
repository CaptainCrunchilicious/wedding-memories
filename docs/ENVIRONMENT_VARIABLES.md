# Wedding Memories — Environment Variables Reference

Complete reference for all environment variables used in production deployment.

## Backend (Render) Environment Variables

### Required Variables

| Variable | Required | Secret | Format | Description |
|----------|----------|--------|--------|-------------|
| `MONGODB_URI` | ✅ Yes | 🔒 Yes | Connection string | MongoDB Atlas connection URI with credentials |
| `MONGODB_DATABASE` | ✅ Yes | No | String | Database name (must be: `wedding_memories`) |
| `JWT_SECRET` | ✅ Yes | 🔒 Yes | 48+ byte string | Secret for signing JWT access tokens (min 32 bytes for HS256) |
| `FRONTEND_ORIGINS` | ✅ Yes | No | Comma-separated URLs | Exact HTTPS frontend URL(s) for CORS (no wildcards, no trailing slash) |
| `PHOTO_STORAGE_PROVIDER` | ✅ Yes | No | `local` or `google_drive` | Initial storage provider selection |

### Application Configuration

| Variable | Required | Default | Format | Description |
|----------|----------|---------|--------|-------------|
| `APP_NAME` | No | `Wedding Memories` | String | Application name (display only) |
| `APP_ENV` | No | `development` | String | Environment name (use `production` for prod) |
| `DEBUG` | No | `true` | Boolean | Debug mode (must be `false` in production) |
| `API_V1_PREFIX` | No | `/api/v1` | Path | API route prefix |

### JWT Configuration

| Variable | Required | Default | Format | Description |
|----------|----------|---------|--------|-------------|
| `JWT_ALGORITHM` | No | `HS256` | String | JWT signing algorithm (HS256/HS384/HS512) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Integer (1-1440) | Access token lifetime in minutes |

### Local Storage Configuration

| Variable | Required | Default | Format | Description |
|----------|----------|---------|--------|-------------|
| `PHOTO_STORAGE_LOCAL_PATH` | No | `storage-data` | Path | Directory for local photo storage |

**Render Notes**:
- Default relative path works for ephemeral storage
- For persistent storage, use: `/opt/render/project/src/storage-data`
- Requires persistent disk configuration in Render dashboard

### Google Drive Configuration (All or None)

| Variable | Required | Secret | Format | Description |
|----------|----------|--------|--------|-------------|
| `GOOGLE_DRIVE_CLIENT_ID` | Conditional | No | String | OAuth 2.0 client ID from Google Cloud Console |
| `GOOGLE_DRIVE_CLIENT_SECRET` | Conditional | 🔒 Yes | String | OAuth 2.0 client secret |
| `GOOGLE_DRIVE_REDIRECT_URI` | Conditional | No | URL | Exact OAuth callback URL (must match Google Console) |
| `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY` | Conditional | 🔒 Yes | Fernet key | Fernet encryption key for token storage |
| `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY_PREVIOUS` | No | 🔒 Yes | Fernet key | Previous encryption key (during rotation only) |
| `GOOGLE_DRIVE_FOLDER_ID` | No | Auto-created | String | Existing Drive folder ID (optional) |

**Generation Commands**:
```bash
# JWT Secret
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Fernet Encryption Key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Critical**:
- `GOOGLE_DRIVE_REDIRECT_URI` must exactly match Google Cloud Console configuration
- Must be HTTPS in production (except localhost for development)
- Format: `https://your-backend.onrender.com/api/v1/integrations/google-drive/callback`
- Backup `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY` independently (cannot decrypt tokens without it)

### Upload Limits Configuration

| Variable | Required | Default | Format | Description |
|----------|----------|---------|--------|-------------|
| `UPLOAD_SESSION_MINUTES` | No | `30` | Integer (1-180) | Upload session token lifetime |
| `UPLOAD_MAX_FILE_BYTES` | No | `12582912` (12 MB) | Integer | Maximum single file size |
| `UPLOAD_MAX_REQUEST_BYTES` | No | `57671680` (55 MB) | Integer | Maximum request body size |
| `UPLOAD_MAX_FILES_PER_REQUEST` | No | `10` | Integer (1-50) | Maximum files per upload request |
| `UPLOAD_MAX_FILES_PER_SESSION` | No | `30` | Integer | Maximum files per session |
| `UPLOAD_MAX_BYTES_PER_SESSION` | No | `104857600` (100 MB) | Integer | Maximum total bytes per session |
| `UPLOAD_SESSIONS_PER_IP_PER_HOUR` | No | `20` | Integer | Session creation rate limit |
| `UPLOAD_REQUESTS_PER_IP_PER_HOUR` | No | `30` | Integer | Upload request rate limit |

**Notes**:
- Limits are process-local (in-memory)
- Not shared between instances
- Reset on backend restart
- For multi-instance deployment, implement Redis-backed rate limiting

## Frontend (Vercel) Environment Variables

### Required Variables

| Variable | Required | Secret | Format | Description |
|----------|----------|--------|--------|-------------|
| `VITE_API_BASE_URL` | ✅ Yes | No | URL | Backend API base URL including `/api/v1` |
| `VITE_PUBLIC_APP_URL` | ✅ Yes | No | URL | Frontend public URL (for QR codes and links) |

**Format Requirements**:
- `VITE_API_BASE_URL` must end with `/api/v1`
- `VITE_PUBLIC_APP_URL` must not have trailing slash
- Both must be HTTPS in production
- Must match `FRONTEND_ORIGINS` in backend configuration

**Examples**:
```bash
VITE_API_BASE_URL=https://wedding-memories-backend.onrender.com/api/v1
VITE_PUBLIC_APP_URL=https://wedding-memories.vercel.app
```

**Important**:
- These are build-time variables
- Changing them requires redeploying the frontend
- Values are compiled into the JavaScript bundle
- Never put backend secrets in `VITE_*` variables

## Configuration Validation

### Backend Validation

All backend environment variables are validated on startup:

- `JWT_SECRET` minimum byte length enforced
- `FRONTEND_ORIGINS` must not be wildcard (`*`)
- `MONGODB_DATABASE` must not be empty
- `GOOGLE_DRIVE_REDIRECT_URI` must be HTTPS (except localhost)
- `JWT_ALGORITHM` must be HS256/HS384/HS512
- `PHOTO_STORAGE_PROVIDER` must be `local` or `google_drive`

Failed validation prevents application startup with clear error messages.

### Frontend Validation

Frontend variables have fallback defaults:
- `VITE_API_BASE_URL` defaults to `http://localhost:8011/api/v1`
- `VITE_PUBLIC_APP_URL` defaults to `window.location.origin`

**Production**: Always set both variables explicitly to avoid using localhost defaults.

## Security Guidelines

### Secret Management

**Never commit secrets to Git**:
- ✅ Use `.env` files (already in `.gitignore`)
- ✅ Store in platform secret managers (Render/Vercel environment variables)
- ❌ Never commit `.env` files
- ❌ Never put secrets in `VITE_*` variables (compiled into public JavaScript)
- ❌ Never log secrets

**Secret Rotation**:
1. Generate new secret
2. Update in platform dashboard
3. Service redeploys automatically
4. Old secret remains valid during rotation window (if supported)

### CORS Configuration

**Strict origin policy**:
- Always use exact URLs
- No wildcards (`*`)
- No trailing slashes
- Include protocol (`https://`)
- Multiple origins: comma-separated

**Example**:
```bash
# ✅ Correct
FRONTEND_ORIGINS=https://app.vercel.app,https://custom-domain.com

# ❌ Wrong
FRONTEND_ORIGINS=*
FRONTEND_ORIGINS=http://localhost:5173,*
FRONTEND_ORIGINS=https://app.vercel.app/
```

### Network Security

**Backend (Render)**:
- All secrets stored server-side
- HTTPS automatically provided
- OAuth secrets never exposed to frontend
- MongoDB credentials remain server-side

**Frontend (Vercel)**:
- HTTPS automatically provided
- Only `VITE_*` variables compiled into bundle
- No backend secrets accessible
- API calls go through backend CORS policy

## Platform-Specific Notes

### Render

**Free Tier**:
- Service sleeps after 15 minutes of inactivity
- First request after sleep takes ~30 seconds
- Environment variables persist
- Filesystem is ephemeral (lost on restart)

**Paid Tier**:
- Always-on service
- Persistent disk available
- Static outbound IPs available (for stricter MongoDB access)

**Environment Variable Management**:
- Set in service dashboard under **Environment**
- Changing variables triggers automatic redeploy
- Support for secret masking

### Vercel

**Build-time Variables**:
- `VITE_*` variables compiled during build
- Changing requires redeploy
- Not secret (appear in browser bundle)

**Deployment**:
- Automatic deploys on Git push
- Preview deployments for PRs
- Production deployment requires explicit environment variables

**Custom Domains**:
- Automatic HTTPS certificates
- Update `VITE_PUBLIC_APP_URL` after adding domain
- Update `FRONTEND_ORIGINS` in backend
- Redeploy both services

## Development vs Production

### Development (.env files)

**Backend** (`backend/.env`):
```bash
MONGODB_URI=mongodb+srv://...
MONGODB_DATABASE=wedding_memories
JWT_SECRET=dev-secret-at-least-32-bytes
FRONTEND_ORIGINS=http://localhost:5173
PHOTO_STORAGE_PROVIDER=local
GOOGLE_DRIVE_REDIRECT_URI=http://localhost:8011/api/v1/integrations/google-drive/callback
# ... other variables
```

**Frontend** (`frontend/.env`):
```bash
VITE_API_BASE_URL=http://localhost:8011/api/v1
VITE_PUBLIC_APP_URL=http://localhost:5173
```

### Production (Platform Dashboards)

**Backend (Render)**:
- Use strong random secrets
- Use production MongoDB cluster
- Use HTTPS frontend URL
- Set `APP_ENV=production`
- Set `DEBUG=false`
- Use production Google Drive callback URL

**Frontend (Vercel)**:
- Use production backend URL (HTTPS)
- Use production frontend URL (HTTPS)
- Matches backend CORS configuration

## Troubleshooting

### "Authentication is not configured" (503)

**Cause**: `JWT_SECRET` missing or too short

**Fix**:
- Set `JWT_SECRET` in Render environment variables
- Minimum 32 bytes (48+ recommended)
- Generate with: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

### "MongoDB database is not connected" (503)

**Cause**: Database connection failed

**Fix**:
- Check `MONGODB_URI` format and credentials
- Verify MongoDB Atlas network access (0.0.0.0/0 for Render)
- Check database name matches `MONGODB_DATABASE`
- Review Render logs for specific error

### "CORS policy" errors in browser

**Cause**: Frontend origin not allowed by backend

**Fix**:
- Check `FRONTEND_ORIGINS` in Render matches exact Vercel URL
- No trailing slash
- Include protocol (`https://`)
- Wait for backend redeploy after changing variable

### "Google Drive is not configured" (503)

**Cause**: Incomplete Google Drive configuration

**Fix**:
- Set all Google Drive variables or none
- Required: CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, TOKEN_ENCRYPTION_KEY
- Verify encryption key is valid Fernet key
- Check redirect URI matches Google Cloud Console exactly

### "The stored Google Drive credentials cannot be decrypted"

**Cause**: Encryption key changed or missing

**Fix**:
- Restore original `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY`
- If lost, reconnect Google Drive from admin settings
- Backup encryption key independently

## Migration Checklist

Moving from development to production:

### Backend
- [ ] Generate production JWT secret (48+ bytes)
- [ ] Use production MongoDB Atlas cluster
- [ ] Set strong MongoDB user password
- [ ] Configure MongoDB network access for Render
- [ ] Set `APP_ENV=production`
- [ ] Set `DEBUG=false`
- [ ] Update `FRONTEND_ORIGINS` to production URL
- [ ] Update `GOOGLE_DRIVE_REDIRECT_URI` to production URL
- [ ] Register production callback in Google Cloud Console
- [ ] Back up `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY`

### Frontend
- [ ] Set `VITE_API_BASE_URL` to production backend
- [ ] Set `VITE_PUBLIC_APP_URL` to production frontend
- [ ] Verify build succeeds
- [ ] Check no development URLs in bundle

### Cross-Platform
- [ ] Backend `FRONTEND_ORIGINS` matches frontend URL exactly
- [ ] Frontend `VITE_API_BASE_URL` matches backend URL exactly
- [ ] Both services use HTTPS
- [ ] CORS allows credentials
- [ ] Test end-to-end authentication flow
- [ ] Verify Google Drive callback works (if configured)

