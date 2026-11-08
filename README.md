# Wedding Memories

A complete photo-sharing platform for weddings and events with QR code access, guest uploads, moderation workflow, and dual storage support (local and Google Drive).

## Overview

Wedding Memories enables event organizers to:
- Create albums and events with unique QR codes
- Allow guests to upload photos via QR code links
- Moderate uploaded photos (approve/reject)
- Display approved photos in public galleries
- Store photos locally or in Google Drive
- Download photos individually or in bulk

## Architecture

- **Frontend**: React 19 + Vite + TypeScript + Tailwind CSS
- **Backend**: FastAPI + Python + Uvicorn
- **Database**: MongoDB Atlas
- **Storage**: Local filesystem or Google Drive (per-photo provider selection)
- **Authentication**: JWT access tokens for admin, separate upload tokens for guests
- **Deployment**: Vercel (frontend) + Render (backend)

## Project Status

### Phase 7: Reliability Engineering ✅ Complete
- Atomic deletion with retry queue
- Offloaded local storage I/O
- OAuth callback log redaction
- Mixed-provider photo support
- 69 backend tests + 24 frontend tests passing
- MongoDB Atlas and Google Drive integration verified

### Phase 8: Production Deployment ✅ Preparation Complete
- Production readiness audit complete (no blocking issues)
- Deployment configurations created
- Comprehensive documentation written
- Environment variables documented (31 total)
- Security review complete
- Ready for deployment to Render + Vercel

## Quick Start

### Development Setup

**Prerequisites**:
- Python 3.11+
- Node.js 18+
- MongoDB Atlas account
- Git

