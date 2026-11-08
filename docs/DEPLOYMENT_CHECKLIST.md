# Wedding Memories — Production Deployment Checklist

Use this checklist to ensure all deployment steps are completed correctly.

## Pre-Deployment

### Code Readiness
- [x] Phase 7 backend tests passing (69/69)
- [x] Phase 7 frontend tests passing (24/24)
- [x] Production build succeeds
- [x] TypeScript compilation passes
- [x] No hardcoded localhost URLs in source (except tests/defaults)
- [x] Secrets in `.gitignore`
- [ ] Phase 7 live authenticated testing completed
- [ ] Phase 7 mobile viewport testing completed

### Documentation Review
- [x] Read `docs/PHASE7_FINAL_REPORT.md`
- [x] Read `docs/PHASE8_DEPLOYMENT_AUDIT.md`
- [x] Read `docs/DEPLOYMENT_GUIDE.md`
- [x] Read `docs/ENVIRONMENT_VARIABLES.md`
- [x] Read `backend/README.md`

### Accounts & Access
- [ ] MongoDB Atlas account created
- [ ] MongoDB cluster created and running
- [ ] Render account created
- [ ] Vercel account created
- [ ] Git repository accessible to both platforms
- [ ] Google Cloud Console project created (if using Drive)

## MongoDB Atlas Configuration

### Database Setup
- [ ] Database name: `wedding_memories`
- [ ] Database user created with read/write access
- [ ] Strong password generated and saved securely
- [ ] Connection string obtained and saved

### Network Access
- [ ] Network access configured for Render
- [ ] Recommended: 0.0.0.0/0 (Render uses dynamic IPs on free tier)
- [ ] Connection string tested from development machine

### Collections
- [ ] Collections will be created automatically on first backend startup
- [ ] No manual collection creation needed

## Google Drive Setup (Optional - Skip if Using Local Storage)

### Google Cloud Console
- [ ] Google Cloud project created
- [ ] Google Drive API enabled
- [ ] OAuth consent screen configured
- [ ] Consent screen user type: External
- [ ] Scope added: `drive.file`
- [ ] Test user added (your Google account)

### OAuth Credentials
- [ ] OAuth client ID created (Web application)
- [ ] Development redirect URI added: `http://localhost:8011/api/v1/integrations/google-drive/callback`
- [ ] Production redirect URI ready (will add after deploying backend)
- [ ] Client ID saved securely
- [ ] Client secret saved securely

### Encryption Key
- [ ] Fernet encryption key generated
- [ ] Key saved in password manager
- [ ] Backup copy stored securely offline
- [ ] Key never committed to Git

### Publishing Status
- [ ] Understand testing mode limitations (7-day token expiry)
- [ ] Decide if verification/publishing is needed for your use case
- [ ] Plan for weekly reconnection if staying in testing mode

## Backend Secrets Generation

### JWT Secret
- [ ] Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- [ ] Save securely (minimum 32 bytes, 48+ recommended)
- [ ] Different from development secret
- [ ] Never commit to Git

### Google Drive Encryption (if using Drive)
- [ ] Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] Save securely
- [ ] Backup independently
- [ ] Never commit to Git

## Backend Deployment (Render)

### Service Creation
- [ ] New Web Service created
- [ ] Git repository connected
- [ ] Branch selected (e.g., `main`)
- [ ] Root directory: `backend`
- [ ] Runtime: Python 3
- [ ] Region selected
- [ ] Plan selected (Free or paid)

### Build Configuration
- [ ] Build command: `pip install -r requirements.txt`
- [ ] Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- [ ] Health check path: `/health`

### Required Environment Variables
- [ ] `APP_ENV=production`
- [ ] `DEBUG=false`
- [ ] `MONGODB_URI=<your_connection_string>`
- [ ] `MONGODB_DATABASE=wedding_memories`
- [ ] `JWT_SECRET=<your_jwt_secret>`
- [ ] `FRONTEND_ORIGINS=<will_update_after_frontend_deploy>`
- [ ] `PHOTO_STORAGE_PROVIDER=local` (or `google_drive`)
- [ ] `PHOTO_STORAGE_LOCAL_PATH=/opt/render/project/src/storage-data`

