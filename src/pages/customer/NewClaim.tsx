import { useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { claimsApi } from '../../services/claimsApi';
import { Card } from '../../components/ui/Card';
import { Upload, X, ChevronRight, Car, AlertTriangle, Flame, CloudLightning, Video, FileText, CheckCircle2 } from 'lucide-react';
import { useGSAP, animateStep, animateFadeIn } from '../../lib/gsap';

type Step = 1 | 2 | 3 | 4;

const MAX_IMAGES = 10;
const MAX_VIDEOS = 2;
const UPLOAD_COOLDOWN_MS = 500;

const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];
const ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'];

const ALLOWED_VIDEO_TYPES = ['video/mp4', 'video/quicktime', 'video/webm'];
const ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.webm'];

const isValidImageFile = (file: File): boolean => {
  const extension = '.' + (file.name.split('.').pop() || '').toLowerCase();
  const mimeType = file.type.toLowerCase();
  return ALLOWED_IMAGE_TYPES.includes(mimeType) || ALLOWED_IMAGE_EXTENSIONS.includes(extension);
};

const isValidVideoFile = (file: File): boolean => {
  const extension = '.' + (file.name.split('.').pop() || '').toLowerCase();
  const mimeType = file.type.toLowerCase();
  return ALLOWED_VIDEO_TYPES.includes(mimeType) || ALLOWED_VIDEO_EXTENSIONS.includes(extension);
};

// ── India-format validation ───────────────────────────────────────────────────
// HSRP / Registration plate: e.g. MH12AB1234
const HSRP_REGEX = /^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$/;
const validateHSRP = (v: string) => !v || HSRP_REGEX.test(v.toUpperCase());

// Indian Driving License format: State(2) + RTO(2) + Year(4) + Number(7) = 15 chars
// Allows spaces or hyphens between components (e.g., MH14 20110012345 or MH-14-2011-0012345 or MH1420110012345)
const validateIndianDL = (dl: string): boolean => {
  if (!dl) return false;
  const clean = dl.replace(/[-\s]/g, '').toUpperCase();
  return /^[A-Z]{2}[0-9]{2}(?:19|20)[0-9]{2}[0-9]{7}$/.test(clean);
};

interface UploadedVideo {
  id: string;
  url: string;
  name: string;
}

