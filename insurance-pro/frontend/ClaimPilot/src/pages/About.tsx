import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../store/authStore';
import {
  UploadCloud,
  BrainCircuit,
  LayoutDashboard,
  CheckSquare,
  Sparkles,
  ArrowRight,
  Clock,
  MessageSquare,
  HelpCircle,
  FileSpreadsheet,
  Eye,
  CheckCircle2,
  Layers
} from 'lucide-react';
import { gsap, useGSAP, ScrollTrigger, isReducedMotion } from '../lib/gsap';
import './about.css';

interface AboutProps {
  onReturn?: () => void;
  isVisible?: boolean;
  onSectionChange?: (sectionId: string) => void;
  showNav?: boolean;
}

export interface TeamMember {
  id: string;
  initials: string;
  name: string;
  role?: string;
  description?: string;
}

const TEAM_MEMBERS: TeamMember[] = [
  {
    id: 'as',
    initials: 'AS',
    name: 'Ayaan Shaikh',
    role: 'Frontend Developer · UI/UX & 2D Damage Visualization R&D',
    description: "Built ClaimPilot's frontend and user experience while researching precise 2D vehicle damage visualization and accurate damage mapping onto vehicle models.",
  },
  {
    id: 'ss',
    initials: 'SS',
    name: 'Shreyas Shah',
    role: 'Computer Vision Engineer',
    description: ' Fine-tuned YOLOv11m and RT-DETR-L on CarDD for six damage categories. Integrated SAM2, depth estimation, DSINE, COLMAP and Open3D to derive physical damage measurements, including area, depth, volume and crease angle. ',
  },
  {
    id: 'rs',
    initials: 'RS',
    name: 'Rahul Sutar',
    role: 'Backend & Systems Engineer',
    description: "Architected ClaimPilot's backend and database using FastAPI and Supabase, implementing secure dual-role authentication and seamless frontend-to-backend integration.",
  },
  {
    id: 'am',
    initials: 'AM',
    name: 'Abhiram Mukkamala',
    role: 'Product Manager & Systems Integration',
    description: 'Directed ClaimPilot’s product development and integrated its frontend, FastAPI backend, and ML models into a unified pipeline. Designed a cross-claim perceptual hashing system to detect reused and duplicate claim images.',
  },
];