### Optional Google Drive Variables (if using Drive)
- [ ] `GOOGLE_DRIVE_CLIENT_ID=<your_client_id>`
- [ ] `GOOGLE_DRIVE_CLIENT_SECRET=<your_client_secret>`
- [ ] `GOOGLE_DRIVE_REDIRECT_URI=https://YOUR-APP.onrender.com/api/v1/integrations/google-drive/callback`
- [ ] `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY=<your_fernet_key>`
- [ ] `GOOGLE_DRIVE_FOLDER_ID=<optional>`

### Deploy & Verify
- [ ] Service deployed successfully
- [ ] Build logs show no errors
- [ ] Service status: Running
- [ ] Backend URL noted: `https://_____.onrender.com`
- [ ] Health check passing: Visit `https://YOUR-APP.onrender.com/health`
- [ ] Response shows: `"status": "healthy"`
- [ ] Response shows: `"database": {"status": "connected"}`

### Troubleshooting (if needed)
- [ ] If database disconnected: Check MongoDB URI and Atlas network access
- [ ] If service fails: Review Render logs
- [ ] If build fails: Check Python version and dependencies

## Frontend Deployment (Vercel)

### Project Setup
- [ ] New project created
- [ ] Git repository imported
- [ ] Framework preset: Vite
- [ ] Root directory: `frontend`
- [ ] Build command: `npm run build` (default)
- [ ] Output directory: `dist` (default)

### Environment Variables
- [ ] `VITE_API_BASE_URL=https://YOUR-BACKEND.onrender.com/api/v1`
- [ ] `VITE_PUBLIC_APP_URL=https://YOUR-FRONTEND.vercel.app` (will update with actual URL)

### Deploy & Verify
- [ ] Project deployed successfully
- [ ] Build logs show no errors
- [ ] Frontend URL noted: `https://_____.vercel.app`
- [ ] Homepage loads correctly
- [ ] `/admin/login` page loads correctly

### Update Environment Variable
- [ ] Update `VITE_PUBLIC_APP_URL` with actual Vercel URL
- [ ] Redeploy frontend

### Troubleshooting (if needed)
- [ ] If build fails: Check Node version and dependencies
- [ ] If blank page: Check browser console for errors
- [ ] If routing broken: Verify `frontend/vercel.json` exists

## Cross-Platform Configuration

### Update Backend CORS
- [ ] Return to Render backend environment variables
- [ ] Update `FRONTEND_ORIGINS` with exact Vercel URL
- [ ] Format: `https://your-app.vercel.app` (no trailing slash)
- [ ] Backend redeploys automatically
- [ ] Wait for redeploy to complete

### Update Google Drive Callback (if using Drive)
- [ ] Go to Google Cloud Console
- [ ] Navigate to OAuth credentials
- [ ] Add authorized redirect URI: `https://YOUR-BACKEND.onrender.com/api/v1/integrations/google-drive/callback`
- [ ] Save changes

### Verify Integration
- [ ] Visit frontend URL
- [ ] Open browser developer tools (Network tab)
- [ ] Navigate to `/admin/login`
- [ ] Check for CORS errors (should be none)
- [ ] API requests should succeed (or 401 if not logged in)

## Administrator Account Creation

### Option A: Local Script with Production MongoDB
- [ ] Clone repository locally (if not already)
- [ ] Install backend dependencies
- [ ] Create temporary `backend/.env` with production MongoDB URI
- [ ] Run: `python -m app.utils.create_admin`
- [ ] Enter administrator email
- [ ] Enter strong password (min 12 characters)
- [ ] Verify: "Administrator account created successfully"
- [ ] Delete temporary `.env` file

### Option B: Render Shell (if available)
- [ ] Access Render service shell
- [ ] Run: `python -m app.utils.create_admin`
- [ ] Follow prompts

### Verify
- [ ] Administrator email saved securely
- [ ] Administrator password saved securely (password manager recommended)

## Initial Admin Login

### Test Authentication
- [ ] Visit `https://YOUR-FRONTEND.vercel.app/admin/login`
- [ ] Enter administrator email and password
- [ ] Click **Sign in**
- [ ] Should redirect to admin dashboard
- [ ] Verify: "Welcome" message or album list appears