**Backend**:
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your MongoDB URI and JWT secret
python -m app.utils.create_admin
uvicorn app.main:app --reload --port 8011
```

**Frontend**:
```powershell
cd frontend
npm install
cp .env.example .env
# Edit .env with backend URL
npm run dev
```

**Access**:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8011/docs
- Admin: http://localhost:5173/admin/login

### Production Deployment

**Ready to deploy?** Follow the complete guide:

📖 **[Production Deployment Guide](docs/DEPLOYMENT_GUIDE.md)**

Quick links:
- [Environment Variables Reference](docs/ENVIRONMENT_VARIABLES.md)
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)
- [Phase 8 Final Report](docs/PHASE8_FINAL_REPORT.md)

**Deployment platforms**:
- Backend: [Render](https://render.com) (configuration: `render.yaml`)
- Frontend: [Vercel](https://vercel.com) (configuration: `frontend/vercel.json`)
- Database: [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
- Storage: Google Drive (optional) or Local filesystem

## Documentation

### For Developers
- [Backend README](backend/README.md) - API, authentication, storage, Google Drive setup
- [Phase 7 Report](docs/PHASE7_FINAL_REPORT.md) - Reliability engineering details
- [Phase 8 Audit](docs/PHASE8_DEPLOYMENT_AUDIT.md) - Production readiness findings

### For Deployment
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) - Step-by-step production deployment
- [Environment Variables](docs/ENVIRONMENT_VARIABLES.md) - Complete variable reference
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md) - Granular task list
- [Phase 8 Report](docs/PHASE8_FINAL_REPORT.md) - Deployment preparation summary

## Features

### Admin Features
- Single administrator account with secure authentication
- Album and event management with unique slugs
- QR code generation for guest access
- Photo moderation workflow (approve/reject/pending)
- Deletion retry queue for failed operations
- Storage provider selection (local or Google Drive)
- Google Drive OAuth integration with encrypted tokens

### Guest Features
- QR code scan to access event upload page
- Mobile camera capture (HTTPS required)
- Gallery picker for photo selection
- Multi-photo upload with progress tracking
- Public gallery viewing with responsive masonry layout
- Lightbox with image navigation and downloads
- No registration required

### Technical Features
- Dual storage support (local + Google Drive)
- Per-photo provider tracking (mixed albums supported)
- Image validation and EXIF stripping
- Upload rate limiting (process-local)
- Atomic deletion with claim lease
- OAuth callback log redaction
- Health check endpoint
- Comprehensive test coverage

## Security

- JWT authentication with configurable expiry
- Separate guest upload tokens (event-scoped, short-lived)
- Strict CORS policy (no wildcards)
- Encrypted Google Drive OAuth tokens (Fernet)
- Private Google Drive files (no public permissions)
- Image validation and sanitization
- Upload size and rate limiting
- No secrets in frontend bundles
- HTTPS required for production

## Testing

**Backend** (69 tests):
```powershell
cd backend
.venv\Scripts\Activate.ps1
pytest
```

**Frontend** (24 tests):
```powershell
cd frontend
npm test
```

**Production build**:
```powershell
cd frontend
npm run build
```

## Technology Stack

### Backend
- **FastAPI**: Modern async Python web framework
- **Uvicorn**: ASGI server
- **Pydantic**: Data validation
- **PyMongo**: MongoDB driver (async)
- **PyJWT**: JWT token handling
- **pwdlib**: Password hashing (Argon2)
- **Pillow**: Image processing
- **Cryptography**: Fernet encryption for OAuth tokens
- **httpx**: Async HTTP client for Google Drive API

### Frontend
- **React 19**: UI framework
- **Vite**: Build tool and dev server
- **TypeScript**: Type safety
- **Tailwind CSS**: Utility-first styling
- **React Router**: Client-side routing
- **Axios**: HTTP client
- **Framer Motion**: Animations
- **QRCode.react**: QR code generation
- **Lucide React**: Icon library

### Database & Storage
- **MongoDB Atlas**: Cloud database
- **Google Drive API**: Optional photo storage
- **Local Filesystem**: Default photo storage

## Project Structure

```
QR Gallery/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # API endpoints
│   │   ├── core/             # Configuration and security
│   │   ├── database/         # MongoDB connection and collections
│   │   ├── middleware/       # Upload size, OAuth log redaction
│   │   ├── models/           # Data models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   ├── storage/          # Local and Google Drive adapters
│   │   └── utils/            # Admin creation, password reset
│   ├── tests/                # Backend tests (69 tests)
│   ├── requirements.txt      # Python dependencies
│   ├── .env.example          # Environment template
│   └── README.md             # Backend documentation
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── pages/            # Route pages
│   │   ├── layouts/          # Layout components
│   │   ├── services/         # API client services
│   │   ├── config/           # Configuration
│   │   └── test/             # Frontend tests (24 tests)
│   ├── dist/                 # Production build output
│   ├── package.json          # Node dependencies
│   ├── vite.config.ts        # Vite configuration
│   ├── vercel.json           # Vercel deployment config
│   └── .env.example          # Environment template
├── docs/
│   ├── DEPLOYMENT_GUIDE.md   # Production deployment guide
│   ├── ENVIRONMENT_VARIABLES.md  # Variable reference
│   ├── DEPLOYMENT_CHECKLIST.md   # Deployment tasks
│   ├── PHASE7_FINAL_REPORT.md    # Reliability report
│   ├── PHASE8_DEPLOYMENT_AUDIT.md  # Readiness audit
│   └── PHASE8_FINAL_REPORT.md    # Deployment report
├── render.yaml               # Render backend configuration
├── .gitignore                # Git ignore rules
└── README.md                 # This file
```

## Environment Variables

### Backend (31 variables)
**Required**:
- `MONGODB_URI` - MongoDB Atlas connection string
- `MONGODB_DATABASE` - Database name (wedding_memories)
- `JWT_SECRET` - JWT signing secret (48+ bytes)
- `FRONTEND_ORIGINS` - Frontend URL for CORS
- `PHOTO_STORAGE_PROVIDER` - `local` or `google_drive`

**Optional** (Google Drive):
- `GOOGLE_DRIVE_CLIENT_ID`
- `GOOGLE_DRIVE_CLIENT_SECRET`
- `GOOGLE_DRIVE_REDIRECT_URI`
- `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY`
- `GOOGLE_DRIVE_FOLDER_ID`

**Configuration**: 21 additional variables with defaults

See [Environment Variables Reference](docs/ENVIRONMENT_VARIABLES.md) for complete details.

### Frontend (2 variables)
- `VITE_API_BASE_URL` - Backend API URL (must end with `/api/v1`)
- `VITE_PUBLIC_APP_URL` - Frontend URL (for QR codes)

## API Endpoints

### Public (no authentication)
- `GET /health` - Health check
- `GET /api/v1/public/albums/{slug}` - Get album
- `GET /api/v1/public/albums/{slug}/events/{slug}` - Get event
- `GET /api/v1/public/albums/{slug}/photos` - List album photos
- `GET /api/v1/public/albums/{slug}/events/{slug}/photos` - List event photos
- `GET /api/v1/public/photos/{id}/image` - Get photo image
- `POST /api/v1/public/albums/{slug}/events/{slug}/upload-session` - Create upload session
- `POST /api/v1/public/albums/{slug}/events/{slug}/photos` - Upload photos

### Admin (JWT required)
- `POST /api/v1/auth/login` - Admin login
- `GET /api/v1/auth/me` - Get current admin
- `POST /api/v1/auth/logout` - Logout (increment token version)
- `GET /api/v1/albums` - List albums
- `POST /api/v1/albums` - Create album
- `GET /api/v1/albums/{id}` - Get album
- `PATCH /api/v1/albums/{id}` - Update album
- `DELETE /api/v1/albums/{id}` - Delete album
- `PATCH /api/v1/albums/{id}/archive` - Archive album
- `PATCH /api/v1/albums/{id}/restore` - Restore album
- `POST /api/v1/albums/{id}/events` - Create event
- `GET /api/v1/albums/{id}/events` - List events
- (Additional event and photo management endpoints)

Interactive documentation: `https://YOUR-BACKEND/docs`

