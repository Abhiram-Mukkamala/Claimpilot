# Claimbot AI - Demo Runbook

**Hackathon Finale Demo Guide**  
**Date: October 23-24, 2026**  
**Last Updated: October 11, 2026**

---

## Quick Start

```powershell
# Run preflight checks (REQUIRED before demo)
.\scripts\preflight.ps1

# If all checks pass, start the demo
.\scripts\start_demo.ps1

# After demo, stop all processes
.\scripts\stop_demo.ps1
```

---

## 1. Demo Script

### Step-by-Step Flow

| # | Step | Action | Expected Result | Timing |
|---|------|--------|-----------------|--------|
| 1 | **System Startup** | Run `start_demo.ps1` | Backend on :8000, Frontend on :4173 | 2-3 min |
| 2 | **Login** | Navigate to http://localhost:4173, enter credentials from .env | User authenticated, redirect to dashboard | 10 sec |
| 3 | **Create New Claim** | Click "New Claim" button, fill form with test data | Claim form submitted, confirmation toast | 30 sec |
| 4 | **Upload Images** | Upload 2-3 damage photos using test images from `public/test-images/` | Images uploaded, processing starts | 15 sec |
| 5 | **Damage Analysis** | Wait for AI model to analyze images | Damage detection results displayed with bounding boxes | 20-45 sec |
| 6 | **Fraud Detection** | System automatically flags suspicious claims | Fraud score and reasons displayed | 10 sec |
| 7 | **Agent Review** | Agent reviews analysis and fraud flags | Agent approval/rejection screen | 20 sec |
| 8 | **Approval** | Agent clicks "Approve" | Claim status changes to "Approved", notification sent | 5 sec |

### Test Data

**Sample Claim for Demo:**
- **Policy Number:** TEST-POL-2026-001
- **Claimant Name:** Demo User
- **Incident Date:** 2026-10-20
- **Description:** Rear-end collision, minor damage
- **Estimated Cost:** $2,500
- **Test Images:** Use images from `public/test-images/` directory

**Demo Credentials:**
- Refer to `insurance-pro/frontend/ClaimPilot/.env` for login credentials
- Admin user: Check .env for ADMIN_EMAIL and ADMIN_PASSWORD

---

## 2. Failure Modes & Workarounds

### Network Issues

| Failure | Symptoms | Workaround | Time to Recover |
|---------|----------|------------|------------------|
| **No Internet** | Supabase connection fails, external API calls timeout | Switch to mobile hotspot, use cached offline data | 30 sec |
| **Supabase Down** | All database operations fail, 500 errors | Use local SQLite fallback (if configured), or show pre-loaded demo data | 1 min |
| **Slow Connection** | Images take >30s to upload | Use smaller test images (<500KB each), reduce to 1-2 images | 20 sec |

### Authentication Issues

| Failure | Symptoms | Workaround | Time to Recover |
|---------|----------|------------|------------------|
| **OTP Email Not Arriving** | Login stuck at OTP entry | Use manual OTP bypass: Check backend logs for OTP code, or temporarily disable OTP in .env | 1 min |
| **Session Timeout** | User redirected to login unexpectedly | Increase session timeout in .env, or re-login quickly | 30 sec |

### Model Issues

| Failure | Symptoms | Workaround | Time to Recover |
|---------|----------|------------|------------------|
| **Model Loading Slow** | First inference takes >1 minute | Pre-load models during startup (warm-up endpoint), use smaller quantized models | 2 min |
| **Model Fails to Load** | 500 error on inference | Verify weight files exist in `backend/app/models/weights/`, check file permissions | 1 min |
| **CUDA Out of Memory** | GPU error, process crashes | Use CPU mode: Set CUDA_VISIBLE_DEVICES="" in .env, or reduce batch size | 2 min |

### Frontend Issues

| Failure | Symptoms | Workaround | Time to Recover |
|---------|----------|------------|------------------|
| **Build Fails** | Frontend doesn't start, npm errors | Run `npm ci` manually, delete node_modules and retry, use `--force` flag | 3 min |
| **Blank Screen** | Page loads but nothing displays | Check browser console for errors, clear cache, try incognito mode | 30 sec |
| **Port 4173 in Use** | Frontend fails to start | Kill process on port 4173: `netstat -ano | findstr 4173`, then `taskkill /PID <pid> /F` | 30 sec |

### Backend Issues

| Failure | Symptoms | Workaround | Time to Recover |
|---------|----------|------------|------------------|
| **Port 8000 in Use** | Backend fails to start | Kill process on port 8000, check for zombie uvicorn processes | 30 sec |
| **Import Errors** | Backend crashes on startup | Run `pip install -r requirements.txt`, verify Python 3.11, check virtual environment | 2 min |
| **Database Connection** | Supabase connection refused | Verify SUPABASE_URL in .env, test with `psql` or API call, check network | 1 min |

---

## 3. Emergency Procedures

### Immediate Recovery (Under 1 Minute)

1. **Hard Refresh**: Press Ctrl+Shift+R to bypass cache
2. **Restart Process**: Run `stop_demo.ps1` then `start_demo.ps1`
3. **Check Logs**:
   - Backend: `curl http://localhost:8000/logs` or check console
   - Frontend: Browser DevTools > Console