### Troubleshooting (if login fails)
- [ ] Check browser console for errors
- [ ] Verify `VITE_API_BASE_URL` in Vercel
- [ ] Verify `FRONTEND_ORIGINS` in Render
- [ ] Check Render backend logs
- [ ] Try logging out and clearing browser storage

## Google Drive Connection (Optional)

### Connect Drive Account
- [ ] Log into admin dashboard
- [ ] Navigate to **Settings** (Storage Settings)
- [ ] Current provider shows: `local` or previous state
- [ ] Google Drive status shows configuration state
- [ ] Click **Connect Google Drive**
- [ ] Complete Google OAuth consent screen
- [ ] Grant permissions to Wedding Memories
- [ ] Redirected back to Settings page
- [ ] Status shows: **Connected and ready**
- [ ] Connected email shows your Google account

### Select Drive Provider
- [ ] Storage provider dropdown shows "Google Drive"
- [ ] Select **Google Drive**
- [ ] Click **Save**
- [ ] Confirmation message appears
- [ ] Page refreshes and shows Google Drive selected

### Verify Drive Status
- [ ] Status: Connected and ready
- [ ] Folder status: ready
- [ ] Connected email: your Google account
- [ ] Last successful check: recent timestamp

### Troubleshooting (if connection fails)
- [ ] Verify OAuth redirect URI matches exactly
- [ ] Check test user is added in Google Console
- [ ] Verify encryption key is set in Render
- [ ] Check Render logs for specific errors
- [ ] Try disconnecting and reconnecting

## Production Verification

### Backend Health
- [ ] Visit `https://YOUR-BACKEND.onrender.com/health`
- [ ] Status: `healthy`
- [ ] Database status: `connected`
- [ ] Database name: `wedding_memories`

### API Documentation
- [ ] Visit `https://YOUR-BACKEND.onrender.com/docs`
- [ ] Interactive docs load correctly
- [ ] All endpoints documented

### Create Test Album
- [ ] Log into admin dashboard
- [ ] Click **Create album**
- [ ] Name: "Test Wedding"
- [ ] Couple names: "Test User"
- [ ] Slug auto-generated: `test-wedding`
- [ ] Click **Create**
- [ ] Album created successfully
- [ ] Album appears in list

### Create Test Event
- [ ] Open test album
- [ ] Click **Add event**
- [ ] Name: "Test Ceremony"
- [ ] Slug auto-generated: `test-ceremony`
- [ ] Click **Create**
- [ ] Event created successfully
- [ ] Event appears in album

### Verify QR Code
- [ ] QR code displayed for event
- [ ] URL format: `https://YOUR-FRONTEND.vercel.app/a/test-wedding/e/test-ceremony`
- [ ] QR code scannable (test with phone)

### Test Guest Experience
- [ ] Visit event URL directly or scan QR
- [ ] Album information displays
- [ ] Event information displays
- [ ] Navigation shows other events (if any)
- [ ] Click **Upload Photos** button
- [ ] Upload interface appears

### Test Photo Upload
- [ ] Select a test image (JPEG/PNG/WebP)
- [ ] Image preview appears
- [ ] Click **Upload Photos**
- [ ] Progress indicator appears
- [ ] Success message appears
- [ ] Upload count increments

### Test Photo Moderation
- [ ] Return to admin dashboard
- [ ] Navigate to **Photo Moderation**
- [ ] Filter: **Pending** (default)
- [ ] Test photo appears in list
- [ ] Image preview loads
- [ ] Click ✓ (Approve)
- [ ] Photo moves to approved
- [ ] Photo count updates

### Verify Public Gallery
- [ ] Return to guest event page
- [ ] Refresh page
- [ ] Approved photo appears in gallery
- [ ] Click photo to open lightbox
- [ ] Image loads in lightbox
- [ ] Can swipe/navigate (if multiple photos)
- [ ] Can close lightbox
- [ ] Can download image

### Test Album Gallery
- [ ] Visit album URL: `https://YOUR-FRONTEND.vercel.app/a/test-wedding`
- [ ] Album information displays
- [ ] Events list displays
- [ ] Approved photos from all events appear
- [ ] Gallery works correctly

