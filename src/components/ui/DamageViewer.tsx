import React, { useState } from 'react';
import {  DamageAnalysis, DamageArea  } from '../../types/analysis';
import { ShieldAlert } from 'lucide-react';

interface DamageViewerProps {
  analysis: DamageAnalysis;
  onSelectDamage?: (damage: DamageArea | null) => void;
  selectedDamageId?: string | null;
}

export const DamageViewer: React.FC<DamageViewerProps> = ({ 
  analysis, 
  onSelectDamage,
  selectedDamageId 
}) => {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <div style={{ position: 'relative', width: '100%', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--border-color)', backgroundColor: 'var(--bg-primary)' }}>
      <img 
        src={analysis.imageUrl} 
        alt="Vehicle Damage Analysis" 
        style={{ width: '100%', height: 'auto', display: 'block' }} 
      />
      
      {/* Overlays */}
      {analysis.damages.map((damage, index) => {
        const isSelected = selectedDamageId === damage.id;
        const isHovered = hoveredId === damage.id;
        const isActive = isSelected || isHovered;
        
        return (
          <div 
            key={damage.id}
            onMouseEnter={() => setHoveredId(damage.id)}
            onMouseLeave={() => setHoveredId(null)}
            onClick={() => onSelectDamage?.(isSelected ? null : damage)}
            style={{
              position: 'absolute',
              left: `${damage.boundingBox.x}%`,
              top: `${damage.boundingBox.y}%`,
              width: `${damage.boundingBox.width}%`,
              height: `${damage.boundingBox.height}%`,
              border: `2px solid ${isActive ? 'var(--warning)' : 'rgba(245, 158, 11, 0.5)'}`,
              backgroundColor: isActive ? 'rgba(245, 158, 11, 0.2)' : 'rgba(245, 158, 11, 0.05)',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
          >
            <div style={{
              position: 'absolute',
              top: '-12px',
              left: '-12px',
              width: '24px',
              height: '24px',
              backgroundColor: isActive ? 'var(--warning)' : 'var(--bg-secondary)',
              color: isActive ? '#000' : 'var(--text-primary)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.75rem',
              fontWeight: 'bold',
              border: isActive ? 'none' : '1px solid var(--warning)',
              boxShadow: '0 2px 4px rgba(0,0,0,0.5)',
              zIndex: 10
            }}>
              {index + 1}
            </div>
          </div>
        );
      })}

      {/* AI Watermark */}
      <div style={{
        position: 'absolute',
        bottom: '1rem',
        left: '1rem',
        backgroundColor: 'rgba(18, 20, 23, 0.8)',
        backdropFilter: 'blur(4px)',
        padding: '0.25rem 0.75rem',
        borderRadius: 'var(--radius-sm)',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        fontSize: '0.75rem',
        border: '1px solid var(--border-light)'
      }}>
        <ShieldAlert size={14} color="var(--accent-primary)" />
        <span className="font-bold">AI Analysis Overlay</span>
      </div>
    </div>
  );
};