export const NewClaim = () => {
  const navigate = useNavigate();
  const routerLocation = useLocation();
  const params = new URLSearchParams(routerLocation.search);
  const initialType = params.get('type') || 'Accident';

  const [step, setStep] = useState<Step>(1);
  const [loading, setLoading] = useState(false);
  const prevStepRef = useRef<Step>(1);
  const stepContainerRef = useRef<HTMLDivElement>(null);
  const noticeRef = useRef<HTMLDivElement>(null);

  // Form State
  const [claimType, setClaimType] = useState(initialType);
  const [policyNumber, setPolicyNumber] = useState('');
  const [incidentDate, setIncidentDate] = useState('');
  const [location, setLocation] = useState('');
  const [vehicle, setVehicle] = useState('');
  const [engineNumber, setEngineNumber] = useState('');
  const [chassisNumber, setChassisNumber] = useState('');
  const [hsrpNumber, setHsrpNumber] = useState('');
  const [driverName, setDriverName] = useState('');
  const [driverLicenseNumber, setDriverLicenseNumber] = useState('');
  const [driverLicenseFrontPhoto, setDriverLicenseFrontPhoto] = useState<string | null>(null);
  const [driverLicenseBackPhoto, setDriverLicenseBackPhoto] = useState<string | null>(null);
  const [description, setDescription] = useState('');
  const [images, setImages] = useState<string[]>([]);
  const [videos, setVideos] = useState<UploadedVideo[]>([]);
  const [uploadNotice, setUploadNotice] = useState<{ type: 'warning' | 'error'; message: string } | null>(null);
  const lastUploadTimestamp = useRef<number>(0);

  // Inline field-validation errors (shown on blur, cleared when field becomes valid)
  const [hsrpError, setHsrpError] = useState('');
  const [dlError, setDlError] = useState('');

  useGSAP(() => {
    if (stepContainerRef.current) {
      const direction = step >= prevStepRef.current ? 'forward' : 'backward';
      animateStep(stepContainerRef.current, direction);
      prevStepRef.current = step;
    }
  }, { dependencies: [step] });

  useGSAP(() => {
    if (uploadNotice && noticeRef.current) {
      animateFadeIn(noticeRef.current, { y: -6, duration: 0.22 });
    }
  }, { dependencies: [uploadNotice] });

  const handleNext = () => setStep((s) => Math.min(s + 1, 4) as Step);
  const handlePrev = () => setStep((s) => Math.max(s - 1, 1) as Step);

  const checkRateLimit = (): boolean => {
    const now = Date.now();
    if (now - lastUploadTimestamp.current < UPLOAD_COOLDOWN_MS) {
      setUploadNotice({
        type: 'warning',
        message: 'Upload rate limit: Please wait a moment before uploading more files.'
      });
      return false;
    }
    lastUploadTimestamp.current = now;
    return true;
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    if (!checkRateLimit()) {
      e.target.value = '';
      return;
    }

    const availableSlots = MAX_IMAGES - images.length;
    if (availableSlots <= 0) {
      setUploadNotice({
        type: 'error',
        message: `Maximum limit reached: You cannot upload more than ${MAX_IMAGES} photos.`
      });
      e.target.value = '';
      return;
    }

    const incoming = Array.from(files);
    const validFiles = incoming.filter(isValidImageFile);
    const invalidCount = incoming.length - validFiles.length;

    if (validFiles.length === 0) {
      setUploadNotice({
        type: 'error',
        message: 'Unsupported format. Only JPG, PNG, WEBP, and HEIC images are accepted.'
      });
      e.target.value = '';
      return;
    }

    const filesToUpload = validFiles.slice(0, availableSlots);

    if (invalidCount > 0 && validFiles.length > availableSlots) {
      setUploadNotice({
        type: 'warning',
        message: `${invalidCount} invalid file${invalidCount > 1 ? 's' : ''} rejected (only JPG/PNG/WEBP/HEIC allowed). Added ${filesToUpload.length} photo${filesToUpload.length > 1 ? 's' : ''} (max ${MAX_IMAGES} reached).`
      });
    } else if (invalidCount > 0) {
      setUploadNotice({
        type: 'warning',
        message: `${invalidCount} non-image or unsupported file${invalidCount > 1 ? 's' : ''} rejected. Only JPG, PNG, WEBP, and HEIC images are accepted.`
      });
    } else if (validFiles.length > availableSlots) {
      setUploadNotice({
        type: 'warning',
        message: `Upload limit reached: Only ${availableSlots} more photo${availableSlots > 1 ? 's' : ''} allowed (max ${MAX_IMAGES}). Added ${filesToUpload.length}.`
      });
    } else {
      setUploadNotice(null);
    }

    const newUrls = filesToUpload.map(file => URL.createObjectURL(file));
    setImages(prev => [...prev, ...newUrls]);
    e.target.value = '';
  };

  const removeImage = (index: number) => {
    setImages(prev => prev.filter((_, i) => i !== index));
    setUploadNotice(null);
  };

  const handleVideoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    if (!checkRateLimit()) {
      e.target.value = '';
      return;
    }

    const availableSlots = MAX_VIDEOS - videos.length;
    if (availableSlots <= 0) {
      setUploadNotice({
        type: 'error',
        message: `Maximum limit reached: You cannot upload more than ${MAX_VIDEOS} videos.`
      });
      e.target.value = '';
      return;
    }

    const incoming = Array.from(files);
    const validFiles = incoming.filter(isValidVideoFile);
    const invalidCount = incoming.length - validFiles.length;

    if (validFiles.length === 0) {
      setUploadNotice({
        type: 'error',
        message: 'Unsupported format. Only MP4, MOV, and WebM videos are accepted.'
      });
      e.target.value = '';
      return;
    }

    const filesToUpload = validFiles.slice(0, availableSlots);

    if (invalidCount > 0 && validFiles.length > availableSlots) {
      setUploadNotice({
        type: 'warning',
        message: `${invalidCount} invalid file${invalidCount > 1 ? 's' : ''} rejected (only MP4/MOV/WebM allowed). Added ${filesToUpload.length} video (max ${MAX_VIDEOS} reached).`
      });
    } else if (invalidCount > 0) {
      setUploadNotice({
        type: 'warning',
        message: `${invalidCount} non-video or unsupported file${invalidCount > 1 ? 's' : ''} rejected. Only MP4, MOV, and WebM videos are accepted.`
      });
    } else if (validFiles.length > availableSlots) {
      setUploadNotice({
        type: 'warning',
        message: `Upload limit reached: Only ${availableSlots} more video${availableSlots > 1 ? 's' : ''} allowed (max ${MAX_VIDEOS}). Added ${filesToUpload.length}.`
      });
    } else {
      setUploadNotice(null);
    }

    const newVideos: UploadedVideo[] = filesToUpload.map((file, i) => ({
      id: `${Date.now()}-${i}-${Math.random().toString(36).slice(2, 7)}`,
      url: URL.createObjectURL(file),
      name: file.name
    }));

    setVideos(prev => [...prev, ...newVideos]);
    e.target.value = '';
  };

  const removeVideo = (id: string) => {
    setVideos(prev => prev.filter(v => v.id !== id));
    setUploadNotice(null);
  };

  const handleDLPhotoUpload = (e: React.ChangeEvent<HTMLInputElement>, side: 'front' | 'back') => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!isValidImageFile(file)) {
      setUploadNotice({
        type: 'error',
        message: 'Unsupported format. Please upload a JPG, PNG, WEBP, or HEIC image.'
      });
      e.target.value = '';
      return;
    }

    const previewUrl = URL.createObjectURL(file);
    if (side === 'front') {
      setDriverLicenseFrontPhoto(previewUrl);
    } else {
      setDriverLicenseBackPhoto(previewUrl);
    }
    setUploadNotice(null);
    e.target.value = '';
  };

  const handleSubmit = async () => {
    setLoading(true);
    const newClaim = await claimsApi.createClaim({
      claimType,
      policyNumber: policyNumber || undefined,
      incidentDate,
      location,
      vehicle,
      engineNumber: engineNumber || undefined,
      chassisNumber: chassisNumber || undefined,
      hsrpNumber: hsrpNumber || undefined,
      driverName: driverName || undefined,
      driverLicenseNumber: driverLicenseNumber || undefined,
      driverLicenseFrontPhoto: driverLicenseFrontPhoto || undefined,
      driverLicenseBackPhoto: driverLicenseBackPhoto || undefined,
      description,
      images,
      video: videos[0]?.url || undefined,
      videos: videos.map(v => v.url)
    });
    setLoading(false);
    navigate(`/customer/claims/${newClaim.id}`);
  };

  const typeOptions = [
    { id: 'Accident', icon: <Car size={24} /> },
    { id: 'Fire', icon: <Flame size={24} /> },
    { id: 'Natural Event', icon: <CloudLightning size={24} /> },
  ];

  return (
    <div style={{ width: '140%', padding: '0 2.5rem', boxSizing: 'border-box' }}>
      <div style={{ maxWidth: '900px', marginLeft: '6rem', paddingTop: '2rem', paddingBottom: '4rem' }}>
        <div className="mb-8">
          <h1 className="text-2xl mb-6">Request a Claim</h1>

          {/* Progress Stepper */}
          <div className="flex justify-between items-center text-sm" style={{ padding: '0 1rem' }}>
            {[
              { num: 1, label: 'Details' },
              { num: 2, label: 'Driver Details' },
              { num: 3, label: 'Photos & Video' },
              { num: 4, label: 'Review' }
            ].map((s) => (
              <div key={s.num} className="flex flex-col items-center gap-xs relative" style={{ flex: 1 }}>
                <div
                  style={{
                    width: '24px', height: '24px', borderRadius: '50%',
                    backgroundColor: step >= s.num ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                    color: step >= s.num ? '#fff' : 'var(--text-secondary)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 'bold', fontSize: '0.75rem', zIndex: 2
                  }}
                >
                  {s.num}
                </div>
                <span style={{ color: step >= s.num ? 'var(--text-primary)' : 'var(--text-secondary)', fontSize: '0.8125rem', textAlign: 'center' }}>{s.label}</span>
                {s.num < 4 && (
                  <div style={{ position: 'absolute', top: '12px', left: '50%', width: '100%', height: '2px', backgroundColor: step > s.num ? 'var(--accent-primary)' : 'var(--bg-tertiary)', zIndex: 1 }} />
                )}
              </div>
            ))}
          </div>
        </div>

        <Card style={{
          padding: '2rem',
          boxShadow: '0 8px 24px -4px rgba(0,0,0,0.18), 0 32px 64px -12px rgba(0,0,0,0.22), 0 0 0 1px var(--border)',
          transform: 'translateY(0)',
          transition: 'box-shadow 0.3s ease, transform 0.3s ease',
          borderRadius: 'var(--radius-lg)',
        }}>
          <div ref={stepContainerRef}>
            {step === 1 && (
              <div className="flex flex-col gap-lg">
                <div>
                  <h2 className="text-xl mb-1">What happened?</h2>
                  <p className="text-muted text-sm">Select the type of incident.</p>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '1rem' }}>
                  {typeOptions.map(opt => (
                    <div
                      key={opt.id}
                      onClick={() => setClaimType(opt.id)}
                      className="interactive-card flex flex-col items-center justify-center gap-sm text-center"
                      style={{
                        padding: '1.5rem 1rem',
                        border: claimType === opt.id ? '2px solid var(--accent-primary)' : '1px solid var(--border-color)',
                        backgroundColor: claimType === opt.id ? 'var(--accent-dim)' : 'var(--bg-primary)'
                      }}
                    >
                      <div style={{ color: claimType === opt.id ? 'var(--accent-primary)' : 'var(--text-secondary)' }}>{opt.icon}</div>
                      <span className="text-sm font-medium">{opt.id}</span>
                    </div>
                  ))}
                </div>

                <div className="form-group mt-4">
                  <label className="form-label">Vehicle Model</label>
                  <input type="text" className="form-input" placeholder="e.g. Honda City " value={vehicle} onChange={(e) => setVehicle(e.target.value)} />
                </div>

                {/* Vehicle identifier row: Engine + Chassis + HSRP */}
                <div className="flex gap-md" style={{ flexWrap: 'wrap' }}>
                  <div className="form-group" style={{ flex: 1, minWidth: '180px' }}>
                    <label className="form-label">
                      Engine Number
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Enter last 6 digits"
                      value={engineNumber}
                      onChange={(e) => setEngineNumber(e.target.value.toUpperCase())}
                    />
                  </div>

                  <div className="form-group" style={{ flex: 1, minWidth: '180px' }}>
                    <label className="form-label">
                      Chassis Number
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Enter last 6 digits"
                      value={chassisNumber}
                      onChange={(e) => setChassisNumber(e.target.value.toUpperCase())}
                    />
                  </div>

                  <div className="form-group" style={{ flex: 1, minWidth: '180px' }}>
                    <label className="form-label">
                      HSRP / Reg. Number
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. MH12AB1234"
                      value={hsrpNumber}
                      maxLength={10}
                      onChange={(e) => {
                        const v = e.target.value.toUpperCase();
                        setHsrpNumber(v);
                        if (hsrpError && validateHSRP(v)) setHsrpError('');
                      }}
                      onBlur={() => setHsrpError(validateHSRP(hsrpNumber) ? '' : 'Invalid format. Use Indian plate format: 2 letters + 2 digits + 1–3 letters + 4 digits (e.g. MH12AB1234).')}
                      style={{ borderColor: hsrpError ? 'var(--danger)' : undefined }}
                    />
                    {hsrpError && <p style={{ color: 'var(--danger)', fontSize: '0.72rem', marginTop: '0.25rem' }}>{hsrpError}</p>}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Policy Number</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. POL-M-847291"
                    value={policyNumber}
                    onChange={(e) => setPolicyNumber(e.target.value.toUpperCase())}
                  />
                </div>

                <div className="flex gap-md">
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">Date Of Incident</label>
                    <input type="date" className="form-input" max={new Date().toISOString().split('T')[0]} value={incidentDate} onChange={(e) => setIncidentDate(e.target.value)} />
                  </div>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">Location Of Incident  </label>
                    <input type="text" className="form-input" placeholder="e.g. Pune" value={location} onChange={(e) => setLocation(e.target.value)} />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Brief Description</label>
                  <textarea className="form-input" rows={3} placeholder="I hit a pole while parking..." value={description} onChange={(e) => setDescription(e.target.value)} />
                </div>

                <div className="flex justify-end mt-4">
                  <button className="btn btn-primary" onClick={handleNext} disabled={!incidentDate || !vehicle || !description}>
                    Continue <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="flex flex-col gap-lg">
                <div>
                  <h2 className="text-xl mb-1">Driver Details</h2>
                  <p className="text-muted text-sm">Provide the driver's license number and a clear photo of the license card.</p>
                </div>

                {/* Upload Notice */}
                {uploadNotice && (
                  <div ref={noticeRef} style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.75rem 1rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: uploadNotice.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                    border: `1px solid ${uploadNotice.type === 'error' ? 'var(--danger)' : 'var(--warning, #f59e0b)'}`,
                    color: uploadNotice.type === 'error' ? 'var(--danger)' : 'var(--warning, #f59e0b)',
                    fontSize: '0.8125rem',
                    fontWeight: 500
                  }}>
                    <div className="flex items-center gap-xs">
                      <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                      <span>{uploadNotice.message}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setUploadNotice(null)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: '0.2rem' }}
                      title="Dismiss notice"
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}

                {/* Driver Name Input */}
                <div className="form-group">
                  <label className="form-label">
                    Driver Name <span style={{ color: 'var(--danger)' }}>*</span>
                  </label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Ramesh Kumar"
                    value={driverName}
                    onChange={(e) => setDriverName(e.target.value)}
                  />
                </div>

                {/* Driving License Number Input */}
                <div className="form-group">
                  <div className="flex justify-between items-center mb-1">
                    <label className="form-label" style={{ marginBottom: 0 }}>
                      Indian Driving License Number <span style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    {driverLicenseNumber && validateIndianDL(driverLicenseNumber) && (
                      <span className="flex items-center gap-xs text-xs font-semibold" style={{ color: 'var(--success, #10b981)' }}>
                        <CheckCircle2 size={14} /> Valid Format
                      </span>
                    )}
                  </div>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. MH14 20110012345 or DL0420110012345"
                    value={driverLicenseNumber}
                    maxLength={18}
                    onChange={(e) => {
                      const v = e.target.value.toUpperCase();
                      setDriverLicenseNumber(v);
                      if (dlError && validateIndianDL(v)) setDlError('');
                    }}
                    onBlur={() => {
                      if (driverLicenseNumber.trim() && !validateIndianDL(driverLicenseNumber)) {
                        setDlError('Invalid format. Indian Driving License must be 15 characters (e.g. MH14 20110012345 or MH1420110012345).');
                      } else {
                        setDlError('');
                      }
                    }}
                    style={{ borderColor: dlError ? 'var(--danger)' : undefined }}
                  />
                  {dlError ? (
                    <p style={{ color: 'var(--danger)', fontSize: '0.75rem', marginTop: '0.35rem' }}>{dlError}</p>
                  ) : (
                    <p className="text-muted" style={{ fontSize: '0.75rem', marginTop: '0.35rem' }}>
                      Standard 15-character format: 2 letters (State) + 2 digits (RTO) + 4 digits (Year) + 7 digits (License number).
                    </p>
                  )}
                </div>

                {/* Driving License Photo Upload */}
                <div className="form-group flex gap-md">
                  <div style={{ flex: 1 }}>
                    <label className="form-label mb-2">
                      License Front <span style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    {!driverLicenseFrontPhoto ? (
                      <div
                        style={{
                          border: '2px dashed var(--border-light)',
                          borderRadius: 'var(--radius-md)',
                          padding: '1.5rem',
                          textAlign: 'center',
                          backgroundColor: 'var(--bg-primary)',
                          position: 'relative',
                          cursor: 'pointer',
                          transition: 'border-color 0.2s, background-color 0.2s'
                        }}
                        className="hover:bg-tertiary"
                      >
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif"
                          onChange={(e) => handleDLPhotoUpload(e, 'front')}
                          style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%', height: '100%' }}
                        />
                        <div className="flex flex-col items-center gap-xs">
                          <FileText size={24} color="var(--accent-primary)" />
                          <span className="font-bold text-sm mt-1">Upload Front</span>
                        </div>
                      </div>
                    ) : (
                      <div
                        style={{
                          border: '1px solid var(--border-color)',
                          borderRadius: 'var(--radius-md)',
                          padding: '0.75rem',
                          backgroundColor: 'var(--bg-surface)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <div className="flex items-center gap-sm">
                          <img
                            src={driverLicenseFrontPhoto}
                            alt="Front"
                            style={{ width: '60px', height: '40px', objectFit: 'cover', borderRadius: 'var(--radius-sm)' }}
                          />
                          <span className="font-semibold text-xs">Front Uploaded</span>
                        </div>
                        <button type="button" onClick={() => setDriverLicenseFrontPhoto(null)} className="btn-ghost p-1 text-danger">
                          <X size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                  <div style={{ flex: 1 }}>
                    <label className="form-label mb-2">
                      License Back <span style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    {!driverLicenseBackPhoto ? (
                      <div
                        style={{
                          border: '2px dashed var(--border-light)',
                          borderRadius: 'var(--radius-md)',
                          padding: '1.5rem',
                          textAlign: 'center',
                          backgroundColor: 'var(--bg-primary)',
                          position: 'relative',
                          cursor: 'pointer',
                          transition: 'border-color 0.2s, background-color 0.2s'
                        }}
                        className="hover:bg-tertiary"
                      >
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif"
                          onChange={(e) => handleDLPhotoUpload(e, 'back')}
                          style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%', height: '100%' }}
                        />
                        <div className="flex flex-col items-center gap-xs">
                          <FileText size={24} color="var(--accent-primary)" />
                          <span className="font-bold text-sm mt-1">Upload Back</span>
                        </div>
                      </div>
                    ) : (
                      <div
                        style={{
                          border: '1px solid var(--border-color)',
                          borderRadius: 'var(--radius-md)',
                          padding: '0.75rem',
                          backgroundColor: 'var(--bg-surface)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <div className="flex items-center gap-sm">
                          <img
                            src={driverLicenseBackPhoto}
                            alt="Back"
                            style={{ width: '60px', height: '40px', objectFit: 'cover', borderRadius: 'var(--radius-sm)' }}
                          />
                          <span className="font-semibold text-xs">Back Uploaded</span>
                        </div>
                        <button type="button" onClick={() => setDriverLicenseBackPhoto(null)} className="btn-ghost p-1 text-danger">
                          <X size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Requirement Hint */}
                {(!driverName.trim() || !driverLicenseNumber.trim() || !validateIndianDL(driverLicenseNumber) || !driverLicenseFrontPhoto || !driverLicenseBackPhoto) && (
                  <div style={{
                    padding: '0.65rem 0.85rem',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--bg-tertiary)',
                    fontSize: '0.75rem',
                    color: 'var(--text-secondary)'
                  }}>
                    Driver name, valid Indian Driving License number, and both front & back photos are required.
                  </div>
                )}

                <div className="flex justify-between mt-4">
                  <button className="btn btn-secondary" onClick={handlePrev}>Back</button>
                  <button
                    className="btn btn-primary"
                    onClick={handleNext}
                    disabled={!driverName.trim() || !driverLicenseNumber.trim() || !validateIndianDL(driverLicenseNumber) || !driverLicenseFrontPhoto || !driverLicenseBackPhoto}
                  >
                    Continue <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="flex flex-col gap-lg">
                <div>
                  <h2 className="text-xl mb-1">Add Photos & Video</h2>
                  <p className="text-muted text-sm">Clear media helps our AI assess the vehicle damage immediately.</p>
                </div>

                {/* Upload Limit / Rate Limit Notice */}
                {uploadNotice && (
                  <div ref={noticeRef} style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.75rem 1rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: uploadNotice.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                    border: `1px solid ${uploadNotice.type === 'error' ? 'var(--danger)' : 'var(--warning, #f59e0b)'}`,
                    color: uploadNotice.type === 'error' ? 'var(--danger)' : 'var(--warning, #f59e0b)',
                    fontSize: '0.8125rem',
                    fontWeight: 500
                  }}>
                    <div className="flex items-center gap-xs">
                      <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                      <span>{uploadNotice.message}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setUploadNotice(null)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: '0.2rem' }}
                      title="Dismiss notice"
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}

                {/* Video 30-60s Guidance Alert */}
                <div style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.75rem',
                  padding: '0.875rem 1rem',
                  backgroundColor: 'var(--accent-dim)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border)'
                }}>
                  <Video size={20} color="var(--accent)" style={{ marginTop: '0.125rem', flexShrink: 0 }} />
                  <div style={{ fontSize: '0.8125rem', lineHeight: 1.5 }}>
                    <p style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.125rem' }}>
                      Video Requirement: 30–60 Second Walkaround
                    </p>
                    <p style={{ color: 'var(--text-secondary)' }}>
                      Please upload a <strong>30–60 second</strong> video walking around the vehicle (max {MAX_VIDEOS} videos). This helps our 3D AI models accurately assess deformation depth, normal vectors, and hidden damage.</p>
                    <p><strong>NOTE: Include Engine & Chasis Number in Videos.</strong>
                    </p>
                  </div>
                </div>

                {/* Photos Upload */}
                <div>
                  <div className="flex justify-between items-center" style={{ marginBottom: '0.5rem' }}>
                    <label className="form-label" style={{ marginBottom: 0 }}>
                      Vehicle Photos
                    </label>
                    <span
                      className="text-xs font-semibold px-2 py-0.5"
                      style={{
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: images.length >= MAX_IMAGES ? 'rgba(239, 68, 68, 0.15)' : 'var(--bg-tertiary)',
                        color: images.length >= MAX_IMAGES ? 'var(--danger)' : 'var(--text-secondary)'
                      }}
                    >
                      {images.length} / {MAX_IMAGES} max
                    </span>
                  </div>

                  {images.length < MAX_IMAGES ? (
                    <div style={{
                      border: '2px dashed var(--border-light)',
                      borderRadius: 'var(--radius-md)',
                      padding: '2.5rem 2rem',
                      textAlign: 'center',
                      backgroundColor: 'var(--bg-primary)',
                      position: 'relative',
                      transition: 'background-color 0.2s'
                    }} className="hover:bg-tertiary">
                      <input
                        type="file"
                        multiple
                        accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif"
                        onChange={handleImageUpload}
                        style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%', height: '100%' }}
                      />
                      <div className="flex flex-col items-center gap-sm">
                        <Upload size={28} color="var(--text-secondary)" />
                        <span className="font-bold text-base">Drop photos here</span>
                        <span className="text-xs text-muted">JPG, PNG, WEBP, or HEIC • {MAX_IMAGES - images.length} remaining (max {MAX_IMAGES})</span>
                      </div>
                    </div>
                  ) : (
                    <div style={{
                      border: '1px dashed var(--border)',
                      borderRadius: 'var(--radius-md)',
                      padding: '1.25rem',
                      textAlign: 'center',
                      backgroundColor: 'var(--bg-tertiary)',
                      color: 'var(--text-secondary)',
                      fontSize: '0.875rem'
                    }}>
                      Maximum photo limit reached ({MAX_IMAGES}/{MAX_IMAGES}). Remove a photo below to upload another.
                    </div>
                  )}

                  {images.length > 0 && (
                    <div className="flex gap-sm mt-3" style={{ flexWrap: 'wrap' }}>
                      {images.map((img, idx) => (
                        <div key={idx} style={{ position: 'relative', width: '80px', height: '80px', borderRadius: 'var(--radius-sm)', overflow: 'hidden', border: '1px solid var(--border-color)' }}>
                          <img src={img} alt={`Evidence ${idx + 1}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          <button
                            type="button"
                            onClick={() => removeImage(idx)}
                            style={{ position: 'absolute', top: 4, right: 4, backgroundColor: 'rgba(0,0,0,0.7)', borderRadius: '50%', padding: '0.25rem', color: 'white', border: 'none', cursor: 'pointer' }}
                            title="Remove photo"
                          >
                            <X size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Video Upload Section */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="form-label" style={{ marginBottom: 0 }}>
                      Walkaround Video (30–60 seconds)
                    </label>
                    <div className="flex items-center gap-xs">
                      <span className="text-xs text-muted">MP4, MOV, or WebM</span>
                      <span
                        className="text-xs font-semibold px-2 py-0.5"
                        style={{
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: videos.length >= MAX_VIDEOS ? 'rgba(239, 68, 68, 0.15)' : 'var(--bg-tertiary)',
                          color: videos.length >= MAX_VIDEOS ? 'var(--danger)' : 'var(--text-secondary)'
                        }}
                      >
                        {videos.length} / {MAX_VIDEOS} max
                      </span>
                    </div>
                  </div>

                  {videos.length < MAX_VIDEOS && (
                    <div style={{
                      border: '2px dashed var(--border-light)',
                      borderRadius: 'var(--radius-md)',
                      padding: '2rem 1.5rem',
                      textAlign: 'center',
                      backgroundColor: 'var(--bg-primary)',
                      position: 'relative',
                      transition: 'background-color 0.2s',
                      marginBottom: videos.length > 0 ? '1rem' : 0
                    }} className="hover:bg-tertiary">
                      <input
                        type="file"
                        accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
                        multiple={videos.length === 0}
                        onChange={handleVideoUpload}
                        style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%', height: '100%' }}
                      />
                      <div className="flex flex-col items-center gap-xs">
                        <Video size={28} color="var(--accent)" />
                        <span className="font-bold text-base">
                          {videos.length === 0 ? 'Upload 30–60s Video' : 'Add Another Video'}
                        </span>
                        <span className="text-xs text-muted">
                          MP4, MOV, or WebM • {MAX_VIDEOS - videos.length} remaining (max {MAX_VIDEOS})
                        </span>
                      </div>
                    </div>
                  )}

                  {videos.length > 0 && (
                    <div className="flex flex-col gap-sm">
                      <div style={{ display: 'grid', gridTemplateColumns: videos.length > 1 ? 'repeat(auto-fit, minmax(280px, 1fr))' : '1fr', gap: '0.75rem' }}>
                        {videos.map((v) => (
                          <div
                            key={v.id}
                            style={{
                              borderRadius: 'var(--radius-md)',
                              overflow: 'hidden',
                              border: '1px solid var(--border)',
                              backgroundColor: '#000'
                            }}
                          >
                            <video src={v.url} controls style={{ width: '100%', maxHeight: '200px', display: 'block' }} />
                            <div style={{ padding: '0.5rem 0.75rem', backgroundColor: 'var(--bg-surface)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border)' }}>
                              <div className="flex items-center gap-xs" style={{ minWidth: 0 }}>
                                <Video size={14} color="var(--accent)" style={{ flexShrink: 0 }} />
                                <span className="text-xs font-medium" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {v.name || 'Walkaround Video (30-60s)'}
                                </span>
                              </div>
                              <button
                                type="button"
                                onClick={() => removeVideo(v.id)}
                                className="btn-ghost"
                                style={{ padding: '0.2rem', color: 'var(--danger)', cursor: 'pointer' }}
                                title="Remove video"
                              >
                                <X size={14} />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                      {videos.length >= MAX_VIDEOS && (
                        <div style={{
                          border: '1px dashed var(--border)',
                          borderRadius: 'var(--radius-md)',
                          padding: '1rem',
                          textAlign: 'center',
                          backgroundColor: 'var(--bg-tertiary)',
                          color: 'var(--text-secondary)',
                          fontSize: '0.8125rem'
                        }}>
                          Maximum video limit reached ({MAX_VIDEOS}/{MAX_VIDEOS}). Remove a video above to upload another.
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex justify-between mt-4">
                  <button className="btn btn-secondary" onClick={handlePrev}>Back</button>
                  <button className="btn btn-primary" onClick={handleNext} disabled={images.length === 0 && videos.length === 0}>
                    Review Claim <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="flex flex-col gap-lg">
                <div>
                  <h2 className="text-xl mb-1">Review Details</h2>
                  <p className="text-muted text-sm">Please verify the information before submitting.</p>
                </div>

                <div style={{ backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                  <div className="p-md" style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <h4 className="text-sm text-muted uppercase font-bold mb-4">Incident & Vehicle</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '0.75rem', fontSize: '0.875rem' }}>
                      <span className="text-muted">Type</span> <span className="font-medium">{claimType}</span>
                      <span className="text-muted">Vehicle</span> <span className="font-medium">{vehicle}</span>
                      {policyNumber && <><span className="text-muted">Policy No</span> <span className="font-medium">{policyNumber}</span></>}
                      {hsrpNumber && <><span className="text-muted">HSRP / Reg</span> <span className="font-medium">{hsrpNumber}</span></>}
                      {engineNumber && <><span className="text-muted">Engine No</span> <span className="font-medium">{engineNumber}</span></>}
                      {chassisNumber && <><span className="text-muted">Chassis No</span> <span className="font-medium">{chassisNumber}</span></>}
                      <span className="text-muted">Date</span> <span>{incidentDate}</span>
                      <span className="text-muted">Location</span> <span>{location}</span>
                      <span className="text-muted">Details</span> <span>{description}</span>
                    </div>
                  </div>

                  <div className="p-md" style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <h4 className="text-sm text-muted uppercase font-bold mb-4">Driver Details</h4>
                    <div className="flex items-center justify-between gap-md" style={{ flexWrap: 'wrap' }}>
                      <div>
                        <div className="text-xs text-muted mb-1">Driver Name</div>
                        <div className="font-semibold text-base mb-2">{driverName}</div>
                        <div className="text-xs text-muted mb-1">Driving License Number</div>
                        <div className="font-semibold text-base" style={{ letterSpacing: '0.5px' }}>{driverLicenseNumber}</div>
                        <div className="flex items-center gap-xs mt-1 text-xs" style={{ color: 'var(--success, #10b981)' }}>
                          <CheckCircle2 size={13} /> Verified Indian DL Format
                        </div>
                      </div>
                      <div className="flex gap-sm">
                        {driverLicenseFrontPhoto && (
                          <div className="flex flex-col items-center gap-xs">
                            <img
                              src={driverLicenseFrontPhoto}
                              alt="Front"
                              style={{ width: '80px', height: '52px', objectFit: 'cover', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}
                            />
                            <span className="text-xs text-muted">Front</span>
                          </div>
                        )}
                        {driverLicenseBackPhoto && (
                          <div className="flex flex-col items-center gap-xs">
                            <img
                              src={driverLicenseBackPhoto}
                              alt="Back"
                              style={{ width: '80px', height: '52px', objectFit: 'cover', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}
                            />
                            <span className="text-xs text-muted">Back</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="p-md">
                    <h4 className="text-sm text-muted uppercase font-bold mb-4">Evidence</h4>
                    <div className="flex flex-col gap-sm">
                      <div className="flex items-center gap-sm" style={{ flexWrap: 'wrap' }}>
                        {images.map((img, idx) => (
                          <img key={idx} src={img} alt={`Evidence ${idx + 1}`} style={{ width: '60px', height: '60px', objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                        ))}
                        <span className="text-sm text-muted ml-2">{images.length} photo{images.length !== 1 ? 's' : ''} attached</span>
                      </div>

                      {videos.length > 0 && (
                        <div className="flex flex-col gap-xs mt-1">
                          {videos.map((v) => (
                            <div key={v.id} className="flex items-center gap-sm p-2" style={{ backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', maxWidth: '360px' }}>
                              <Video size={16} color="var(--accent)" style={{ flexShrink: 0 }} />
                              <span className="text-xs font-medium" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {v.name || 'Walkaround Video'}
                              </span>
                              <span className="badge badge-success text-xs">30–60s Video</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex justify-between mt-4">
                  <button className="btn btn-secondary" onClick={handlePrev} disabled={loading}>Back</button>
                  <button className="btn btn-success" onClick={handleSubmit} disabled={loading}>
                    {loading ? 'Submitting...' : 'Submit Claim'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};
