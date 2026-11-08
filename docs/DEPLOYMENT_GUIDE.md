# Wedding Memories — Production Deployment Guide

Last Updated: 2026-11-08

## Overview

This guide covers production deployment to:
- **Backend**: Render (Free tier with optional paid upgrade)
- **Frontend**: Vercel (Hobby/Pro tier)
- **Database**: MongoDB Atlas (Free tier M0)
- **Storage**: Google Drive (optional) or Local filesystem

## Prerequisites

### Required Accounts
- [ ] MongoDB Atlas account with a cluster created
- [ ] Render account (https://render.com)
- [ ] Vercel account (https://vercel.com)
- [ ] Google Cloud Console project (if using Google Drive storage)

### Required Secrets Ready
- [ ] MongoDB Atlas connection URI
- [ ] JWT secret (48+ bytes)
- [ ] Google Drive OAuth credentials (if using Drive storage)
- [ ] Fernet encryption key (if using Drive storage)

## Part 1: MongoDB Atlas Setup

### 1.1 Create Database

1. Log into MongoDB Atlas
2. Navigate to your cluster
3. Click **Browse Collections**
4. Create database: `wedding_memories`
5. Initial collection will be created automatically by the backend

### 1.2 Configure Network Access

**For Render (recommended approach)**:
1. Navigate to **Network Access** in Atlas
2. Click **Add IP Address**
3. Click **Allow Access from Anywhere** (0.0.0.0/0)
4. Add description: "Render backend (dynamic IPs)"

**Security Note**: Render uses dynamic outbound IPs on the free tier. The recommended approach is to allow all IPs (0.0.0.0/0) and rely on:
- Strong MongoDB connection string
- Database-level authentication
- Application-level JWT authentication
- Private connection URI (never exposed to frontend)

For paid Render plans with static IPs, you can restrict to specific IP ranges.

### 1.3 Create Database User

1. Navigate to **Database Access**
2. Click **Add New Database User**
3. Choose **Password** authentication
4. Username: `wedding_memories_app` (or your choice)
5. Generate a strong password (save securely)
6. Database User Privileges: **Read and write to any database**
7. Click **Add User**

### 1.4 Get Connection String

1. Click **Connect** on your cluster
2. Choose **Connect your application**
3. Driver: Python, Version: 3.12 or later
4. Copy the connection string
5. Replace `<password>` with your database user password
6. Replace `<dbname>` with `wedding_memories` if present, or add `?retryWrites=true&w=majority` at the end

Example format:
```
mongodb+srv://wedding_memories_app:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/wedding_memories?retryWrites=true&w=majority
```

**Important**: Keep this connection string secret. Never commit it to Git or expose it in frontend code.

## Part 2: Google Drive Setup (Optional)

If you want to use Google Drive for photo storage instead of local filesystem, complete this section. Otherwise, skip to Part 3.

### 2.1 Create Google Cloud Project

1. Go to https://console.cloud.google.com
2. Create a new project or select existing
3. Project name: "Wedding Memories" (or your choice)

### 2.2 Enable Google Drive API

1. Navigate to **APIs & Services** > **Library**
2. Search for "Google Drive API"
3. Click **Enable**

### 2.3 Configure OAuth Consent Screen

1. Navigate to **APIs & Services** > **OAuth consent screen**
2. User Type: **External** (unless you have Google Workspace)
3. Click **Create**
4. Fill in required fields:
   - App name: "Wedding Memories"
   - User support email: Your email
   - Developer contact: Your email
5. Scopes: Click **Add or Remove Scopes**
   - Search for: `drive.file`
   - Select: `.../auth/drive.file` - "View and manage Google Drive files and folders that you have opened or created with this app"
   - Click **Update**
6. Test users: Add the Google account email you'll use for photo storage
7. Click **Save and Continue**

**Publishing Status**:
- For personal/testing use: Keep in "Testing" mode
- For production with multiple users: You'll need to submit for verification
- Testing mode: Refresh tokens expire after 7 days unless app is verified
- For long-term production: Request verification from Google

### 2.4 Create OAuth Credentials

1. Navigate to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Application type: **Web application**
4. Name: "Wedding Memories Backend"
5. **Authorized redirect URIs**:
   - Development: `http://localhost:8011/api/v1/integrations/google-drive/callback`
   - Production: `https://YOUR-RENDER-APP.onrender.com/api/v1/integrations/google-drive/callback`
   
   **Critical**: The production URI must exactly match your deployed backend URL. You can add both development and production URIs to the same OAuth client.

6. Click **Create**
7. **Save these values securely**:
   - Client ID
   - Client Secret

### 2.5 Generate Encryption Key

Open terminal and run:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Critical**: Save this key securely. You cannot decrypt existing tokens without it. Back it up independently from your hosting provider.

### 2.6 Create Drive Folder (Optional)

You can let the app create its own folder automatically, or:

1. Go to https://drive.google.com
2. Create a folder: "Wedding Memories"
3. Right-click the folder > **Share** > Copy the folder ID from the URL
4. Example URL: `https://drive.google.com/drive/folders/1ABCdef-GHI123jkl456MNO`
5. Folder ID: `1ABCdef-GHI123jkl456MNO`

## Part 3: Backend Deployment (Render)

### 3.1 Create Web Service

1. Log into Render dashboard
2. Click **New** > **Web Service**
3. Connect your Git repository (GitHub/GitLab/Bitbucket)
4. Select the `QR Gallery` repository (or your fork)

### 3.2 Configure Service

**Basic Settings**:
- Name: `wedding-memories-backend` (or your choice)
- Region: Choose closest to your users
- Branch: `main` (or your production branch)
- Root Directory: `backend`
- Runtime: `Python 3`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Instance Type**:
- Free tier: 512 MB RAM (sufficient for testing)
- Paid: Upgrade if needed for production load

**Health Check**:
- Path: `/health`

### 3.3 Set Environment Variables

Navigate to the **Environment** section and add these variables:

#### Required Variables

```bash
# Application
APP_NAME=Wedding Memories
APP_ENV=production
DEBUG=false
API_V1_PREFIX=/api/v1

# MongoDB (REQUIRED - use your Atlas connection string)
MONGODB_URI=mongodb+srv://username:password@cluster.xxxxx.mongodb.net/wedding_memories?retryWrites=true&w=majority
MONGODB_DATABASE=wedding_memories

# JWT Authentication (REQUIRED - generate new secret)
JWT_SECRET=<GENERATE_NEW_SECRET>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS (REQUIRED - set after deploying frontend)
FRONTEND_ORIGINS=https://your-app.vercel.app

# Storage (REQUIRED - local or google_drive)
PHOTO_STORAGE_PROVIDER=local
PHOTO_STORAGE_LOCAL_PATH=/opt/render/project/src/storage-data
```

**Generate JWT_SECRET**:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

#### Optional: Google Drive Variables

Only add these if using Google Drive storage:

```bash
GOOGLE_DRIVE_CLIENT_ID=<YOUR_CLIENT_ID>
GOOGLE_DRIVE_CLIENT_SECRET=<YOUR_CLIENT_SECRET>
GOOGLE_DRIVE_REDIRECT_URI=https://your-backend.onrender.com/api/v1/integrations/google-drive/callback
GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY=<YOUR_FERNET_KEY>
GOOGLE_DRIVE_FOLDER_ID=<OPTIONAL_FOLDER_ID>
```

#### Optional: Upload Limits

Default values are suitable for most deployments. Override if needed:

```bash
UPLOAD_SESSION_MINUTES=30
UPLOAD_MAX_FILE_BYTES=12582912
UPLOAD_MAX_REQUEST_BYTES=57671680
UPLOAD_MAX_FILES_PER_REQUEST=10
UPLOAD_MAX_FILES_PER_SESSION=30
UPLOAD_MAX_BYTES_PER_SESSION=104857600
UPLOAD_SESSIONS_PER_IP_PER_HOUR=20
UPLOAD_REQUESTS_PER_IP_PER_HOUR=30
```

### 3.4 Deploy

1. Click **Create Web Service**
2. Render will build and deploy automatically
3. Monitor the deploy logs for errors
4. Once deployed, note your backend URL: `https://YOUR-APP.onrender.com`

### 3.5 Verify Backend

1. Visit `https://YOUR-APP.onrender.com/health`
2. Expected response:
   ```json
   {
     "status": "healthy",
     "application": "Wedding Memories",
     "database": {
       "status": "connected",
       "name": "wedding_memories"
     }
   }
   ```

3. If `database.status` is `"disconnected"`:
   - Check MongoDB connection string
   - Verify MongoDB Atlas network access (0.0.0.0/0 allowed)
   - Check MongoDB Atlas user credentials
   - Review Render logs for specific error messages

### 3.6 Update CORS Configuration

After verifying the backend works:

1. Deploy the frontend (see Part 4)
2. Return to Render environment variables
3. Update `FRONTEND_ORIGINS` with your exact Vercel URL
4. Example: `https://wedding-memories.vercel.app`
5. **Do not include trailing slash**
6. For multiple origins, use comma separation: `https://app1.vercel.app,https://app2.vercel.app`
7. Render will redeploy automatically after saving

## Part 4: Frontend Deployment (Vercel)

### 4.1 Deploy to Vercel

1. Log into Vercel dashboard
2. Click **Add New** > **Project**
3. Import your Git repository
4. Configure project:
   - Framework Preset: **Vite**
   - Root Directory: `frontend`
   - Build Command: `npm run build` (default)
   - Output Directory: `dist` (default)
   - Install Command: `npm install` (default)

### 4.2 Set Environment Variables

In the **Environment Variables** section, add:

```bash
VITE_API_BASE_URL=https://YOUR-BACKEND.onrender.com/api/v1
VITE_PUBLIC_APP_URL=https://YOUR-FRONTEND.vercel.app
```

**Critical**:
- `VITE_API_BASE_URL` must end with `/api/v1`
- `VITE_PUBLIC_APP_URL` must be your exact frontend URL (no trailing slash)
- These are build-time variables; redeploy after changing them

### 4.3 Deploy

1. Click **Deploy**
2. Vercel will build and deploy automatically
3. Note your frontend URL: `https://YOUR-APP.vercel.app`

### 4.4 Update Backend CORS

Return to Render and update the `FRONTEND_ORIGINS` variable with your Vercel URL (see Part 3.6).

### 4.5 Verify Frontend

1. Visit your Vercel URL
2. You should see the Wedding Memories homepage
3. Navigate to `/admin/login`
4. Verify the page loads (don't log in yet)

## Part 5: Create Administrator Account

### 5.1 Connect to Backend

You need Python access to run the admin creation script. Choose one option:

**Option A: Local with Production MongoDB**

1. Clone repository locally
2. Install Python dependencies:
   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # or: source .venv/bin/activate  # Mac/Linux
   pip install -r requirements.txt
   ```

3. Create `.env` file in `backend` directory:
   ```bash
   MONGODB_URI=<YOUR_PRODUCTION_MONGODB_URI>
   MONGODB_DATABASE=wedding_memories
   JWT_SECRET=<ANY_VALUE_FOR_THIS_SCRIPT>
   ```

4. Run admin creation:
   ```bash
   python -m app.utils.create_admin
   ```

5. Follow prompts to enter email and password (minimum 12 characters)

**Option B: Render Shell (if available on your plan)**

1. In Render dashboard, click on your service
2. Click **Shell** tab
3. Run: `python -m app.utils.create_admin`
4. Follow prompts

### 5.2 Verify Administrator Login

1. Visit `https://YOUR-FRONTEND.vercel.app/admin/login`
2. Enter the email and password you created
3. You should be redirected to the admin dashboard

If login fails:
- Check browser console for API errors
- Verify `VITE_API_BASE_URL` is correct in Vercel
- Verify `FRONTEND_ORIGINS` is correct in Render
- Check Render logs for authentication errors

## Part 6: Connect Google Drive (Optional)

If you configured Google Drive in Part 2, connect it now:

1. Log into admin dashboard
2. Navigate to **Settings** (Storage Settings)
3. Click **Connect Google Drive**
4. Complete Google OAuth consent screen
5. Grant permissions
6. Verify status shows: **Connected and ready**
7. Select **Google Drive** as storage provider
8. Click **Save**

**New uploads** will now use Google Drive. Existing local photos remain on local storage and continue to work (photos track their own storage provider).

## Part 7: Production Verification

### 7.1 Backend Health

Visit `https://YOUR-BACKEND.onrender.com/health`

Expected response:
```json
{
  "status": "healthy",
  "application": "Wedding Memories",
  "database": {
    "status": "connected",
    "name": "wedding_memories"
  }
}
```

### 7.2 API Documentation

Visit `https://YOUR-BACKEND.onrender.com/docs` to see interactive API documentation.

### 7.3 Admin Functions

1. ✅ Login works
2. ✅ Create a test album
3. ✅ Create a test event within the album
4. ✅ Verify QR code is displayed with correct URL

### 7.4 Guest Experience

1. Visit the guest album URL (from QR code or link)
2. Verify album and event information displays
3. Click **Upload Photos**
4. Test photo upload:
   - Select a test image
   - Verify upload succeeds
   - Check admin moderation queue

### 7.5 Photo Moderation

1. Navigate to **Photo Moderation** in admin
2. Verify test photo appears as **Pending**
3. Approve the photo
4. Verify it appears in the public gallery

### 7.6 Mobile Testing

Test on physical devices:

**Viewports to test**:
- 320×700 (iPhone SE)
- 360×800 (Android small)
- 393×852 (iPhone 14 Pro)
- 412×924 (Android medium)
- 430×932 (iPhone 14 Pro Max)
- 768×1024 (iPad)

**Functions to verify**:
- [ ] Navigation and layout
- [ ] Camera access (requires HTTPS)
- [ ] Gallery picker
- [ ] Photo upload
- [ ] Gallery viewing
- [ ] Lightbox and swipe gestures
- [ ] Image download

### 7.7 Security Checks

- [ ] Admin routes require authentication
- [ ] Guest upload requires valid upload token
- [ ] Images stream through backend (not direct file access)
- [ ] No CORS errors in browser console
- [ ] OAuth callback works without exposing secrets

## Part 8: Post-Deployment Configuration

### 8.1 Custom Domain (Optional)

**Vercel**:
1. Navigate to project **Settings** > **Domains**
2. Add your custom domain
3. Configure DNS records as instructed
4. Update `VITE_PUBLIC_APP_URL` after domain is active
5. Redeploy frontend

**Render**:
1. Navigate to service **Settings** > **Custom Domains**
2. Add your custom domain
3. Configure DNS CNAME record
4. Update `GOOGLE_DRIVE_REDIRECT_URI` if using Drive
5. Update `VITE_API_BASE_URL` in Vercel
6. Redeploy both services

### 8.2 Monitoring

**Render**:
- Monitor service logs for errors
- Watch for MongoDB connection issues
- Check Google Drive API errors
- Monitor `/health` endpoint availability

**MongoDB Atlas**:
- Set up alerts for high connection count
- Monitor storage usage
- Enable backup if needed

**Vercel**:
- Monitor build success rate
- Check for frontend errors in project analytics

### 8.3 Backup Strategy

**MongoDB**:
1. Enable Atlas backups (paid tier) or
2. Export collections manually using `mongodump`

**Google Drive**:
- Photos are already in Drive (durable)
- Back up MongoDB metadata separately
- **Critical**: Back up `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY` securely

**Local Storage (if used)**:
- Render free tier has ephemeral filesystem
- Paid tier: Set up persistent disk
- Regular backups required if using local storage in production

### 8.4 OAuth Token Refresh

**Google Drive Testing Mode**:
- Refresh tokens expire after 7 days
- You'll need to reconnect every week
- For long-term production: Submit app for verification

**To reconnect**:
1. Admin dashboard > **Settings**
2. Click **Disconnect** (if showing error)
3. Click **Connect Google Drive**
4. Complete OAuth flow again

## Troubleshooting

### Backend Deploy Fails

**Build fails**:
- Check Python version (3.11+ required)
- Verify all dependencies in `requirements.txt` install successfully
- Check Render build logs

**Service unhealthy**:
- Visit `/health` to see database status
- Check environment variables are set correctly
- Verify MongoDB connection string
- Check MongoDB Atlas network access allows Render

### Frontend Deploy Fails

**Build fails**:
- Check Node version (18+ required)
- Verify `VITE_API_BASE_URL` is set
- Check build logs for TypeScript errors

**Blank page**:
- Check browser console for errors
- Verify `vercel.json` rewrite rules are in place
- Check that `dist` directory exists in build

### CORS Errors

**Error**: `Access-Control-Allow-Origin`

**Fix**:
1. Verify `FRONTEND_ORIGINS` in Render exactly matches your Vercel URL
2. No trailing slash
3. Must be full HTTPS URL
4. Redeploy backend after changing

### Authentication Fails

**Login returns 401**:
- Check `JWT_SECRET` is set in Render
- Verify admin account exists in MongoDB
- Check Render logs for authentication errors

**Login succeeds but redirects to login**:
- Check `VITE_API_BASE_URL` in Vercel
- Verify CORS is configured correctly
- Check browser console for API errors

### Google Drive Connection Fails

**OAuth callback fails**:
- Verify `GOOGLE_DRIVE_REDIRECT_URI` matches Google Cloud Console exactly
- Check if OAuth consent screen is configured
- Verify test user is added (if in Testing mode)

**"Needs to be reconnected" after working**:
- Refresh token may have expired (7 days in Testing mode)
- Reconnect from admin settings
- Consider submitting for verification for long-term use

**Upload fails to Drive**:
- Check encryption key is set
- Verify account has write permission to folder
- Check Render logs for specific Drive API errors
- Verify Google Drive API is enabled

### Photo Upload Fails

**413 Request Entity Too Large**:
- Check file size (default max: 12 MB)
- Verify `UPLOAD_MAX_FILE_BYTES` setting

**422 Validation Error**:
- Check image format (only JPEG/PNG/WebP supported)
- Verify image is not corrupted

**429 Too Many Requests**:
- Rate limit reached
- Wait before retrying
- Note: Limits reset on backend restart (in-memory)

### Mobile Camera Not Working

**Cause**: Camera requires HTTPS
- Verify frontend is served over HTTPS
- Local testing: Use `localhost` (HTTPS not required)
- Production: Vercel provides HTTPS automatically

## Security Maintenance

### Regular Tasks

**Monthly**:
- Review MongoDB Atlas access logs
- Check for unusual API usage patterns
- Review uploaded photos for moderation

**Quarterly**:
- Rotate JWT secret (requires user re-login)
- Review and update dependencies
- Check for security advisories

**Annually**:
- Review Google OAuth scopes and permissions
- Audit administrator accounts
- Review backup and recovery procedures

### Secret Rotation

**JWT Secret Rotation**:
1. Generate new secret
2. Update `JWT_SECRET` in Render
3. All users must log in again

**Google Drive Encryption Key Rotation**:
1. Generate new key
2. Set as `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY`
3. Set old key as `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY_PREVIOUS`
4. Admin visits Settings page (triggers re-encryption)
5. Remove `PREVIOUS` key variable
6. Redeploy

## Scaling Considerations

### Current Limitations

**Rate Limiting**:
- Process-local (in-memory)
- Not shared between instances
- Resets on restart

**Recommendation**: Run single backend instance until implementing Redis-backed rate limiting.

### Upgrade Path

**When to scale**:
- Multiple events running simultaneously
- High photo upload volume
- Performance degrades

**Scaling options**:
1. Upgrade Render instance size
2. Implement Redis for shared rate limiting
3. Use MongoDB connection pooling
4. Consider CDN for image delivery
5. Add dedicated storage service (S3/CloudFlare R2)

## Support and Resources

- **Backend README**: `backend/README.md`
- **Phase 7 Report**: `docs/PHASE7_FINAL_REPORT.md`
- **Phase 8 Audit**: `docs/PHASE8_DEPLOYMENT_AUDIT.md`
- **Render Documentation**: https://render.com/docs
- **Vercel Documentation**: https://vercel.com/docs
- **MongoDB Atlas**: https://www.mongodb.com/docs/atlas/
- **Google Drive API**: https://developers.google.com/drive