export const About: React.FC<AboutProps> = ({
  onReturn,
  isVisible = true,
  onSectionChange,
  showNav = true
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { user } = useAuth();
  const handleReturn = onReturn || (() => navigate(user ? (user.role === 'agent' ? '/agent' : '/customer') : '/login'));
  const [internalActiveSection, setInternalActiveSection] = useState('hero');

  const navItems = ['hero', 'problem', 'solution', 'team'];
  const activeIndex = Math.max(0, navItems.indexOf(internalActiveSection));

  // Track active section for navbar pill highlight
  useEffect(() => {
    if (!isVisible) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            // Map section IDs to navbar items ('solution' -> 'How it Works', 'team' -> 'Who are We')
            const id = entry.target.id;
            const mappedId = id === 'how-it-works' ? 'solution' : (id === 'who-are-we' ? 'team' : id);
            setInternalActiveSection(mappedId);
            onSectionChange?.(mappedId);
          }
        });
      },
      { root: containerRef.current, threshold: 0.35 }
    );

    const sections = containerRef.current?.querySelectorAll('.about-section');
    sections?.forEach((section) => observer.observe(section));

    return () => observer.disconnect();
  }, [isVisible, onSectionChange]);

  // GSAP Animations
  useGSAP(
    () => {
      if (!isVisible || isReducedMotion()) return;
      const container = containerRef.current;
      if (!container) return;

      // Hero Entrance
      const heroTl = gsap.timeline();
      heroTl
        .fromTo('#hero .glass-header-panel', { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.5, ease: 'power2.out' })
        .fromTo('.flow-node', { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.45, stagger: 0.08, ease: 'power2.out' }, '-=0.2');

      // ScrollTrigger for Sections
      const animateOnScroll = (selector: string, triggerId: string) => {
        gsap.fromTo(
          selector,
          { opacity: 0, y: 22 },
          {
            opacity: 1,
            y: 0,
            duration: 0.45,
            stagger: 0.08,
            ease: 'power2.out',
            scrollTrigger: {
              trigger: triggerId,
              scroller: container,
              start: 'top 80%',
              end: 'bottom 20%',
              toggleActions: 'play reverse play reverse',
            },
          }
        );
      };

      animateOnScroll('#problem .glass-header-panel', '#problem');
      animateOnScroll('.problem-card', '#problem');
      animateOnScroll('.problem-bridge', '#problem');
      animateOnScroll('#how-it-works .glass-header-panel', '#how-it-works');
      animateOnScroll('.how-card', '#how-it-works');
      animateOnScroll('#who-are-we .glass-header-panel', '#who-are-we');
      animateOnScroll('.team-card', '#who-are-we');
      animateOnScroll('.cta-card', '#cta');

      ScrollTrigger.refresh();
    },
    { scope: containerRef, dependencies: [isVisible] }
  );

  return (
    <>
      {showNav && isVisible && (
        <div
          className="glass-transition-layer"
          style={{
            width: '900px',
            maxWidth: 'calc(100vw - 3rem)',
            height: '64px',
            top: '24px',
            borderRadius: '32px',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
            pointerEvents: 'auto',
            zIndex: 50,
          }}
        >
          <div
            className="glass-nav-bar"
            style={{
              opacity: 1,
              pointerEvents: 'auto',
              justifyContent: 'space-between',
              padding: '0 2.5rem',
            }}
          >
            <div className="glass-nav-links">
              {[
                { label: 'ClaimPilot', id: 'hero' },
                { label: 'The Problem', id: 'problem' },
                { label: 'How it Works', id: 'solution' },
                { label: 'Who are We', id: 'team' },
              ].map(({ label, id }, i) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => {
                    if (id === 'hero') {
                      containerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
                    } else {
                      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
                    }
                  }}
                  style={{
                    width: '100px',
                    textAlign: 'center',
                    fontSize: '0.875rem',
                    fontWeight: 500,
                    color: activeIndex === i ? 'var(--text-primary)' : 'var(--text-secondary)',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {label}
                </button>
              ))}
              <div
                className="glass-nav-pill"
                style={{
                  left: `calc(${activeIndex * 140}px)`,
                  width: '100px',
                  transform: 'translateX(0px)',
                }}
              />
            </div>
            <button
              type="button"
              onClick={handleReturn}
              className="btn btn-primary"
              style={{
                padding: '0.5rem 1rem',
                fontSize: '0.875rem',
                fontWeight: 600,
                borderRadius: 'var(--radius-md)',
              }}
            >
              GET STARTED
            </button>
          </div>
        </div>
      )}

      <div
        ref={containerRef}
        className="about-page-container"
        style={{
          opacity: isVisible ? 1 : 0,
          pointerEvents: isVisible ? 'auto' : 'none',
        }}
      >
      {/* SECTION 1: HERO */}
      <section id="hero" className="about-section">
        <div className="about-content">
          <div className="glass-header-panel">
            <div className="about-pill-tag">
              <Sparkles size={13} />
              <span>Intelligent Claims Platform</span>
            </div>

            <h1 className="about-hero-title">ClaimPilot AI</h1>

            <p className="about-hero-desc">
              An intelligent claims platform designed to make insurance claims faster, clearer, and easier to process.
            </p>
          </div>

          <div className="workflow-pipeline">
            <div className="flow-node">
              <UploadCloud size={18} />
              <span>Claim Filed</span>
            </div>
            <div className="flow-arrow">→</div>
            <div className="flow-node active">
              <BrainCircuit size={18} />
              <span>ClaimPilot AI Analysis</span>
            </div>
            <div className="flow-arrow">→</div>
            <div className="flow-node">
              <Eye size={18} />
              <span>Damage Review</span>
            </div>
            <div className="flow-arrow">→</div>
            <div className="flow-node">
              <CheckCircle2 size={18} />
              <span>Decision</span>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 2: THE PROBLEM */}
      <section id="problem" className="about-section">
        <div className="about-content">
          <div className="glass-header-panel">
            <div className="about-pill-tag">
              <Layers size={13} />
              <span>Friction-Heavy Legacy Process</span>
            </div>

            <h2 className="about-section-title">The Problem</h2>

            <p className="about-section-desc">
              Insurance claims can become a long chain of uploads, manual inspections, repeated communication and waiting.
            </p>
          </div>

          <div className="problem-grid">
            <div className="problem-card">
              <FileSpreadsheet size={20} className="card-icon" />
              <h3>Scattered Evidence</h3>
              <p>Photos and documents fragmented across disconnected systems.</p>
            </div>
            <div className="problem-card">
              <Eye size={20} className="card-icon" />
              <h3>Manual Inspection</h3>
              <p>Time-consuming physical assessments and manual data entry.</p>
            </div>
            <div className="problem-card">
              <Clock size={20} className="card-icon" />
              <h3>Long Review Cycles</h3>
              <p>Weeks of backlog delay before claim evaluation begins.</p>
            </div>
            <div className="problem-card">
              <MessageSquare size={20} className="card-icon" />
              <h3>Repeated Communication</h3>
              <p>Constant back-and-forth status inquiries and duplicate requests.</p>
            </div>
            <div className="problem-card">
              <HelpCircle size={20} className="card-icon" />
              <h3>Unclear Progress</h3>
              <p>Zero real-time visibility into processing status or timelines.</p>
            </div>
          </div>

          <div className="problem-bridge">
            <Sparkles size={15} />
            <span>ClaimPilot brings the process together.</span>
          </div>
        </div>
      </section>

      {/* SECTION 3: HOW IT WORKS */}
      <section id="how-it-works" className="about-section">
        {/* Alias anchor for floating navbar */}
        <span id="solution" style={{ position: 'absolute', top: 0, pointerEvents: 'none' }} />
        <div className="about-content">
          <div className="glass-header-panel">
            <div className="about-pill-tag">
              <BrainCircuit size={13} />
              <span>Connected AI Workflow</span>
            </div>

            <h2 className="about-section-title">How It Works</h2>

            <p className="about-section-desc">
              ClaimPilot connects claim submission, ClaimPilot AI-assisted analysis and review into one workflow.
            </p>
          </div>

          <div className="how-grid">
            <div className="how-card">
              <div className="card-step-header">
                <span className="step-number">01</span>
                <span className="step-tag">Input</span>
              </div>
              <h3>File Your Claim</h3>
              <p>The user submits the required claim information and damage evidence.</p>
              <UploadCloud size={18} className="step-icon" />
            </div>

            <div className="how-card highlight">
              <div className="card-step-header">
                <span className="step-number">02</span>
                <span className="step-tag active-tag">Intelligence</span>
              </div>
              <h3>ClaimPilot AI Analyzes the Damage</h3>
              <p>ClaimPilot processes the submitted evidence and assists in identifying visible damage.</p>
              <BrainCircuit size={18} className="step-icon active-icon" />
            </div>

            <div className="how-card">
              <div className="card-step-header">
                <span className="step-number">03</span>
                <span className="step-tag">Understanding</span>
              </div>
              <h3>Review the Results</h3>
              <p>The claim and analysis are presented in a clear, organized interface, including visual damage information where applicable.</p>
              <LayoutDashboard size={18} className="step-icon" />
            </div>

            <div className="how-card">
              <div className="card-step-header">
                <span className="step-number">04</span>
                <span className="step-tag">Action</span>
              </div>
              <h3>Review & Respond</h3>
              <p>The claim can be reviewed and appropriate action can be taken, including requesting additional information, approving, or rejecting the claim.</p>
              <CheckSquare size={18} className="step-icon" />
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 4: WHO ARE WE */}
      <section id="who-are-we" className="about-section">
        {/* Alias anchor for floating navbar */}
        <span id="team" style={{ position: 'absolute', top: 0, pointerEvents: 'none' }} />
        <div className="about-content">
          <div className="glass-header-panel">
            <h2 className="about-section-title">Who Are We</h2>

            <p className="about-section-desc" style={{ fontSize: '16px' }}>
              We’re a team of passionate engineering students believing that insurance claims can be simpler, clearer, and smarter. We built ClaimPilot AI to bring artificial intelligence, visual damage analysis, and streamlined claim management together—reducing complexity and making the process easier for both customers and claim reviewers.
            </p>
          </div>

          <div className="team-grid">
            {TEAM_MEMBERS.map((member) => (
              <div key={member.id} className="team-card">
                <div className="team-avatar">
                  <span>{member.initials}</span>
                </div>
                <h3>{member.name}</h3>
                {member.role ? (
                  <p className="team-role">{member.role}</p>
                ) : (
                  <p className="team-role empty-role" />
                )}
                {member.description ? (
                  <p className="team-desc">{member.description}</p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 5: FINAL CTA */}
      <section id="cta" className="about-section">
        <div className="about-content">
          <div className="cta-card">
            <h2 className="cta-title">Ready to simplify the claim journey?</h2>

            <p className="cta-desc">
              Experience a clearer way to file, understand and manage claims.
            </p>

            <div className="cta-actions">
              <button onClick={handleReturn} className="btn btn-primary cta-btn">
                TRY CLAIMPILOT
                <ArrowRight size={15} />
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
    </>
  );
};
