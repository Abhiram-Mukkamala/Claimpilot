import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authStore } from '../store/authStore';
import { useGSAP, animateFadeIn, animateStagger, isReducedMotion, gsap } from '../lib/gsap';
import { About } from './About';
import { AlertCircle } from 'lucide-react';

export type TransitionState = 'idle' | 'enteringAbout' | 'about' | 'returningToLogin';

export const Login: React.FC = () => {
  const [isSignUp, setIsSignUp] = useState(false);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [transitionState, setTransitionState] = useState<TransitionState>('idle');
  const [activeSection, setActiveSection] = useState('hero');

  // Form State
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [dob, setDob] = useState('');
  const [phone, setPhone] = useState('');

  // Error States
  const [errors, setErrors] = useState<Record<string, string>>({});

  // OTP State
  const [showOtp, setShowOtp] = useState(false);
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [otpError, setOtpError] = useState(false);
  const [resendTimer, setResendTimer] = useState(42);
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);
  const otpModalRef = useRef<HTMLDivElement>(null);
  const otpContentRef = useRef<HTMLDivElement>(null);

  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const brandingRef = useRef<HTMLDivElement>(null);
  const formColRef = useRef<HTMLDivElement>(null);
  const logoItemRef = useRef<HTMLDivElement>(null);
  const logoTextRef = useRef<HTMLHeadingElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);

  // Transition Refs
  const glassRef = useRef<HTMLDivElement>(null);
  const pillRef = useRef<HTMLDivElement>(null);

  // Scroll inertia lock refs
  const scrollLockRef = useRef(false);
  const scrollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Page entrance — runs once on mount
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (showOtp && resendTimer > 0) {
      interval = setInterval(() => {
        setResendTimer(prev => prev - 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [showOtp, resendTimer]);

  const { contextSafe } = useGSAP(() => {
    animateStagger('.login-branding-item', { stagger: 0.07, y: 10, duration: 0.38 });
    animateFadeIn(formColRef.current, { y: 12, duration: 0.4, delay: 0.1 });
  }, { scope: containerRef });

  useGSAP(() => {
    if (showOtp && otpModalRef.current && otpContentRef.current) {
      gsap.fromTo(otpModalRef.current, { opacity: 0 }, { opacity: 1, duration: 0.3, ease: 'power2.out' });
      gsap.fromTo(otpContentRef.current, { scale: 0.95, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.3, delay: 0.1, ease: 'power2.out' });
    }
  }, { dependencies: [showOtp] });

  const startAboutTransition = contextSafe(() => {
    if (transitionState !== 'idle') return;
    setTransitionState('enteringAbout');

    // Lock scrolling to absorb trackpad inertia
    scrollLockRef.current = true;
    if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
    scrollTimeoutRef.current = setTimeout(() => {
      scrollLockRef.current = false;
    }, 500);

    const tl = gsap.timeline({
      onComplete: () => {
        setTransitionState('about');
        window.history.pushState(null, '', '/about');
      }
    });

    // 1. Expand pill to full screen
    tl.to(glassRef.current, {
      width: '100vw',
      height: '100vh',
      top: 0,
      borderRadius: 0,
      backdropFilter: 'blur(32px)',
      backgroundColor: 'rgba(0,0,0,0.5)',
      duration: 0.8,
      ease: 'expo.inOut'
    }, 0);

    // 2. Hide Login Form
    tl.to(containerRef.current, {
      filter: 'blur(12px)',
      scale: 0.95,
      opacity: 0,
      duration: 0.8,
      ease: 'expo.inOut'
    }, 0);

    // 3. Fade in About Page (it is mounted because transitionState='enteringAbout')
    tl.fromTo('.about-page-container',
      { opacity: 0 },
      { opacity: 1, duration: 0.4 },
      0.4
    );

    // 4. Shrink to top nav bar
    tl.to(glassRef.current, {
      width: '900px',
      height: '64px',
      top: '24px',
      borderRadius: '32px',
      backdropFilter: 'blur(20px)',
      backgroundColor: 'rgba(255, 255, 255, 0.1)',
      duration: 0.8,
      ease: 'expo.inOut'
    }, 0.8);
  });

  const reverseAboutTransition = contextSafe(() => {
    if (transitionState !== 'about') return;
    setTransitionState('returningToLogin');

    // Lock scrolling to absorb trackpad inertia
    scrollLockRef.current = true;
    if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
    scrollTimeoutRef.current = setTimeout(() => {
      scrollLockRef.current = false;
    }, 500);

    const tl = gsap.timeline({
      onComplete: () => {
        setTransitionState('idle');
        window.history.pushState(null, '', '/login');
      }
    });

    // 1. Expand to full screen
    tl.to(glassRef.current, {
      width: '100vw',
      height: '100vh',
      top: 0,
      borderRadius: 0,
      backdropFilter: 'blur(32px)',
      backgroundColor: 'rgba(0,0,0,0.5)',
      duration: 0.8,
      ease: 'expo.inOut'
    }, 0);

    // 2. Fade out About Page
    tl.to('.about-page-container', {
      opacity: 0,
      duration: 0.4
    }, 0);

    // 3. Reveal Login Form
    tl.to(containerRef.current, {
      filter: 'blur(0px)',
      scale: 1,
      opacity: 1,
      duration: 0.8,
      ease: 'expo.inOut'
    }, 0.6);

    // 4. Shrink back to initial pill
    tl.to(glassRef.current, {
      width: '320px',
      height: '48px',
      top: '24px',
      borderRadius: '24px',
      backdropFilter: 'blur(12px)',
      backgroundColor: 'rgba(255, 255, 255, 0.2)',
      duration: 0.8,
      ease: 'expo.inOut'
    }, 0.6);
  });

  const startTransition = contextSafe((role: string) => {
    setIsAuthenticating(true);
    if (isReducedMotion()) {
      navigate(role === 'agent' ? '/agent' : '/customer');
      return;
    }

    const tl = gsap.timeline({
      onComplete: () => navigate(role === 'agent' ? '/agent' : '/customer')
    });

    // Phase 1: form/background fades
    tl.to(formColRef.current, { opacity: 0, duration: 0.30, ease: 'power2.out' }, 0);
    tl.to('.login-branding-item:not(:first-child)', { opacity: 0, duration: 0.30, ease: 'power2.out' }, 0);
    tl.to(statusRef.current, { opacity: 0, duration: 0.30, ease: 'power2.out' }, 0);
    tl.to(brandingRef.current, { borderRightColor: 'transparent', duration: 0.30 }, 0);
    tl.to(glassRef.current, { opacity: 0, y: -20, duration: 0.30, ease: 'power2.out' }, 0);

    // Fade out the subtitle under the logo
    if (logoItemRef.current) {
      tl.to(logoItemRef.current.querySelector('p'), { opacity: 0, duration: 0.30, ease: 'power2.out' }, 0);
    }

    // Phase 2: ClaimPilot branding moves to center + scales up
    if (logoItemRef.current && containerRef.current) {
      const rect = logoItemRef.current.getBoundingClientRect();
      const containerRect = containerRef.current.getBoundingClientRect();

      const targetX = (containerRect.width / 2) - (rect.left + rect.width / 2);
      const targetY = (containerRect.height / 2) - (rect.top + rect.height / 2);

      tl.to(logoItemRef.current, {
        x: targetX,
        y: targetY,
        scale: 1.5,
        duration: 0.55,
        ease: 'power3.inOut'
      }, 0.15);

      // Phase 3 is a brief hold 

      // Phase 4:  Backspace/delete text
      const originalText = "ClaimPilot AI";
      const backspaceObj = { length: originalText.length };
      tl.to(backspaceObj, {
        length: 0,
        duration: 1.2,
        ease: 'none',
        onUpdate: () => {
          if (logoTextRef.current) {
            logoTextRef.current.innerText = originalText.slice(0, Math.round(backspaceObj.length));
          }
        }
      }, 0.50);

      // Phase 5: Typewriter text (starts AFTER backspace finishes at 2.25s)
      const userName = name || 'Demo User';
      const newText = `Welcome, ${userName}`;
      const typeObj = { length: 0 };
      tl.to(typeObj, {
        length: newText.length,
        duration: 1,
        ease: 'none',
        onUpdate: () => {
          if (logoTextRef.current) {
            logoTextRef.current.innerText = newText.slice(0, Math.round(typeObj.length));
          }
        }
      }, 2.25);

      // Phase 6: hold for 1 sec, then fade out before navigation
      tl.to(logoItemRef.current, {
        opacity: 0,
        duration: 0.20,
        ease: 'power2.out'
      }, 3.60);
    }
  });

  useEffect(() => {
    const handleScroll = (e: WheelEvent) => {
      // Absorb trackpad inertia dynamically
      if (scrollLockRef.current) {
        e.preventDefault();
        if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
        scrollTimeoutRef.current = setTimeout(() => {
          scrollLockRef.current = false;
        }, 150);
        return;
      }

      if (transitionState !== 'idle') return;

      const target = e.target as HTMLElement;

      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') {
        return;
      }

      const isScrollable = (el: HTMLElement): boolean => {
        if (!el || el === document.body || el === document.documentElement) return false;
        const style = window.getComputedStyle(el);
        const overflowY = style.overflowY;
        const isOverflowing = el.scrollHeight > el.clientHeight;
        if ((overflowY === 'auto' || overflowY === 'scroll') && isOverflowing) {
          return true;
        }
        return el.parentElement ? isScrollable(el.parentElement) : false;
      };

      if (isScrollable(target)) {
        return;
      }

      if (e.deltaY > 0) {
        e.preventDefault();
        startAboutTransition();
      }
    };

    window.addEventListener('wheel', handleScroll, { passive: false });

    return () => {
      window.removeEventListener('wheel', handleScroll);
    };
  }, [transitionState, startAboutTransition]);

  const verifyOtp = contextSafe(() => {
    const enteredOtp = otp.join('');
    // TODO: Remove demo OTP and replace with backend OTP verification before production.
    if (enteredOtp === '000000') {
      if (isReducedMotion()) {
        setShowOtp(false);
        authStore.login(email, name || 'Demo User', phone || undefined, dob || undefined);
        startTransition('customer');
        return;
      }

      // Smoothly animate away the modal
      if (otpContentRef.current) {
        gsap.to(otpContentRef.current, { scale: 0.95, opacity: 0, duration: 0.3, ease: 'power2.in' });
      }

      if (otpModalRef.current) {
        gsap.to(otpModalRef.current, {
          opacity: 0,
          duration: 0.3,
          delay: 0.1,
          ease: 'power2.in',
          onComplete: () => {
            setShowOtp(false);
            authStore.login(email, name || 'Demo User', phone || undefined, dob || undefined);

            // Add a slight pause before starting the login animation
            setTimeout(() => {
              startTransition('customer');
            }, 300);
          }
        });
      } else {
        setShowOtp(false);
        authStore.login(email, name || 'Demo User', phone || undefined, dob || undefined);
        startTransition('customer');
      }
    } else {
      setOtpError(true);
    }
  });

  const closeOtp = contextSafe(() => {
    setOtp(['', '', '', '', '', '']);
    setOtpError(false);
    if (isReducedMotion()) { setShowOtp(false); return; }
    if (otpContentRef.current) gsap.to(otpContentRef.current, { scale: 0.95, opacity: 0, duration: 0.2, ease: 'power2.in' });
    if (otpModalRef.current) gsap.to(otpModalRef.current, { opacity: 0, duration: 0.2, delay: 0.05, ease: 'power2.in', onComplete: () => setShowOtp(false) });
  });

  const handleOtpChange = (index: number, value: string) => {
    if (value.length > 1) {
      const pasted = value.slice(0, 6).split('');
      const newOtp = [...otp];
      pasted.forEach((char, i) => {
        if (index + i < 6) newOtp[index + i] = char;
      });
      setOtp(newOtp);
      const nextIndex = Math.min(index + pasted.length, 5);
      otpRefs.current[nextIndex]?.focus();
      return;
    }
    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);
    setOtpError(false);

    if (value && index < 5) {
      otpRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  };

  // Utility to check password strength
  const getPasswordStrength = (pass: string) => {
    if (!pass) return { label: '', color: 'transparent', width: '0%' };
    let score = 0;
    if (pass.length >= 8) score += 1;
    if (/[A-Z]/.test(pass)) score += 1;
    if (/[0-9]/.test(pass)) score += 1;
    if (/[^A-Za-z0-9]/.test(pass)) score += 1;

    if (score <= 1) return { label: 'Weak', color: 'var(--danger)', width: '33%' };
    if (score === 2 || score === 3) return { label: 'Medium', color: 'var(--warning)', width: '66%' };
    return { label: 'Strong', color: 'var(--success)', width: '100%' };
  };

  // Recognized global email domains
  const VALID_GLOBAL_EMAIL_DOMAINS = new Set([
    // Google
    'gmail.com',
    'googlemail.com',
    // Microsoft
    'outlook.com',
    'hotmail.com',
    'live.com',
    'msn.com',
    // Yahoo
    'yahoo.com',
    'yahoo.co.in',
    'yahoo.co.uk',
    'yahoo.ca',
    'yahoo.fr',
    'yahoo.de',
    'ymail.com',
    // Apple
    'icloud.com',
    'me.com',
    'mac.com',
    // Proton
    'proton.me',
    'protonmail.com',
    'pm.me',
    // Zoho
    'zoho.com',
    'zoho.in',
    // AOL
    'aol.com',
    // Mail.com & GMX
    'mail.com',
    'gmx.com',
    'gmx.net',
    // Fastmail & Tuta
    'fastmail.com',
    'tutanota.com',
    'tutamail.com',
    // Yandex
    'yandex.com',
    // System Agent Domain
    'claimpilot.ai'
  ]);

  const isValidEmail = (val: string): boolean => {
    if (!val || typeof val !== 'string') return false;
    const trimmed = val.trim().toLowerCase();
    const basicRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!basicRegex.test(trimmed)) return false;
    if (trimmed.includes('..')) return false;

    const parts = trimmed.split('@');
    if (parts.length !== 2) return false;
    const domain = parts[1];

    return VALID_GLOBAL_EMAIL_DOMAINS.has(domain);
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!isSignUp) {
      // Login validation: Keep all checking parameters, but provide only 1 unified error message
      const isEmailValid = Boolean(email && isValidEmail(email));
      const isPhoneValid = /^\d{10}$/.test(email.replace(/\D/g, ''));
      const isIdentifierValid = Boolean(email && (isEmailValid || isPhoneValid));
      const isPasswordValid = Boolean(password && password.length >= 6);

      if (!isIdentifierValid || !isPasswordValid) {
        newErrors.auth = 'Invalid Email/Mobile or Password';
      }

      setErrors(newErrors);
      return Object.keys(newErrors).length === 0;
    }

    // Sign Up validation: detailed field-level error messages
    if (!email) {
      newErrors.email = 'Email is required';
    } else if (!isValidEmail(email)) {
      newErrors.email = 'Please enter an email from a recognized global provider (e.g. gmail.com, outlook.com, yahoo.com)';
    }

    if (!password) {
      newErrors.password = 'Password is required';
    } else if (password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    }

    // Name Validation
    if (!name.trim()) {
      newErrors.name = 'Full name is required';
    }

    // DOB Validation
    if (!dob) {
      newErrors.dob = 'Date of birth is required';
    } else {
      const birthDate = new Date(dob);
      const today = new Date();
      let calculatedAge = today.getFullYear() - birthDate.getFullYear();
      const m = today.getMonth() - birthDate.getMonth();
      if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
        calculatedAge--;
      }
      if (calculatedAge < 18) {
        newErrors.dob = 'You must be 18 or older to register';
      }
    }

    // Phone Validation
    const phoneDigits = phone.replace(/\D/g, '');
    if (!phone.trim()) {
      newErrors.phone = 'Phone number is required';
    } else if (phoneDigits.length < 10) {
      newErrors.phone = 'Please enter a valid 10-digit phone number';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isAuthenticating) return;

    if (!validateForm()) return;

    // Proceed with Mock Auth
    const isAgentLogin = !isSignUp && email.toLowerCase() === 'agent@claimpilot.ai';

    if (isAgentLogin) {
      authStore.login(email, name || 'Demo User', phone || undefined, dob || undefined);
      startTransition('agent');
    } else {
      setShowOtp(true);
      setResendTimer(42);
    }
  };

  const strength = getPasswordStrength(password);

  // Calculate pill highlight position based on active section
  const navItems = ['hero', 'problem', 'solution', 'team'];
  const activeIndex = navItems.indexOf(activeSection);

  return (
    <>
      {/* Glass Top Bar / Transition Layer */}
      <div ref={glassRef} className="glass-transition-layer">
        <div className="glass-nav-bar" style={{
          opacity: transitionState === 'idle' ? 1 : (transitionState === 'about' ? 1 : 0),
          transition: 'all 0.4s ease',
          pointerEvents: transitionState === 'about' ? 'auto' : 'none',
          justifyContent: transitionState === 'about' ? 'space-between' : 'center',
          padding: transitionState === 'about' ? '0 2.5rem' : '0'
        }}>
          {transitionState === 'idle' && (
            <div style={{ margin: '0 auto', fontSize: '0.875rem', fontWeight: 500, color: 'var(--text-primary)' }}>
              Want to know about us? Scroll ↓
            </div>
          )}
          {transitionState === 'about' && (
            <>
              <div className="glass-nav-links">
                {['ClaimPilot', 'The Problem', 'How it Works', 'Who are We'].map((label, i) => (
                  <button
                    key={label}
                    onClick={() => {
                      const id = navItems[i];
                      const el = document.getElementById(id);
                      if (id === 'hero') document.querySelector('.about-page-container')?.scrollTo({ top: 0, behavior: 'smooth' });
                      else el?.scrollIntoView({ behavior: 'smooth' });
                    }}
                    style={{
                      width: '100px',
                      textAlign: 'center',
                      fontSize: '0.875rem',
                      fontWeight: 500,
                      color: activeIndex === i ? 'var(--text-primary)' : 'var(--text-secondary)'
                    }}
                  >
                    {label}
                  </button>
                ))}
                <div
                  ref={pillRef}
                  className="glass-nav-pill"
                  style={{
                    left: `calc(${activeIndex * 140}px)`,
                    width: '100px',
                    transform: `translateX(0px)`
                  }}
                />
              </div>
              <button
                onClick={reverseAboutTransition}
                className="btn btn-primary"
                style={{ padding: '0.5rem 1rem', fontSize: '0.875rem', fontWeight: 600, borderRadius: 'var(--radius-md)' }}
              >
                GET STARTED
              </button>
            </>
          )}
        </div>
      </div>

      <About isVisible={transitionState === 'about' || transitionState === 'enteringAbout'} onReturn={reverseAboutTransition} onSectionChange={setActiveSection} />

      <div
        ref={containerRef}
        className="login-layout"
        style={{
          minHeight: '100vh',
          display: 'flex',
          position: 'relative',
        }}
      >
        {/* Left Column — Branding */}
        <div
          ref={brandingRef}
          className="login-branding"
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            padding: '3.5rem',
            borderRight: '1px solid rgba(255, 255, 255, 0.08)',
            position: 'relative',
            zIndex: 1,
          }}
        >
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div ref={logoItemRef} className="login-branding-item" style={{ marginBottom: '2.5rem' }}>
              <h1 ref={logoTextRef} style={{
                fontSize: '3.25rem',
                fontWeight: 700,
                letterSpacing: '-0.04em',
                color: 'var(--text-primary)',
                lineHeight: 1,
                marginBottom: '0.85rem',
                minHeight: '3.25rem', // Prevents layout shift when text is deleted
                textShadow: '0 2px 20px rgba(0, 0, 0, 0.8)',
              }}>
                ClaimPilot AI
              </h1>
              <p style={{
                fontSize: '1rem',
                fontWeight: 500,
                color: 'var(--text-secondary)',
                letterSpacing: '-0.01em',
              }}>
                Claims Operations Platform
              </p>
            </div>

            <div
              className="login-branding-item"
              style={{
                borderLeft: '2px solid rgba(255, 255, 255, 0.12)',
                paddingLeft: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.85rem',
              }}
            >
              {[
                'AI-POWERED DAMAGE ANALYSIS',
                'REAL-TIME FRAUD DETECTION',
                'POLICY LIFECYCLE MANAGEMENT',
              ].map((feature) => (
                <div key={feature} style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                  <span style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--accent)',
                    flexShrink: 0,
                    boxShadow: '0 0 8px rgba(34, 197, 94, 0.6)',
                  }} />
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.6875rem',
                    color: 'rgba(240, 240, 245, 0.85)',
                    letterSpacing: '0.06em',
                  }}>
                    {feature}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div ref={statusRef} style={{
            paddingTop: '1.5rem',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          }}>
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.625rem', color: 'var(--text-secondary)', opacity: 0.7 }}>
              SYSTEM STATUS: <span style={{ color: 'var(--accent)' }}>OPERATIONAL</span>
            </p>
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.625rem', color: 'var(--text-secondary)', opacity: 0.7, marginTop: '0.25rem' }}>
              SECURE CONNECTION ESTABLISHED
            </p>
          </div>
        </div>

        {/* Right Column — Login Form with Liquid Glass Card */}
        <div
          ref={formColRef}
          className="login-form-col"
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '3rem',
            position: 'relative',
            zIndex: 1,
          }}
        >
          <div
            className="login-glass-card"
            style={{
              width: '100%',
              maxWidth: '430px',
              backgroundColor: 'rgba(16, 16, 22, 0.32)',
              backdropFilter: 'blur(5px) saturate(100%)',
              WebkitBackdropFilter: 'blur(5px) saturate(120%)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 'var(--radius-lg)',
              padding: '2.5rem',
              boxShadow: '0 24px 64px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.16), inset 0 0 24px rgba(255, 255, 255, 0.02)',
            }}
          >
            <div style={{ marginBottom: '2rem' }}>
              <h2 style={{
                fontSize: '1.25rem',
                fontWeight: 600,
                letterSpacing: '-0.02em',
                marginBottom: '0.375rem',
              }}>
                {isSignUp ? 'Create an account' : 'Sign in to your account'}
              </h2>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                {isSignUp
                  ? 'Enter your details below to register.'
                  : 'Enter your credentials to access the operations portal.'}
              </p>
            </div>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {errors.auth && (
                <div style={{
                  padding: '0.625rem 0.875rem',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid var(--danger)',
                  color: 'var(--danger)',
                  fontSize: '0.8125rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  lineHeight: 1.4,
                }}>
                  <AlertCircle size={15} style={{ flexShrink: 0 }} />
                  <span>{errors.auth}</span>
                </div>
              )}

              {isSignUp && (
                <>
                  <div>
                    <label className="form-label" style={{ fontSize: '0.8125rem', marginBottom: '0.375rem' }}>
                      Full Name <span style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      value={name}
                      onChange={(e) => { setName(e.target.value); if (errors.name) setErrors({ ...errors, name: '' }); }}
                      placeholder="John Doe"
                      style={{ borderColor: errors.name ? 'var(--danger)' : undefined }}
                    />
                    {errors.name && <p style={{ color: 'var(--danger)', fontSize: '0.75rem', marginTop: '0.25rem' }}>{errors.name}</p>}
                  </div>

                  <div>
                    <label className="form-label" style={{ fontSize: '0.8125rem', marginBottom: '0.375rem' }}>
                      Date of Birth <span style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <input
                      type="date"
                      className="form-input"
                      value={dob}
                      max={new Date().toISOString().split('T')[0]}
                      onChange={(e) => { setDob(e.target.value); if (errors.dob) setErrors({ ...errors, dob: '' }); }}
                      style={{ borderColor: errors.dob ? 'var(--danger)' : undefined, color: dob ? 'inherit' : 'var(--text-muted)' }}
                    />
                    {errors.dob && <p style={{ color: 'var(--danger)', fontSize: '0.75rem', marginTop: '0.25rem' }}>{errors.dob}</p>}
                  </div>
                </>
              )}

              <div>
                <label className="form-label" style={{ fontSize: '0.8125rem', marginBottom: '0.375rem' }}>
                  {isSignUp ? 'Email address' : 'Email or Mobile Number'} {isSignUp && <span style={{ color: 'var(--danger)' }}>*</span>}
                </label>
                <input
                  type={isSignUp ? "email" : "text"}
                  className="form-input"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (errors.email || errors.auth) setErrors({ ...errors, email: '', auth: '' });
                  }}
                  placeholder={isSignUp ? "agent@claimpilot.ai" : "Enter your email or mobile number"}
                  style={{ borderColor: (errors.email || errors.auth) ? 'var(--danger)' : undefined }}
                />
                {errors.email && <p style={{ color: 'var(--danger)', fontSize: '0.75rem', marginTop: '0.25rem' }}>{errors.email}</p>}
              </div>

              {isSignUp && (
                <div>
                  <label className="form-label" style={{ fontSize: '0.8125rem', marginBottom: '0.375rem' }}>
                    Phone number <span style={{ color: 'var(--danger)' }}>*</span>
                  </label>
                  <input
                    type="tel"
                    className="form-input"
                    value={phone}
                    onChange={(e) => {
                      const cleaned = e.target.value.replace(/[^\d+\-\s()]/g, '');
                      setPhone(cleaned);
                      if (errors.phone) setErrors({ ...errors, phone: '' });
                    }}
                    placeholder="+91 98765 43210"
                    style={{ borderColor: errors.phone ? 'var(--danger)' : undefined }}
                  />
                  {errors.phone && <p style={{ color: 'var(--danger)', fontSize: '0.75rem', marginTop: '0.25rem' }}>{errors.phone}</p>}
                </div>
              )}

              <div>
                <label className="form-label" style={{ fontSize: '0.8125rem', marginBottom: '0.375rem' }}>
                  Password {isSignUp && <span style={{ color: 'var(--danger)' }}>*</span>}
                </label>
                <input
                  type="password"
                  className="form-input"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errors.password || errors.auth) setErrors({ ...errors, password: '', auth: '' });
                  }}
                  placeholder="••••••••"
                  style={{ borderColor: (errors.password || errors.auth) ? 'var(--danger)' : undefined }}
                />
                {errors.password && <p style={{ color: 'var(--danger)', fontSize: '0.75rem', marginTop: '0.25rem' }}>{errors.password}</p>}

                {isSignUp && password.length > 0 && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                      <span style={{ fontSize: '0.6875rem', color: 'var(--text-secondary)' }}>Password strength</span>
                      <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: strength.color }}>{strength.label}</span>
                    </div>
                    <div style={{ width: '100%', height: '4px', backgroundColor: 'var(--bg-hover)', borderRadius: '2px', overflow: 'hidden' }}>
                      <div style={{
                        width: strength.width,
                        backgroundColor: strength.color,
                        height: '100%',
                        transition: 'all 0.3s ease'
                      }} />
                    </div>
                  </div>
                )}
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '0.5rem', padding: '0.75rem', fontWeight: 600 }}
              >
                {isSignUp ? 'Create Account' : 'Sign In'}
              </button>
            </form>

            <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                {isSignUp ? 'Already have an account?' : "Don't have an account?"}{' '}
                <button
                  onClick={() => { setIsSignUp(!isSignUp); setErrors({}); }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-primary)',
                    fontWeight: 600,
                    cursor: 'pointer',
                    padding: 0,
                    textDecoration: 'underline',
                    textUnderlineOffset: '4px'
                  }}
                >
                  {isSignUp ? 'Sign in' : 'Sign up'}
                </button>
              </p>
            </div>

            {!isSignUp && (
              <div style={{
                marginTop: '2rem',
                paddingTop: '1.5rem',
                borderTop: '1px solid var(--border)',
              }}>
                <p style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.6875rem',
                  color: 'var(--text-secondary)',
                  letterSpacing: '0.01em',
                  marginBottom: '0.375rem',
                }}>
                  DEMO CREDENTIALS
                </p>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Agent: <span style={{ color: 'var(--text-primary)' }}>agent@claimpilot.ai</span>
                </p>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                  Customer: <span style={{ color: 'var(--text-primary)' }}>any other email</span>
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {showOtp && (
        <div
          ref={otpModalRef}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.55)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}>
          <div
            ref={otpContentRef}
            style={{
              position: 'relative',
              backgroundColor: 'rgba(16, 16, 22, 0.45)',
              backdropFilter: 'blur(20px) saturate(180%)',
              WebkitBackdropFilter: 'blur(20px) saturate(180%)',
              border: '1px solid rgba(255, 255, 255, 0.14)',
              borderRadius: 'var(--radius-lg)',
              padding: '2.5rem',
              width: '100%',
              maxWidth: '420px',
              textAlign: 'center',
              boxShadow: '0 24px 64px -12px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.16)',
            }}>
            <button
              onClick={closeOtp}
              aria-label="Close"
              style={{
                position: 'absolute', top: '0.75rem', right: '0.75rem',
                background: 'none', border: 'none', color: 'var(--text-secondary)',
                fontSize: '1.25rem', cursor: 'pointer', padding: '0.25rem 0.5rem',
                lineHeight: 1, borderRadius: 'var(--radius-sm)',
                transition: 'color 0.2s',
              }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-secondary)')}
            >
              ✕
            </button>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
              Verify your identity
            </h2>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
              We've sent a verification code to<br />
              <strong style={{ color: 'var(--text-primary)' }}>******123</strong>
            </p>

            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', marginBottom: '1.5rem' }}>
              {otp.map((digit, i) => (
                <input
                  key={i}
                  ref={el => { otpRefs.current[i] = el; }}
                  type="text"
                  maxLength={6}
                  value={digit}
                  onChange={e => handleOtpChange(i, e.target.value)}
                  onKeyDown={e => handleOtpKeyDown(i, e)}
                  style={{
                    width: '3rem',
                    height: '3.5rem',
                    textAlign: 'center',
                    fontSize: '1.25rem',
                    fontWeight: 600,
                    backgroundColor: 'var(--bg-base)',
                    border: `1px solid ${otpError ? 'var(--danger)' : 'var(--border)'}`,
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-primary)',
                    outline: 'none',
                    transition: 'border-color 0.2s',
                  }}
                  onFocus={e => e.target.style.borderColor = otpError ? 'var(--danger)' : 'var(--accent)'}
                  onBlur={e => e.target.style.borderColor = otpError ? 'var(--danger)' : 'var(--border)'}
                />
              ))}
            </div>

            {otpError && (
              <p style={{ color: 'var(--danger)', fontSize: '0.875rem', marginBottom: '1rem' }}>
                Incorrect verification code. Please try again.
              </p>
            )}

            <div style={{ marginBottom: '1.5rem' }}>
              {resendTimer > 0 ? (
                <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                  Resend code in 00:{resendTimer.toString().padStart(2, '0')}
                </p>
              ) : (
                <button
                  onClick={() => setResendTimer(42)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--accent)',
                    fontWeight: 600,
                    fontSize: '0.875rem',
                    cursor: 'pointer',
                    padding: 0,
                  }}
                >
                  Resend code
                </button>
              )}
            </div>

            <button
              onClick={verifyOtp}
              className="btn btn-primary"
              style={{ width: '100%', padding: '0.75rem', fontWeight: 600 }}
            >
              Verify
            </button>
          </div>
        </div>
      )}
    </>
  );
};