/**
 * ClaimPilot Frontend Security Utilities
 * Centralizes client-side input validation, safe URL navigation, and file upload checks.
 * Note: Client-side validation is for UX, stability, and defense-in-depth; the backend
 * and cloud storage must enforce authoritative validation and authorization boundaries.
 */

export const MAX_IMAGE_SIZE_BYTES = 15 * 1024 * 1024; // 15 MB
export const MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB
export const MAX_DOC_SIZE_BYTES = 10 * 1024 * 1024;   // 10 MB

export const ALLOWED_IMAGE_MIME_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/heic',
  'image/heif'
]);

export const ALLOWED_IMAGE_EXTENSIONS = new Set([
  '.jpg',
  '.jpeg',
  '.png',
  '.webp',
  '.heic',
  '.heif'
]);

export const ALLOWED_VIDEO_MIME_TYPES = new Set([
  'video/mp4',
  'video/quicktime',
  'video/webm'
]);

export const ALLOWED_VIDEO_EXTENSIONS = new Set([
  '.mp4',
  '.mov',
  '.webm'
]);

/**
 * Validates whether a given URL is safe to open or render.
 * Protects against javascript:, data:text/html, vbscript: and malicious protocol injections.
 */
export function isSafeUrl(url: unknown): boolean {
  if (typeof url !== 'string' || !url.trim()) {
    return false;
  }

  const trimmed = url.trim();

  // Allow blob: URLs created locally in the browser session
  if (trimmed.startsWith('blob:')) {
    try {
      const parsed = new URL(trimmed);
      return parsed.protocol === 'blob:';
    } catch {
      return false;
    }
  }

  // Allow relative URLs starting with / (internal navigation/assets)
  if (trimmed.startsWith('/') && !trimmed.startsWith('//')) {
    return true;
  }

  try {
    const parsed = new URL(trimmed);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:';
  } catch {
    return false;
  }
}

/**
 * Safely opens a URL in a new browser context.
 * Enforces protocol safety and attaches noopener,noreferrer to eliminate reverse tabnabbing risks.
 */
export function safeOpenUrl(url: string | undefined | null, target: string = '_blank'): Window | null {
  if (!url || !isSafeUrl(url)) {
    console.warn('[Security] Refusing to open unsafe or invalid URL:', url);
    return null;
  }

  return window.open(url, target, 'noopener,noreferrer');
}

export interface FileValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Validates uploaded image file against size, MIME type, and extension restrictions.
 * Explicitly rejects SVG (scriptable) and non-whitelisted image types.
 */
export function validateImageFile(file: File): FileValidationResult {
  if (!file) {
    return { valid: false, error: 'No file provided.' };
  }

  if (file.size > MAX_IMAGE_SIZE_BYTES) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    return {
      valid: false,
      error: `File exceeds maximum allowed size of 15 MB (uploaded: ${sizeMb} MB).`
    };
  }

  if (file.size === 0) {
    return { valid: false, error: 'File is empty (0 bytes).' };
  }

  const parts = file.name.split('.');
  const ext = parts.length > 1 ? `.${parts.pop()!.toLowerCase()}` : '';
  const mime = (file.type || '').toLowerCase();

  // Disallow SVG explicitly due to stored XSS capabilities
  if (mime.includes('svg') || ext === '.svg') {
    return {
      valid: false,
      error: 'SVG images are not permitted for vehicle damage evidence.'
    };
  }

  const hasValidExt = ALLOWED_IMAGE_EXTENSIONS.has(ext);
  const hasValidMime = ALLOWED_IMAGE_MIME_TYPES.has(mime);

  if (!hasValidExt && !hasValidMime) {
    return {
      valid: false,
      error: 'Unsupported image format. Allowed formats: JPG, PNG, WEBP, HEIC.'
    };
  }

  return { valid: true };
}

/**
 * Validates uploaded video file against size, MIME type, and extension restrictions.
 */
export function validateVideoFile(file: File): FileValidationResult {
  if (!file) {
    return { valid: false, error: 'No file provided.' };
  }

  if (file.size > MAX_VIDEO_SIZE_BYTES) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    return {
      valid: false,
      error: `Video exceeds maximum allowed size of 50 MB (uploaded: ${sizeMb} MB).`
    };
  }

  if (file.size === 0) {
    return { valid: false, error: 'Video file is empty (0 bytes).' };
  }

  const parts = file.name.split('.');
  const ext = parts.length > 1 ? `.${parts.pop()!.toLowerCase()}` : '';
  const mime = (file.type || '').toLowerCase();

  const hasValidExt = ALLOWED_VIDEO_EXTENSIONS.has(ext);
  const hasValidMime = ALLOWED_VIDEO_MIME_TYPES.has(mime);

  if (!hasValidExt && !hasValidMime) {
    return {
      valid: false,
      error: 'Unsupported video format. Allowed formats: MP4, MOV, WebM.'
    };
  }

  return { valid: true };
}

/**
 * Sanitizes generic user text strings by stripping non-printable ASCII control characters.
 */
export function sanitizeText(val: unknown): string {
  if (typeof val !== 'string') return '';
  // Remove control characters (except newline, tab, carriage return)
  return val.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '').trim();
}