## Known Limitations

1. **Rate Limiting**: Process-local (in-memory), not shared between instances. Run single backend instance until Redis implementation added.

2. **Local Storage**: Ephemeral on Render free tier. Use Google Drive for production or configure persistent disk.

3. **Google OAuth Testing Mode**: Refresh tokens expire after 7 days. Reconnect weekly or complete verification for production.

4. **No Background Workers**: Deletion retries are manual. Automatic retry worker is a future enhancement.

5. **Mobile Viewport Testing**: Automated tests use desktop browser. Physical device testing required for camera/upload verification.

## Troubleshooting

### Backend won't start
- Check `MONGODB_URI` format and credentials
- Verify MongoDB Atlas network access allows 0.0.0.0/0
- Ensure `JWT_SECRET` is at least 32 bytes
- Check Python version (3.11+ required)

### Frontend CORS errors
- Verify `FRONTEND_ORIGINS` in backend matches exact frontend URL
- No trailing slash in origin URL
- Must include protocol (https://)
- Backend must be redeployed after changing CORS

### Google Drive connection fails
- Check redirect URI matches exactly in Google Console
- Verify test user added (if OAuth in Testing mode)
- Confirm encryption key is valid Fernet key
- Check Drive API is enabled

See [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) for 20+ troubleshooting scenarios.

## License

Private project. Not licensed for public use or distribution.

## Support

For deployment issues, consult:
1. [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
2. [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)
3. [Environment Variables](docs/ENVIRONMENT_VARIABLES.md)
4. Backend logs (Render dashboard)
5. Frontend logs (Vercel dashboard)
6. MongoDB Atlas metrics

## Development Roadmap

### Completed
- ✅ Core album and event management
- ✅ Guest upload with QR codes
- ✅ Photo moderation workflow
- ✅ Dual storage support (local + Google Drive)
- ✅ Atomic deletion with retry
- ✅ Mobile-responsive design
- ✅ Production deployment preparation

### Future Enhancements
- ⏳ Redis-backed rate limiting (for multi-instance)
- ⏳ Background deletion worker
- ⏳ Bulk photo downloads (ZIP)
- ⏳ Photo tagging and search
- ⏳ Multi-administrator support
- ⏳ Event invitation emails
- ⏳ Photo analytics dashboard
- ⏳ CDN integration for image delivery

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://react.dev/)
- [Vite](https://vitejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [MongoDB](https://www.mongodb.com/)
- [Google Drive API](https://developers.google.com/drive)