## Mobile Testing

### Prepare Test Devices
- [ ] iPhone or iOS device available
- [ ] Android device available
- [ ] Tablets available (optional)

### Test Viewports (Browser DevTools)
- [ ] 320×700 (iPhone SE) - Layout OK, no horizontal scroll
- [ ] 360×800 (Android small) - Layout OK, no horizontal scroll
- [ ] 393×852 (iPhone 14 Pro) - Layout OK, no horizontal scroll
- [ ] 412×924 (Android medium) - Layout OK, no horizontal scroll
- [ ] 430×932 (iPhone 14 Pro Max) - Layout OK, no horizontal scroll
- [ ] 768×1024 (iPad portrait) - Layout OK
- [ ] 1440×900 (Desktop) - Layout OK

### Test on Physical Device (iOS)
- [ ] Visit guest event page
- [ ] Page loads and renders correctly
- [ ] Click **Upload Photos**
- [ ] Click **Open Camera** button
- [ ] Browser requests camera permission
- [ ] Grant permission
- [ ] Camera viewfinder appears
- [ ] Take photo
- [ ] Photo preview appears
- [ ] Click **Upload Photos**
- [ ] Upload succeeds

### Test on Physical Device (Android)
- [ ] Visit guest event page
- [ ] Page loads and renders correctly
- [ ] Click **Upload Photos**
- [ ] Click **Open Camera** button
- [ ] Browser requests camera permission
- [ ] Grant permission
- [ ] Camera viewfinder appears
- [ ] Take photo
- [ ] Photo preview appears
- [ ] Click **Upload Photos**
- [ ] Upload succeeds

### Mobile Gallery Testing
- [ ] Gallery displays correctly
- [ ] Images load properly
- [ ] Can scroll gallery
- [ ] Can tap to open lightbox
- [ ] Lightbox displays full-screen
- [ ] Can swipe between images
- [ ] Can zoom/pinch image
- [ ] Can close lightbox
- [ ] Download works on mobile

### Mobile Issues to Check
- [ ] No horizontal scrolling on any viewport
- [ ] Touch targets large enough (min 44×44px)
- [ ] Text readable without zooming
- [ ] Images don't overflow containers
- [ ] Buttons and controls accessible
- [ ] Forms usable without keyboard issues

## Security Verification

### Authentication
- [ ] Admin routes require login
- [ ] Logout clears session
- [ ] Cannot access admin after logout
- [ ] Login redirects to dashboard
- [ ] Expired token returns 401
- [ ] Session survives page refresh

### Authorization
- [ ] Guest cannot access admin endpoints
- [ ] Upload requires valid upload token
- [ ] Upload token expires after session time
- [ ] Upload token bound to specific event
- [ ] Cannot upload to different event with same token

### CORS
- [ ] No CORS errors in browser console
- [ ] Credentials included in requests
- [ ] Frontend can make API calls
- [ ] Unauthorized origins rejected (test with curl)

### Image Security
- [ ] Images served through backend, not direct file access
- [ ] Pending photos not accessible to guests
- [ ] Deleted photos not accessible
- [ ] Drive files remain private
- [ ] No directory listing exposure

### Data Privacy
- [ ] No secrets in browser JavaScript bundle
- [ ] No secrets in API responses
- [ ] OAuth callback doesn't expose tokens in logs
- [ ] MongoDB credentials only on backend

## Performance Check

### Backend
- [ ] Health endpoint responds < 2 seconds
- [ ] API requests respond < 3 seconds
- [ ] Image delivery starts < 2 seconds
- [ ] Upload processes < 10 seconds
- [ ] No memory leaks visible in logs

### Frontend
- [ ] Homepage loads < 3 seconds
- [ ] Navigation responsive
- [ ] Images load progressively
- [ ] No console errors
- [ ] No console warnings (review if any)

### Render Free Tier Notes
- [ ] First request after sleep takes ~30 seconds (expected)
- [ ] Subsequent requests are fast
- [ ] Consider upgrade if user experience requires always-on

## Cleanup & Finalization

