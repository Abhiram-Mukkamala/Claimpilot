import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import './LegalModal.css';

export interface LegalModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export const LegalModal: React.FC<LegalModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
}) => {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    // Save previous overflow style and lock body scrolling
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // Focus close button on mount for accessibility
    const timer = setTimeout(() => {
      closeButtonRef.current?.focus();
    }, 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
      clearTimeout(timer);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    // Only close when clicking the backdrop itself, not clicks from children
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="legal-modal-overlay"
      onClick={handleBackdropClick}
      onWheel={(e) => e.stopPropagation()}
      data-testid="legal-modal-overlay"
    >
      <div
        className="legal-modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="legal-modal-title"
        onClick={(e) => e.stopPropagation()}
        onWheel={(e) => e.stopPropagation()}
      >
        <div className="legal-modal-header">
          <h2 id="legal-modal-title" className="legal-modal-title">
            {title}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            className="legal-modal-close-btn"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="legal-modal-body">
          {children}
        </div>
      </div>
    </div>
  );
};
