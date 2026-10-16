import React, { useEffect } from 'react';
import { X } from 'lucide-react';

interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export const Drawer: React.FC<DrawerProps> = ({ isOpen, onClose, title, children }) => {
  // Prevent body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <>
      <div 
        className="drawer-overlay"
        onClick={onClose}
      />
      <div 
        className="drawer-panel"
      >
        <div className="drawer-header flex justify-between items-center">
          <h2 className="text-lg font-medium" style={{ margin: 0 }}>{title}</h2>
          <button onClick={onClose} className="btn-ghost" style={{ padding: '0.25rem', borderRadius: 'var(--radius-sm)' }}>
            <X size={20} />
          </button>
        </div>
        <div className="drawer-body">
          {children}
        </div>
      </div>
    </>
  );
};
