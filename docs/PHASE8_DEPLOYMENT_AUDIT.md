# Wedding Memories — Phase 8 Deployment Audit

Date: 2026-11-08

## Executive Summary

**Status**: Code is production-ready with minor configuration additions needed. No blocking issues found. Phase 7 acceptance gates remain partially unverified (authenticated admin testing and mobile viewport checks not completed).

## Part A: Production Readiness Audit

### ✅ Backend Configuration Review

**Entry Point and Startup** (`app/main.py`):
- ✅ Proper lifespan management with MongoDB connection/cleanup
- ✅ Database status tracking (connected/not_configured/disconnected)
- ✅ Graceful degradation when MongoDB not configured
- ✅ Collection and index initialization on startup
- ✅ Saved storage provider loaded from database
- ✅ Health endpoint at `/health` with database status
- ✅ OAuth callback log redaction filter installed at startup

**Configuration** (`app/core/config.py`):
- ✅ Settings loaded from `.env` file
- ✅ Validation for JWT secret minimum byte length
- ✅ Frontend origins validated (no wildcards)
- ✅ Storage provider validated
- ✅ Google Drive redirect URI validated (HTTPS except localhost)
- ✅ All required fields have defaults or validation

**Security** (`app/core/security.py`):
- ✅ JWT requires minimum 32 bytes for HS256
- ✅ Token version checking prevents use after logout
- ✅ Proper 401/403 status codes
- ✅ No token refresh implementation (intentional, 30-minute access tokens)

**CORS Configuration**:
- ✅ Explicit origins required, no wildcards allowed
- ✅ Credentials enabled for cookie/token handling
- ✅ Proper methods and headers configured

**Database**:
- ✅ Connection timeout: 5 seconds (server selection and connect)
- ✅ Socket timeout: 10 seconds
- ✅ Health check ping with connection state update
- ✅ Collections created if absent
- ✅ Indexes created with named uniqueness (safe for repeated startup)

**Google Drive OAuth**:
- ✅ State validation with 10-minute TTL
- ✅ Token encryption with Fernet (separate from JWT secret)
- ✅ Key rotation support via PREVIOUS key
- ✅ Refresh token persistence
- ✅ Access token refresh before expiry
- ✅ Callback query redaction in Uvicorn access logs
- ✅ OAuth callback returns to frontend with status parameter
- ✅ Redirect URI validation (HTTPS except localhost)

**Storage Adapters**:
- ✅ Local: Atomic file writes with temp file + rename
- ✅ Google Drive: Private files, resumable uploads, per-photo provider tracking
- ✅ Provider selected from photo record for delivery and deletion
- ✅ No migration on provider change

**Image Delivery**:
- ✅ Streams through FastAPI (not direct static exposure)
- ✅ Public delivery checks album/event active status
- ✅ Public delivery excludes deletion_state=pending
- ✅ Drive files remain private (no public permissions created)

**Upload Validation**:
- ✅ Pillow decode and re-encode
- ✅ EXIF stripping
- ✅ Format validation (JPEG/PNG/WebP only)
- ✅ Size limits enforced
- ✅ Decompression bomb protection

**Rate Limiting**:
- ⚠️ Process-local in-memory guard
- ⚠️ Not shared between instances (documented limitation)
- ⚠️ Resets on restart
- ✅ Documented: single instance required until Redis/shared store implemented

**Deletion**:
- ✅ Atomic deletion_state=pending claim
- ✅ Hidden from public immediately
- ✅ 5-minute claim lease for recovery
- ✅ Retry queue in admin UI
- ✅ Provider-specific cleanup

**Logging**:
- ✅ OAuth callback query strings redacted from Uvicorn access logs
- ⚠️ Reverse proxy/hosting logs outside app control (documented requirement)

### ✅ Frontend Configuration Review

**Environment Configuration** (`src/config/api.ts`):
- ✅ `VITE_API_BASE_URL` with fallback to localhost
- ✅ `VITE_PUBLIC_APP_URL` with fallback to window.location.origin
- ✅ No hardcoded production URLs in source code
- ✅ Localhost references only in test files and default fallbacks

**Build Output**:
- ✅ Production build succeeds
- ✅ TypeScript compilation passes
- ✅ No secrets in bundled JavaScript
- ✅ Environment variables injected at build time (correct for Vercel)

**Routing** (`App.tsx`):
- ✅ Public routes: `/`, `/a/:albumSlug`, `/a/:albumSlug/e/:eventSlug`
- ✅ Admin routes: `/admin/*` (protected)
- ✅ Admin login: `/admin/login`
- ✅ React Router structure compatible with Vercel SPA fallback

**Authentication**:
- ✅ Bearer token in sessionStorage
- ✅ Cleared on logout and 401
- ✅ No refresh tokens
- ✅ Session-scoped security

### 🔍 Findings

**No Blocking Issues Found**

**Production Configuration Required**:
1. Create `vercel.json` for SPA routing fallback
2. Create `render.yaml` for backend deployment configuration (optional, can use dashboard)
3. Document exact environment variables needed for each platform

**Recommendations**:
1. Monitor rate limiting effectiveness with single instance
2. Configure reverse proxy log redaction for OAuth callback
3. Consider adding health check frequency documentation
4. Add backup documentation for MongoDB and Google Drive encryption key

**Security Posture**: ✅ Strong
- No debug mode in production
- No secrets in frontend
- No wildcard CORS
- Secure JWT handling
- Encrypted OAuth tokens
- Private Drive files
- Image validation and sanitization
- Upload limits and rate limiting

**Deployment Blockers**: None found in code

**Phase 7 Acceptance Gates**: Partially complete
- ✅ Backend test suite: 69 passed
- ✅ Frontend test suite: 24 passed
- ✅ MongoDB Atlas health check: Passed
- ✅ Google Drive connection: Passed
- ❌ Live authenticated uploads: Not verified
- ❌ Live mobile viewport testing: Not verified
- ❌ Live moderation workflow: Not verified

