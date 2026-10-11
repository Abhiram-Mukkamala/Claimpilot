import React, { useEffect, useRef } from 'react';

interface DottedWaveBackgroundProps {
  className?: string;
  style?: React.CSSProperties;
  overlayOpacity?: number;
}

export const DottedWaveBackground: React.FC<DottedWaveBackgroundProps> = ({
  className = '',
  style = {},
  overlayOpacity = 1,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return;

    let animationFrameId: number;
    let isVisible = true;
    let startTime = performance.now();
    let lastElapsedTime = 0;

    // Check user preference for reduced motion
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    let prefersReducedMotion = mediaQuery.matches;

    const handleMotionPreferenceChange = (e: MediaQueryListEvent) => {
      prefersReducedMotion = e.matches;
      if (prefersReducedMotion) {
        renderFrame(0);
      }
    };
    mediaQuery.addEventListener('change', handleMotionPreferenceChange);

    // Track tab visibility to save battery/CPU
    const handleVisibilityChange = () => {
      isVisible = !document.hidden;
      if (isVisible && !prefersReducedMotion) {
        startTime = performance.now() - lastElapsedTime;
        animationFrameId = requestAnimationFrame(loop);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    let width = 0;
    let height = 0;
    let dpr = 1;

    const resize = () => {
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      width = rect.width || window.innerWidth;
      height = rect.height || window.innerHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);

      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      if (prefersReducedMotion) {
        renderFrame(0);
      }
    };

    window.addEventListener('resize', resize);
    resize();

    // Primary wave parametric curve backbone
    const getSpinePoint = (u: number, t: number, w: number, h: number, isSecondary = false) => {
      const offsetFactor = isSecondary ? 1.18 : 1.0;
      const phaseShift = isSecondary ? 0.75 : 0.0;

      // Base S-curve trajectory spanning across viewport
      const bx = w * (-0.10 + u * 1.20);
      const by = h * (-0.12 + u * 1.24);

      // Organic wave undulations
      const waveX = Math.sin(u * Math.PI * 2.1 + t * 0.35 + phaseShift) * (w * 0.16 * offsetFactor);
      const waveY = Math.cos(u * Math.PI * 1.7 - t * 0.28 + phaseShift) * (h * 0.14 * offsetFactor);
      const waveZ = Math.sin(u * Math.PI * 2.5 + t * 0.3 + phaseShift) * 160;

      // Asymmetric organic displacement
      const organicBend = Math.sin(u * Math.PI * 4.2 + t * 0.2) * (w * 0.025);

      const x = bx + waveX + organicBend;
      const y = by + waveY;
      const z = waveZ;

      return { x, y, z };
    };

    const renderWaveRibbon = (
      t: number,
      w: number,
      h: number,
      isSecondary = false
    ) => {
      const longitudinalSteps = isSecondary ? 70 : 130;
      const transverseSteps = isSecondary ? 24 : 42;
      const baseRibbonWidth = Math.min(w, h) * (isSecondary ? 0.38 : 0.48);
      const cameraFocal = 900;

      for (let i = 0; i <= longitudinalSteps; i++) {
        const u = i / longitudinalSteps;

        // Calculate spine point and tangent for smooth 3D frame
        const p0 = getSpinePoint(u, t, w, h, isSecondary);
        const pNext = getSpinePoint(Math.min(1, u + 0.015), t, w, h, isSecondary);

        const tx = pNext.x - p0.x;
        const ty = pNext.y - p0.y;
        const tz = pNext.z - p0.z;
        const tLen = Math.hypot(tx, ty, tz) || 1;
        const ntx = tx / tLen;
        const nty = ty / tLen;

        // Transverse normal in 2D projection plane
        const nx = -nty;
        const ny = ntx;

        // 3D twist angle along the ribbon length
        const twistAngle = Math.sin(u * Math.PI * 1.9 + t * 0.25 + (isSecondary ? 1.2 : 0)) * 0.85;
        const cosTwist = Math.cos(twistAngle);
        const sinTwist = Math.sin(twistAngle);

        // Ribbon width modulation: tapers slightly at edges, widest in mid-body
        const widthEnvelope = Math.sin(u * Math.PI);
        const currentRibbonWidth = baseRibbonWidth * (0.45 + 0.65 * Math.pow(Math.max(0, widthEnvelope), 0.65));

        // Longitudinal fade to ensure zero hard boundaries
        const uFade = Math.pow(Math.max(0, widthEnvelope), 0.55);

        for (let j = 0; j <= transverseSteps; j++) {
          // Normalized position across ribbon [-1, 1]
          const normV = (j / transverseSteps) * 2 - 1;

          // Non-linear spacing: denser near the core spine, more disperse toward margins
          const v = Math.sign(normV) * Math.pow(Math.abs(normV), 1.32);

          // Subtle ripple along ribbon surface
          const surfaceRipple = Math.sin(u * 15 + normV * 5 + t * 0.45) * 18 * (1 - normV * normV);

          // 3D displacement vector
          const spanDist = v * currentRibbonWidth;
          const px = p0.x + nx * spanDist * cosTwist;
          const py = p0.y + ny * spanDist * cosTwist;
          const pz = p0.z + spanDist * sinTwist + surfaceRipple;

          // 3D perspective projection
          const depthFactor = cameraFocal / (cameraFocal + pz);
          const screenX = (px - w * 0.5) * depthFactor + w * 0.5;
          const screenY = (py - h * 0.5) * depthFactor + h * 0.5;

          // Dot alpha calculation (Gaussian falloff from spine + boundary fade)
          const vFalloff = Math.exp(-2.5 * normV * normV);
          const depthAlpha = Math.max(0.5, Math.min(1.4, depthFactor));

          // Clear, luminous alphas so wave ribbons are crisp & visible through clear glass
          const baseAlpha = isSecondary ? 0.48 : 0.88;
          const alpha = Math.max(0, Math.min(0.92, baseAlpha * vFalloff * uFade * depthAlpha));

          if (alpha < 0.015) continue;

          // Dot size: crisper and slightly larger for rich visibility
          const baseSize = isSecondary ? 1.1 : 1.45;
          const radius = Math.max(0.6, (baseSize + 0.65 * vFalloff) * depthFactor * 0.85);

          // Dot color: pure glowing white with subtle ethereal icy silver tint
          let colorString: string;
          if (vFalloff > 0.6) {
            colorString = `rgba(255, 255, 255, ${alpha.toFixed(3)})`;
          } else if (vFalloff > 0.25) {
            colorString = `rgba(225, 238, 255, ${alpha.toFixed(3)})`;
          } else {
            colorString = `rgba(175, 205, 240, ${(alpha * 0.95).toFixed(3)})`;
          }

          ctx.fillStyle = colorString;
          ctx.beginPath();
          ctx.arc(screenX, screenY, radius, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    };

    const renderFrame = (elapsedTime: number) => {
      lastElapsedTime = elapsedTime;
      // Very slow, subtle ambient time rate
      const t = elapsedTime * 0.00045;

      ctx.clearRect(0, 0, width, height);

      // 1. Atmospheric subtle radial ambient glow behind the main wave crest
      const glowX = width * (0.30 + 0.05 * Math.sin(t * 0.4));
      const glowY = height * (0.42 + 0.05 * Math.cos(t * 0.3));
      const glowRadius = Math.min(width, height) * 0.75;

      const radialGlow = ctx.createRadialGradient(
        glowX,
        glowY,
        0,
        glowX,
        glowY,
        glowRadius
      );
      radialGlow.addColorStop(0, 'rgba(255, 255, 255, 0.05)');
      radialGlow.addColorStop(0.35, 'rgba(140, 200, 255, 0.025)');
      radialGlow.addColorStop(0.7, 'rgba(34, 197, 94, 0.015)');
      radialGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');

      ctx.fillStyle = radialGlow;
      ctx.fillRect(0, 0, width, height);

      // 2. Secondary faint echo ribbon (adds rich 3D layered depth)
      renderWaveRibbon(t * 0.85, width, height, true);

      // 3. Primary flowing dotted ribbon
      renderWaveRibbon(t, width, height, false);
    };

    const loop = (timestamp: number) => {
      if (!isVisible) return;
      const elapsed = timestamp - startTime;
      renderFrame(elapsed);
      if (!prefersReducedMotion) {
        animationFrameId = requestAnimationFrame(loop);
      }
    };

    if (!prefersReducedMotion) {
      animationFrameId = requestAnimationFrame(loop);
    } else {
      renderFrame(0);
    }

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', resize);
      mediaQuery.removeEventListener('change', handleMotionPreferenceChange);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  return (
    <div
      className={`dotted-wave-bg-container ${className}`}
      style={{
        position: 'fixed',
        inset: 0,
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        pointerEvents: 'none',
        zIndex: 0,
        backgroundColor: '#070709',
        ...style,
      }}
      aria-hidden="true"
    >
      <canvas
        ref={canvasRef}
        style={{
          display: 'block',
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
        }}
      />
      {/* Gentle transparent vignette overlay - keeps wave crisp and legible */}
      <div
        className="dotted-wave-overlay"
        style={{
          position: 'absolute',
          inset: 1,
          pointerEvents: 'none',
          opacity: overlayOpacity,
          background: `
            radial-gradient(ellipse at 50% 50%, rgba(7, 7, 9, 0.12) 0%, rgba(4, 4, 6, 0.42) 100%),
            linear-gradient(180deg, rgba(7, 7, 9, 0.08) 0%, rgba(4, 4, 6, 0.32) 100%)
          `,
        }}
      />
    </div>
  );
};