### If All Else Fails

1. **Fallback to Recorded Demo**:
   - Open pre-recorded screen capture from USB drive
   - File: `demo_fallback.mp4` (should be on USB backup)
   - Use VLC or Windows Media Player

2. **Manual Walkthrough**:
   - Show static screenshots of each step
   - Describe the flow verbally
   - Use whiteboard if available

---

## 4. Travel & Venue Checklist

### Hardware

- [ ] **Primary Laptop** with charger
- [ ] **Backup Laptop** (optional) with charger
- [ ] **Universal Power Adapter** (for international venues)
- [ ] **HDMI/VGA Adapter** for projector/screen
- [ ] **USB-C to HDMI Dongle** (if laptop requires)
- [ ] **External Mouse & Keyboard** (for presentation ease)
- [ ] **USB Flash Drive** (32GB+) with:
  - Full repository backup
  - Weight files backup
  - Demo video fallback
  - This runbook (PDF + markdown)

### Network

- [ ] **Mobile Hotspot** with sufficient data (10GB+)
- [ ] **Hotspot Credentials** written down
- [ ] **Ethernet Cable** (if venue has wired internet)
- [ ] **Network Configurations** for venue (if provided)

### Software

- [ ] **Python 3.11** installed and in PATH
- [ ] **Node.js** (v18+) installed and in PATH
- [ ] **Git** installed
- [ ] **Docker** installed (optional, for containerized demo)
- [ ] **VS Code** or similar editor (for emergency fixes)
- [ ] **Postman** or **curl** for API testing
- [ ] **Screen Recording Software** (OBS Studio, Camtasia, or built-in)
- [ ] **Zoom/Skype** installed (for remote participants)

### Configuration Files

- [ ] **backend/.env** file (SENSITIVE - do not share)
- [ ] **frontend/ClaimPilot/.env** file
- [ ] **Supabase Credentials** verified and working
- [ ] **SMTP Credentials** verified for OTP emails
- [ ] **Test Images** in `public/test-images/`
- [ ] **Weight Files** in `backend/app/models/weights/`

### Pre-Demo Verification

- [ ] Run `preflight.ps1` - all checks pass
- [ ] Test complete demo flow locally
- [ ] Verify all test images upload successfully
- [ ] Confirm OTP emails are received (if using email auth)
- [ ] Test on venue network (if possible)
- [ ] Charge all devices to 100%

### Presentation Materials

- [ ] Printed copy of this runbook
- [ ] Business cards
- [ ] Project one-pager
- [ ] Architecture diagram
- [ ] Pitch deck (if applicable)

### Day-of Demo Checklist

**Morning of Demo:**
- [ ] Arrive 2 hours early
- [ ] Set up workstation and test all connections
- [ ] Run `preflight.ps1` on venue network
- [ ] Start demo and verify all services
- [ ] Have backup laptop charged and ready
- [ ] Test projector/screen connection
- [ ] Verify audio (if presenting remotely)

**30 Minutes Before Demo:**
- [ ] Close all non-essential applications
- [ ] Clear browser cache
- [ ] Open demo URLs in tabs
- [ ] Have runbook open on screen
- [ ] Silence phone notifications
- [ ] Test screen sharing

**After Demo:**
- [ ] Run `stop_demo.ps1`
- [ ] Collect all materials
- [ ] Note any issues for post-mortem

---

## 5. Directory Structure

```
wt-ops/
├── insurance-pro/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py          # FastAPI application
│   │   │   ├── models/
│   │   │   │   └── weights/     # Model weight files
│   │   │   └── ...
│   │   ├── requirements.txt
│   │   ├── .env                 # Backend environment (SECRET)
│   │   ├── Dockerfile
│   │   └── .dockerignore
│   │
│   └── frontend/
│       └── ClaimPilot/
│           ├── .env             # Frontend environment (SECRET)
│           └── ...
│
├── scripts/
│   ├── start_demo.ps1          # Start all services
│   ├── stop_demo.ps1           # Stop all services
│   └── preflight.ps1           # Pre-demo checks
│
└── docs/
    └── DEMO_RUNBOOK.md         # This file
```

---

## 6. Important Notes

### Security
- **Never commit .env files to Git**
- **Never share .env files** or their contents
- **Use environment variables** for all secrets
- **Clean up** after demo - verify no secrets in browser history or logs

### Performance Tips
- Use smaller test images (<500KB) for faster processing
- Pre-load models by hitting the health endpoint after startup
- Close browser tabs to free memory
- Use wired network connection if available

### Common Pitfalls
- **Port Conflicts**: Always run `stop_demo.ps1` before starting again
- **Python Environment**: Use the same Python version everywhere (3.11)
- **Node Version**: Ensure Node.js version matches package-lock.json
- **File Paths**: All paths in this runbook are relative to `wt-ops/`

---

## 7. Contact Information

| Role | Name | Contact |
|------|------|---------|
| Technical Lead | [Your Name] | [Your Phone] |
| Backup Support | [Name] | [Phone] |
| Project Manager | [Name] | [Phone] |

---

**Good luck with the demo!**

*Last updated: October 11, 2026*