### Remove Test Data
- [ ] Delete test photos from moderation
- [ ] Archive or delete test event
- [ ] Archive or delete test album
- [ ] Verify deletion works correctly

### Documentation
- [ ] Save backend URL in team docs
- [ ] Save frontend URL in team docs
- [ ] Save administrator credentials securely
- [ ] Document any customizations made
- [ ] Save Google Drive encryption key backup

### Monitoring Setup
- [ ] Render: Enable email notifications for deploy failures
- [ ] MongoDB Atlas: Set up connection alerts (optional)
- [ ] Vercel: Enable deployment notifications (optional)
- [ ] Bookmark health endpoint for manual checks

## Custom Domain Setup (Optional)

### Frontend Domain (Vercel)
- [ ] Domain purchased/available
- [ ] Add domain in Vercel project settings
- [ ] Configure DNS records as instructed
- [ ] Wait for DNS propagation (up to 48 hours)
- [ ] Verify HTTPS certificate issued
- [ ] Update `VITE_PUBLIC_APP_URL` to custom domain
- [ ] Redeploy frontend
- [ ] Update `FRONTEND_ORIGINS` in backend
- [ ] Test with custom domain

### Backend Domain (Render)
- [ ] Domain purchased/available
- [ ] Add custom domain in Render service settings
- [ ] Configure CNAME DNS record
- [ ] Wait for DNS propagation
- [ ] Verify HTTPS certificate issued
- [ ] Update `VITE_API_BASE_URL` in Vercel
- [ ] Update `GOOGLE_DRIVE_REDIRECT_URI` in Render (if using Drive)
- [ ] Update OAuth redirect URI in Google Console (if using Drive)
- [ ] Redeploy frontend
- [ ] Test end-to-end

## Post-Deployment Tasks

### Immediate (First 24 Hours)
- [ ] Monitor Render logs for errors
- [ ] Check MongoDB Atlas connections
- [ ] Verify Google Drive operations (if used)
- [ ] Test from multiple devices
- [ ] Get feedback from a test user

### First Week
- [ ] Monitor upload patterns
- [ ] Check rate limiting effectiveness
- [ ] Review photo moderation workflow
- [ ] Verify backup strategy
- [ ] Test Google Drive reconnection (if testing mode)

### Ongoing
- [ ] Weekly: Review logs for anomalies
- [ ] Monthly: Check MongoDB storage usage
- [ ] Monthly: Review uploaded photos
- [ ] Quarterly: Update dependencies
- [ ] Quarterly: Rotate JWT secret (requires user re-login)

## Rollback Plan

If critical issues occur:

### Backend Rollback
- [ ] Render: Revert to previous deployment from dashboard
- [ ] Check health endpoint
- [ ] Verify database connectivity

### Frontend Rollback
- [ ] Vercel: Revert to previous deployment from dashboard
- [ ] Clear browser cache
- [ ] Test admin login

### Data Integrity
- [ ] MongoDB data persists across backend deployments
- [ ] Photos persist if using Google Drive
- [ ] Local photos lost if backend redeployed (ephemeral filesystem)

## Success Criteria

Production deployment is successful when:

- [x] Backend health check returns "healthy"
- [x] Frontend loads without errors
- [x] Administrator can log in
- [ ] Albums and events can be created
- [ ] QR codes display correct URLs
- [ ] Guests can access album/event pages
- [ ] Guests can upload photos (tested)
- [ ] Photos appear in moderation queue
- [ ] Photos can be approved
- [ ] Approved photos appear in public gallery
- [ ] Lightbox and downloads work
- [ ] Mobile devices can use camera (HTTPS)
- [ ] Google Drive integration works (if configured)
- [ ] No security vulnerabilities identified
- [ ] Performance is acceptable
- [ ] No CORS errors
- [ ] All authentication flows work

## Deployment Status

**Backend Deployment**: ⏳ Pending
**Frontend Deployment**: ⏳ Pending
**Admin Account**: ⏳ Pending
**Google Drive**: ⏳ Pending (Optional)
**Production Testing**: ⏳ Pending
**Mobile Testing**: ⏳ Pending

**Overall Status**: 🟡 Ready to Deploy (Code complete, configuration documented)

