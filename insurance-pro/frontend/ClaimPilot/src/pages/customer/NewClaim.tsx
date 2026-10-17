import { useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { claimsApi, storageApi } from '../../services/claimsApi';
import { Card } from '../../components/ui/Card';
import { Upload, X, ChevronRight, Car, AlertTriangle, Flame, CloudLightning, Video, FileText, CheckCircle2, Loader2 } from 'lucide-react';
import { useGSAP, animateStep, animateFadeIn } from '../../lib/gsap';
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile } from '@ffmpeg/util';

type Step = 1 | 2 | 3 | 4;

const ffmpeg = new FFmpeg();

const MAX_IMAGES = 10;
const MAX_VIDEOS = 2;
const UPLOAD_COOLDOWN_MS = 500;
// TODO: Add an image file-size limit once the upload limit is defined.

const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp'];

const ALLOWED_VIDEO_TYPES = ['video/mp4', 'video/quicktime'];
const ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.mov'];

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

const HSRP_REGEX = /^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$/;
const validateHSRP = (v: string) => !v || HSRP_REGEX.test(v.toUpperCase());

const validateIndianDL = (dl: string): boolean => {
  if (!dl) return false;
  const clean = dl.replace(/[-\s]/g, '').toUpperCase();
  return /^[A-Z]{2}[0-9]{2}(?:19|20)[0-9]{2}[0-9]{7}$/.test(clean);
};

interface LocalImage {
  file: File;
  previewUrl: string;
}

interface UploadedVideo {
  id: string;
  file: File;
  previewUrl: string;
  name: string;
}

interface EvidenceCatalogItem {
  id: string;
  fileName: string;
  file_url: string;
  storage_path: string;
  file_type: string;
  category: 'photo' | 'walkaround_video' | 'dl_front' | 'dl_back';
}

interface PendingSubmission {
  claimId: string;
  routeClaimId: string;
  evidence: EvidenceCatalogItem[];
  registeredEvidenceIds: string[];
}

