import React from 'react';

export const Badge: React.FC<{
  children: React.ReactNode;
  variant?: 'success' | 'warning' | 'danger' | 'neutral';
  className?: string;
  style?: React.CSSProperties;
}> = ({ children, variant = 'neutral', className = '', style }) => {
  return (
    <span className={`badge badge-${variant} ${className}`} style={style}>
      {children}
    </span>
  );
};