export const NewClaim = () => {
  const navigate = useNavigate();
  const routerLocation = useLocation();
  const params = new URLSearchParams(routerLocation.search);
  const initialType = params.get('type') || 'Accident';

  const [step, setStep] = useState<Step>(1);
  const [loading, setLoading] = useState(false);
  const [submissionStatus, setSubmissionStatus] = useState<'idle' | 'analyzing' | 'submitted'>('idle');
  const [isCompressing, setIsCompressing] = useState(false);
  const [pendingSubmission, setPendingSubmission] = useState<PendingSubmission | null>(null);
  const [catalogErrors, setCatalogErrors] = useState<Record<string, string>>({});
  const [retryingEvidenceId, setRetryingEvidenceId] = useState<string | null>(null);
  const submissionStartedRef = useRef(false);
  const claimCreatedRef = useRef(false);
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

  // Store raw binary Files alongside string preview URLs
  const [driverLicenseFrontFile, setDriverLicenseFrontFile] = useState<File | null>(null);
  const [driverLicenseFrontPhoto, setDriverLicenseFrontPhoto] = useState<string | null>(null);

  const [driverLicenseBackFile, setDriverLicenseBackFile] = useState<File | null>(null);
  const [driverLicenseBackPhoto, setDriverLicenseBackPhoto] = useState<string | null>(null);

  const [description, setDescription] = useState('');
  const [images, setImages] = useState<LocalImage[]>([]);
  const [videos, setVideos] = useState<UploadedVideo[]>([]);
  const [uploadNotice, setUploadNotice] = useState<{ type: 'warning' | 'error' | 'success'; message: string } | null>(null);
  const lastUploadTimestamp = useRef<number>(0);

  const [hsrpError, setHsrpError] = useState('');
  const [dlError, setDlError] = useState('');
  const [policyError, setPolicyError] = useState('');

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

  const downscaleImage = async (file: File): Promise<File> => {
    if (!file.type.startsWith('image/')) return file;
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
    if (scale === 1) {
      bitmap.close();
      return file;
    }
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.88));
    return blob ? new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), { type: 'image/jpeg', lastModified: file.lastModified }) : file;
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
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
        message: 'Unsupported format. Only JPG, PNG, and WEBP images are accepted.'
      });
      e.target.value = '';
      return;
    }

    const filesToUpload = validFiles.slice(0, availableSlots);

    if (invalidCount > 0 && validFiles.length > availableSlots) {
      setUploadNotice({
        type: 'warning',
        message: `${invalidCount} invalid file${invalidCount > 1 ? 's' : ''} rejected. Added ${filesToUpload.length} photo${filesToUpload.length > 1 ? 's' : ''} (max ${MAX_IMAGES} reached).`
      });
    } else if (invalidCount > 0) {
      setUploadNotice({
        type: 'warning',
        message: `${invalidCount} unsupported file${invalidCount > 1 ? 's' : ''} rejected.`
      });
    } else if (validFiles.length > availableSlots) {
      setUploadNotice({
        type: 'warning',
        message: `Upload limit reached: Added ${filesToUpload.length} photo(s).`
      });
    } else {
      setUploadNotice(null);
    }

    const newImages: LocalImage[] = [];
    for (const file of filesToUpload) {
      const previewFile = await downscaleImage(file);
      newImages.push({ file: previewFile, previewUrl: URL.createObjectURL(previewFile) });
    }

    setImages(prev => [...prev, ...newImages]);
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
        message: 'Unsupported format. Only MP4 and MOV videos are accepted.'
      });
      e.target.value = '';
      return;
    }

    const filesToUpload = validFiles.slice(0, availableSlots);

    if (invalidCount > 0) {
      setUploadNotice({
        type: 'warning',
        message: `${invalidCount} non-video file${invalidCount > 1 ? 's' : ''} rejected.`
      });
    } else {
      setUploadNotice(null);
    }

    setIsCompressing(true);

    const compressVideos = async () => {
      try {
        if (!ffmpeg.loaded) {
          await ffmpeg.load();
        }

        const newVideos: UploadedVideo[] = [];

        for (let i = 0; i < filesToUpload.length; i++) {
          const file = filesToUpload[i];
          const inputName = `input-${i}-${file.name.replace(/[^a-zA-Z0-9.]/g, '')}`;
          const outputName = `output-${i}.mp4`;

          await ffmpeg.writeFile(inputName, await fetchFile(file));

          await ffmpeg.exec([
            '-i', inputName,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '28',
            '-vf', 'scale=-2:720',
            '-c:a', 'aac',
            outputName
          ]);

          const data = await ffmpeg.readFile(outputName);
          const blob = new Blob([data as any], { type: 'video/mp4' });
          const compressedFile = new File([blob], file.name.replace(/\.[^/.]+$/, "") + ".mp4", { type: 'video/mp4' });

          newVideos.push({
            id: `${Date.now()}-${i}-${Math.random().toString(36).slice(2, 7)}`,
            file: compressedFile,
            previewUrl: URL.createObjectURL(blob),
            name: file.name
          });
        }

        setVideos(prev => [...prev, ...newVideos]);
      } catch (error) {
        console.error("Compression error, falling back to original file:", error);
        const newVideos: UploadedVideo[] = filesToUpload.map((file, i) => ({
          id: `${Date.now()}-${i}-${Math.random().toString(36).slice(2, 7)}`,
          file,
          previewUrl: URL.createObjectURL(file),
          name: file.name
        }));
        setVideos(prev => [...prev, ...newVideos]);
      } finally {
        setIsCompressing(false);
      }
    };

    compressVideos();
    e.target.value = '';
  };

  const removeVideo = (id: string) => {
    setVideos(prev => prev.filter(v => v.id !== id));
    setUploadNotice(null);
  };

  const handleDLPhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>, side: 'front' | 'back') => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!isValidImageFile(file)) {
      setUploadNotice({
        type: 'error',
        message: 'Unsupported format. Please upload a JPG, PNG, or WEBP image.'
      });
      e.target.value = '';
      return;
    }

    const processedFile = await downscaleImage(file);
    const previewUrl = URL.createObjectURL(processedFile);
    if (side === 'front') {
      setDriverLicenseFrontFile(processedFile);
      setDriverLicenseFrontPhoto(previewUrl);
    } else {
      setDriverLicenseBackFile(processedFile);
      setDriverLicenseBackPhoto(previewUrl);
    }
    setUploadNotice(null);
    e.target.value = '';
  };

  const isUnauthorizedError = (error: any): boolean =>
    error?.status === 401 || error?.statusCode === 401 || error?.message === 'Unauthorized';

  const catalogEvidenceForClaim = async (claimId: string, item: EvidenceCatalogItem) =>
    storageApi.catalogEvidence({
      claim_id: claimId,
      file_url: item.file_url,
      storage_path: item.storage_path,
      file_type: item.file_type,
      category: item.category
    });

  const finishSubmission = (submission: PendingSubmission) => {
    const allEvidenceRegistered = submission.evidence.length > 0 && submission.evidence.every(
      (item) => submission.registeredEvidenceIds.includes(item.id)
    );
    if (!allEvidenceRegistered) {
      setLoading(false);
      setSubmissionStatus('idle');
      setUploadNotice({
        type: 'error',
        message: 'Evidence is not fully registered yet. Retry each file marked with an error before continuing.'
      });
      return;
    }

    const hasRegisteredPhoto = submission.evidence.some(
      (item) => item.category === 'photo' && submission.registeredEvidenceIds.includes(item.id)
    );
    setLoading(false);
    setSubmissionStatus(hasRegisteredPhoto ? 'analyzing' : 'submitted');
    setUploadNotice({
      type: 'success',
      message: hasRegisteredPhoto
        ? 'Claim created and evidence registered. Damage analysis has been queued for the vehicle photos.'
        : 'Claim created and evidence registered. Damage analysis was not started because no vehicle photo was registered.'
    });

    setClaimType('Accident');
    setPolicyNumber('');
    setIncidentDate('');
    setLocation('');
    setVehicle('');
    setEngineNumber('');
    setChassisNumber('');
    setHsrpNumber('');
    setDriverName('');
    setDriverLicenseNumber('');
    setDriverLicenseFrontFile(null);
    setDriverLicenseFrontPhoto(null);
    setDriverLicenseBackFile(null);
    setDriverLicenseBackPhoto(null);
    setDescription('');
    setImages([]);
    setVideos([]);

    setTimeout(() => navigate(`/customer/claims/${submission.routeClaimId}`), 1000);
  };

  const retryEvidenceCatalog = async (evidenceId: string) => {
    const submission = pendingSubmission;
    const item = submission?.evidence.find((evidence) => evidence.id === evidenceId);
    if (!submission || !item || loading || submissionStartedRef.current === false) return;

    setLoading(true);
    setRetryingEvidenceId(evidenceId);
    try {
      await catalogEvidenceForClaim(submission.claimId, item);
    } catch (error: any) {
      setLoading(false);
      setRetryingEvidenceId(null);
      if (isUnauthorizedError(error)) {
        navigate('/login', { replace: true });
        return;
      }
      setCatalogErrors((current) => ({
        ...current,
        [item.id]: 'Could not register this file. Retry to continue.'
      }));
      setUploadNotice({
        type: 'error',
        message: `Evidence for ${item.fileName} could not be registered. Retry this file to finish submission.`
      });
      return;
    }

    const registeredEvidenceIds = Array.from(new Set([...submission.registeredEvidenceIds, item.id]));
    const updatedSubmission = { ...submission, registeredEvidenceIds };
    const remainingErrors = { ...catalogErrors };
    delete remainingErrors[item.id];
    setPendingSubmission(updatedSubmission);
    setCatalogErrors(remainingErrors);
    setLoading(false);
    setRetryingEvidenceId(null);

    if (Object.keys(remainingErrors).length === 0) finishSubmission(updatedSubmission);
  };

  const handleSubmit = async () => {
    if (submissionStartedRef.current || pendingSubmission) return;
    submissionStartedRef.current = true;
    claimCreatedRef.current = false;
    setLoading(true);
    setSubmissionStatus('idle');
    setCatalogErrors({});

    try {
      const uploadedImages: { public_url: string; file_path: string; name: string; file_type: string }[] = [];
      const uploadedVideos: { public_url: string; file_path: string; name: string; file_type: string }[] = [];
      let dlFrontResult: { public_url: string; file_path: string } | undefined = undefined;
      let dlBackResult: { public_url: string; file_path: string } | undefined = undefined;

      // Upload license files first, then vehicle photos and walkaround videos.
      if (driverLicenseFrontFile) {
        const res = await storageApi.uploadFile(driverLicenseFrontFile, 'dl_front');
        if (res?.public_url && res?.file_path) dlFrontResult = res;
      }
      if (driverLicenseBackFile) {
        const res = await storageApi.uploadFile(driverLicenseBackFile, 'dl_back');
        if (res?.public_url && res?.file_path) dlBackResult = res;
      }

      for (const imgItem of images) {
        const res = await storageApi.uploadFile(imgItem.file, 'photo');
        if (res?.public_url && res?.file_path) {
          uploadedImages.push({ public_url: res.public_url, file_path: res.file_path, name: imgItem.file.name, file_type: imgItem.file.type || 'image/jpeg' });
        }
      }

      for (const vidItem of videos) {
        const res = await storageApi.uploadFile(vidItem.file, 'walkaround_video');
        if (res?.public_url && res?.file_path) {
          uploadedVideos.push({ public_url: res.public_url, file_path: res.file_path, name: vidItem.name, file_type: vidItem.file.type || 'video/mp4' });
        }
      }

      if (
        uploadedImages.length !== images.length ||
        uploadedVideos.length !== videos.length ||
        uploadedImages.length + uploadedVideos.length === 0
      ) {
        throw new Error('One or more vehicle evidence uploads did not return a usable file URL. Please retry submission.');
      }

      const newClaim = await claimsApi.createClaim({
        claimType,
        policyNumber: policyNumber ? policyNumber.trim().toUpperCase() : undefined,
        incidentDate,
        location,
        vehicle,
        engineNumber: engineNumber || undefined,
        chassisNumber: chassisNumber || undefined,
        hsrpNumber: hsrpNumber || undefined,
        driverName: driverName || undefined,
        driverLicenseNumber: driverLicenseNumber ? driverLicenseNumber.replace(/[-\s]/g, '').toUpperCase() : undefined,
        driverLicenseFrontPhoto: dlFrontResult?.public_url || driverLicenseFrontPhoto || undefined,
        driverLicenseBackPhoto: dlBackResult?.public_url || driverLicenseBackPhoto || undefined,
        description,
        images: uploadedImages.map((img) => img.public_url),
        video: uploadedVideos[0]?.public_url || undefined,
        videos: uploadedVideos.map((vid) => vid.public_url)
      });
      claimCreatedRef.current = true;

      const claimIdForStorage = (newClaim as any).backendId || newClaim.id;
      const evidence: EvidenceCatalogItem[] = [
        ...(dlFrontResult ? [{
          id: 'dl-front',
          fileName: driverLicenseFrontFile?.name || 'Driver_License_Front.jpg',
          file_url: dlFrontResult.public_url,
          storage_path: dlFrontResult.file_path,
          file_type: driverLicenseFrontFile?.type || 'image/jpeg',
          category: 'dl_front' as const
        }] : []),
        ...(dlBackResult ? [{
          id: 'dl-back',
          fileName: driverLicenseBackFile?.name || 'Driver_License_Back.jpg',
          file_url: dlBackResult.public_url,
          storage_path: dlBackResult.file_path,
          file_type: driverLicenseBackFile?.type || 'image/jpeg',
          category: 'dl_back' as const
        }] : []),
        ...uploadedImages.map((img, index) => ({
          id: `photo-${index}`,
          fileName: img.name || `Photo ${index + 1}`,
          file_url: img.public_url,
          storage_path: img.file_path,
          file_type: img.file_type,
          category: 'photo' as const
        })),
        ...uploadedVideos.map((vid, index) => ({
          id: `video-${index}`,
          fileName: vid.name || `Video ${index + 1}`,
          file_url: vid.public_url,
          storage_path: vid.file_path,
          file_type: vid.file_type,
          category: 'walkaround_video' as const
        }))
      ];
      const submission: PendingSubmission = {
        claimId: claimIdForStorage,
        routeClaimId: newClaim.id,
        evidence,
        registeredEvidenceIds: []
      };
      setPendingSubmission(submission);

      const registeredEvidenceIds: string[] = [];
      const failedEvidence: Record<string, string> = {};
      for (const item of evidence) {
        try {
          await catalogEvidenceForClaim(submission.claimId, item);
          registeredEvidenceIds.push(item.id);
        } catch (error: any) {
          if (isUnauthorizedError(error)) {
            setLoading(false);
            navigate('/login', { replace: true });
            return;
          }
          failedEvidence[item.id] = 'Could not register this file. Retry to continue.';
        }
      }

      const updatedSubmission = { ...submission, registeredEvidenceIds };
      setPendingSubmission(updatedSubmission);
      setCatalogErrors(failedEvidence);
      if (Object.keys(failedEvidence).length > 0) {
        setLoading(false);
        setSubmissionStatus('idle');
        setUploadNotice({
          type: 'error',
          message: 'Some evidence could not be registered. Retry each file marked with an error; your claim will not be submitted again.'
        });
        return;
      }

      finishSubmission(updatedSubmission);
    } catch (error: any) {
      setLoading(false);
      setSubmissionStatus('idle');
      if (!claimCreatedRef.current) submissionStartedRef.current = false;
      if (isUnauthorizedError(error)) {
        navigate('/login', { replace: true });
        return;
      }
      setUploadNotice({
        type: 'error',
        message: error?.message || 'An error occurred while submitting your claim.'
      });
    }
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
                  <input type="text" className="form-input" placeholder="e.g. Honda City" value={vehicle} onChange={(e) => setVehicle(e.target.value)} />
                </div>

                <div className="flex gap-md" style={{ flexWrap: 'wrap' }}>
                  <div className="form-group" style={{ flex: 1, minWidth: '180px' }}>
                    <label className="form-label">Engine Number</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Enter last 6 digits"
                      value={engineNumber}
                      onChange={(e) => setEngineNumber(e.target.value.toUpperCase())}
                    />
                  </div>

                  <div className="form-group" style={{ flex: 1, minWidth: '180px' }}>
                    <label className="form-label">Chassis Number</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Enter last 6 digits"
                      value={chassisNumber}
                      onChange={(e) => setChassisNumber(e.target.value.toUpperCase())}
                    />
                  </div>

                  <div className="form-group" style={{ flex: 1, minWidth: '180px' }}>
                    <label className="form-label">HSRP / Reg. Number</label>
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
                    onChange={(e) => {
                      setPolicyNumber(e.target.value.toUpperCase());
                      if (policyError) setPolicyError('');
                    }}
                    onBlur={() => {
                      if (!policyNumber.trim()) setPolicyError('Policy Number is required');
                    }}
                    style={{ borderColor: policyError ? 'var(--danger)' : undefined }}
                  />
                  {policyError && <p style={{ color: 'var(--danger)', fontSize: '0.72rem', marginTop: '0.25rem' }}>{policyError}</p>}
                </div>

                <div className="flex gap-md">
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">Date Of Incident</label>
                    <input type="date" className="form-input" max={new Date().toISOString().split('T')[0]} value={incidentDate} onChange={(e) => setIncidentDate(e.target.value)} />
                  </div>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label">Location Of Incident</label>
                    <input type="text" className="form-input" placeholder="e.g. Pune" value={location} onChange={(e) => setLocation(e.target.value)} />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Brief Description</label>
                  <textarea className="form-input" rows={3} placeholder="I hit a pole while parking..." value={description} onChange={(e) => setDescription(e.target.value)} />
                </div>

                <div className="flex justify-end mt-4">
                  <button className="btn btn-primary" onClick={() => {
                    if (!policyNumber.trim()) {
                      setPolicyError('Policy Number is required');
                      return;
                    }
                    handleNext();
                  }} disabled={!incidentDate || !vehicle || !description}>
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
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}

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
                        setDlError('Invalid format. Indian Driving License must be 15 characters (e.g. MH14 20110012345).');
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

                <div className="form-group flex gap-md">
                  <div style={{ flex: 1 }}>
                    <label className="form-label mb-2">License Front <span style={{ color: 'var(--danger)' }}>*</span></label>
                    {!driverLicenseFrontPhoto ? (
                      <div
                        style={{
                          border: '2px dashed var(--border-light)',
                          borderRadius: 'var(--radius-md)',
                          padding: '1.5rem',
                          textAlign: 'center',
                          backgroundColor: 'var(--bg-primary)',
                          position: 'relative',
                          cursor: 'pointer'
                        }}
                        className="hover:bg-tertiary"
                      >
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
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
                        <button type="button" onClick={() => { setDriverLicenseFrontPhoto(null); setDriverLicenseFrontFile(null); }} className="btn-ghost p-1 text-danger">
                          <X size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                  <div style={{ flex: 1 }}>
                    <label className="form-label mb-2">License Back <span style={{ color: 'var(--danger)' }}>*</span></label>
                    {!driverLicenseBackPhoto ? (
                      <div
                        style={{
                          border: '2px dashed var(--border-light)',
                          borderRadius: 'var(--radius-md)',
                          padding: '1.5rem',
                          textAlign: 'center',
                          backgroundColor: 'var(--bg-primary)',
                          position: 'relative',
                          cursor: 'pointer'
                        }}
                        className="hover:bg-tertiary"
                      >
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
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
                        <button type="button" onClick={() => { setDriverLicenseBackPhoto(null); setDriverLicenseBackFile(null); }} className="btn-ghost p-1 text-danger">
                          <X size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {(!driverName.trim() || !driverLicenseNumber.trim() || !validateIndianDL(driverLicenseNumber) || !driverLicenseFrontPhoto || !driverLicenseBackPhoto) && (
                  <div style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
                    Driver name, a valid Indian driving license number, and both license photos are required to continue.
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
                  <p className="text-muted text-sm">Clear, well-lit evidence photos help assess visible vehicle damage.</p>
                </div>

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
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}

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
                      Please upload a <strong>30–60 second</strong> video walking around the vehicle. Automated damage analysis starts after vehicle photo evidence is registered.
                    </p>
                  </div>
                </div>

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
                      position: 'relative'
                    }} className="hover:bg-tertiary">
                      <input
                        type="file"
                        multiple
                        accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                        onChange={handleImageUpload}
                        style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%', height: '100%' }}
                      />
                      <div className="flex flex-col items-center gap-sm">
                        <Upload size={28} color="var(--text-secondary)" />
                        <span className="font-bold text-base">Drop photos here</span>
                        <span className="text-xs text-muted">JPG, PNG, or WEBP • {MAX_IMAGES - images.length} remaining (max {MAX_IMAGES})</span>
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
                          <img src={img.previewUrl} alt={`Evidence ${idx + 1}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
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

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="form-label" style={{ marginBottom: 0 }}>
                      Walkaround Video (30–60 seconds)
                    </label>
                    <div className="flex items-center gap-xs">
                      <span className="text-xs text-muted">MP4 or MOV</span>
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
                        accept="video/mp4,video/quicktime,.mp4,.mov"
                        multiple={videos.length === 0}
                        onChange={handleVideoUpload}
                        disabled={isCompressing}
                        style={{ position: 'absolute', inset: 0, opacity: 0, cursor: isCompressing ? 'not-allowed' : 'pointer', width: '100%', height: '100%' }}
                      />
                      <div className="flex flex-col items-center gap-xs">
                        {isCompressing ? (
                          <>
                            <Loader2 size={28} className="animate-spin" color="var(--accent)" />
                            <span className="font-bold text-base mt-1">Optimizing video...</span>
                            <span className="text-xs text-muted">Please wait while FFmpeg processes your file</span>
                          </>
                        ) : (
                          <>
                            <Video size={28} color="var(--accent)" />
                            <span className="font-bold text-base">
                              {videos.length === 0 ? 'Upload 30–60s Video' : 'Add Another Video'}
                            </span>
                            <span className="text-xs text-muted">
                              MP4 or MOV • {MAX_VIDEOS - videos.length} remaining (max {MAX_VIDEOS})
                            </span>
                          </>
                        )}
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
                            <video src={v.previewUrl} controls style={{ width: '100%', maxHeight: '200px', display: 'block' }} />
                            <div style={{ padding: '0.5rem 0.75rem', backgroundColor: 'var(--bg-surface)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border)' }}>
                              <div className="flex items-center gap-xs" style={{ minWidth: 0 }}>
                                <Video size={14} color="var(--accent)" style={{ flexShrink: 0 }} />
                                <span className="text-xs font-medium" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {v.name}
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
                  <button className="btn btn-secondary" onClick={handlePrev} disabled={isCompressing}>Back</button>
                  <button className="btn btn-primary" onClick={handleNext} disabled={isCompressing || (images.length === 0 && videos.length === 0)}>
                    {isCompressing ? (
                      <span className="flex items-center gap-xs">
                        <Loader2 size={16} className="animate-spin" />
                        Processing...
                      </span>
                    ) : (
                      <>
                        Review Claim <ChevronRight size={16} />
                      </>
                    )}
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

                {submissionStatus === 'analyzing' && (
                  <div role="status" style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--accent-primary)', color: 'var(--accent-primary)', backgroundColor: 'var(--accent-dim)' }}>
                    Vehicle photo evidence is registered. Damage analysis has been queued in the background.
                  </div>
                )}
                {submissionStatus === 'submitted' && (
                  <div role="status" style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', color: 'var(--text-secondary)', backgroundColor: 'var(--bg-tertiary)' }}>
                    Evidence is registered. No vehicle photo was registered, so damage analysis was not started and the claim remains pending review.
                  </div>
                )}

                {pendingSubmission && (
                  <div className="flex flex-col gap-sm p-md" style={{ borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', backgroundColor: 'var(--bg-primary)' }}>
                    <h3 className="text-sm font-bold">Evidence registration</h3>
                    {pendingSubmission.evidence.map((item) => {
                      const isRegistered = pendingSubmission.registeredEvidenceIds.includes(item.id);
                      const itemError = catalogErrors[item.id];
                      return (
                        <div key={item.id} className="flex items-start justify-between gap-md p-2" style={{ borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface)' }}>
                          <div className="flex items-start gap-sm" style={{ minWidth: 0 }}>
                            {itemError ? (
                              <AlertTriangle size={16} color="var(--danger)" style={{ flexShrink: 0, marginTop: '0.1rem' }} />
                            ) : isRegistered ? (
                              <CheckCircle2 size={16} color="var(--success, #10b981)" style={{ flexShrink: 0, marginTop: '0.1rem' }} />
                            ) : (
                              <Loader2 size={16} className="animate-spin" color="var(--accent-primary)" style={{ flexShrink: 0, marginTop: '0.1rem' }} />
                            )}
                            <div style={{ minWidth: 0 }}>
                              <div className="text-sm font-medium" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.fileName}</div>
                              <div className="text-xs text-muted">
                                {itemError ? itemError : isRegistered ? 'Registered' : 'Registering evidence...'}
                              </div>
                            </div>
                          </div>
                          {itemError && (
                            <button
                              type="button"
                              className="btn btn-secondary"
                              onClick={() => retryEvidenceCatalog(item.id)}
                              disabled={loading}
                            >
                              {retryingEvidenceId === item.id ? (
                                <span className="flex items-center gap-xs"><Loader2 size={14} className="animate-spin" /> Retrying...</span>
                              ) : 'Retry'}
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {uploadNotice && (
                  <div ref={noticeRef} style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.75rem 1rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: uploadNotice.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : uploadNotice.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                    border: `1px solid ${uploadNotice.type === 'error' ? 'var(--danger)' : uploadNotice.type === 'success' ? 'var(--success, #10b981)' : 'var(--warning, #f59e0b)'}`,
                    color: uploadNotice.type === 'error' ? 'var(--danger)' : uploadNotice.type === 'success' ? 'var(--success, #10b981)' : 'var(--warning, #f59e0b)',
                    fontSize: '0.8125rem',
                    fontWeight: 500
                  }}>
                    <div className="flex items-center gap-xs">
                      {uploadNotice.type === 'success' ? <CheckCircle2 size={16} style={{ flexShrink: 0 }} /> : <AlertTriangle size={16} style={{ flexShrink: 0 }} />}
                      <span>{uploadNotice.message}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setUploadNotice(null)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: '0.2rem' }}
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}

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
                            <img src={driverLicenseFrontPhoto} alt="Front" style={{ width: '80px', height: '52px', objectFit: 'cover', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }} />
                            <span className="text-xs text-muted">Front</span>
                          </div>
                        )}
                        {driverLicenseBackPhoto && (
                          <div className="flex flex-col items-center gap-xs">
                            <img src={driverLicenseBackPhoto} alt="Back" style={{ width: '80px', height: '52px', objectFit: 'cover', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }} />
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
                          <img key={idx} src={img.previewUrl} alt={`Evidence ${idx + 1}`} style={{ width: '60px', height: '60px', objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                        ))}
                        <span className="text-sm text-muted ml-2">{images.length} photo{images.length !== 1 ? 's' : ''} attached</span>
                      </div>
                      {videos.length > 0 && (
                        <div className="flex flex-col gap-xs mt-1">
                          {videos.map((video) => (
                            <div key={video.id} className="flex items-center gap-sm p-2" style={{ backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', maxWidth: '360px' }}>
                              <Video size={16} color="var(--accent)" style={{ flexShrink: 0 }} />
                              <span className="text-xs font-medium" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {video.name}
                              </span>
                              <span className="badge badge-success text-xs">Attached</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex justify-between mt-4">
                  <button className="btn btn-secondary" onClick={handlePrev} disabled={loading || isCompressing || Boolean(pendingSubmission)}>Back</button>
                  <button className="btn btn-success" onClick={handleSubmit} disabled={loading || isCompressing || Boolean(pendingSubmission)}>
                    {loading ? 'Submitting & Uploading...' : isCompressing ? 'Processing Video...' : 'Submit Claim'}
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
