import React, { useState, useMemo, useEffect } from 'react';
import type { ClaimEvidenceItem } from '../../types/claim';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import {
  Camera,
  Video,
  CreditCard,
  FileText,
  Search,
  Grid,
  List,
  Eye,
  ExternalLink,
  Download,
  X,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Calendar,
  CheckCircle2,
  Layers,
  Sparkles,
} from 'lucide-react';

interface AgentEvidenceViewerProps {
  evidence: ClaimEvidenceItem[];
  claimId: string;
  claimVehicle?: string;
  customerName?: string;
  onOpenDamageAnalysis?: () => void;
}

type CategoryFilter = 'all' | 'photo' | 'video' | 'dl' | 'doc';

export const AgentEvidenceViewer: React.FC<AgentEvidenceViewerProps> = ({
  evidence = [],
  claimId,
  claimVehicle,
  customerName,
  onOpenDamageAnalysis,
}) => {
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedItemIndex, setSelectedItemIndex] = useState<number | null>(null);

  // Zoom & Rotation state for modal preview
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [rotationAngle, setRotationAngle] = useState<number>(0);

  // Reset zoom & rotation when inspecting a different item
  useEffect(() => {
    setZoomLevel(1);
    setRotationAngle(0);
  }, [selectedItemIndex]);

  // Keyboard navigation inside modal
  useEffect(() => {
    if (selectedItemIndex === null) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedItemIndex(null);
      } else if (e.key === 'ArrowLeft') {
        setSelectedItemIndex((prev) => (prev !== null && prev > 0 ? prev - 1 : filteredItems.length - 1));
      } else if (e.key === 'ArrowRight') {
        setSelectedItemIndex((prev) => (prev !== null && prev < filteredItems.length - 1 ? prev + 1 : 0));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedItemIndex]);

  // Categorization helpers
  const isVideoCategory = (cat?: string) => {
    const c = (cat || '').toLowerCase();
    return c === 'video' || c === 'walkaround_video' || c.includes('video');
  };

  const isDlCategory = (cat?: string) => {
    const c = (cat || '').toLowerCase();
    return c === 'dl_front' || c === 'dl_back' || c.includes('dl') || c.includes('license');
  };

  const isPhotoCategory = (cat?: string) => {
    const c = (cat || '').toLowerCase();
    return c === 'photo' || c === 'damage_photo' || (!isVideoCategory(c) && !isDlCategory(c) && !c.includes('doc'));
  };

  // Counts by category
  const stats = useMemo(() => {
    let photos = 0;
    let videos = 0;
    let licenses = 0;
    let docs = 0;

    evidence.forEach((item) => {
      if (isVideoCategory(item.category)) videos++;
      else if (isDlCategory(item.category)) licenses++;
      else if (item.category?.includes('doc') || item.category === 'document') docs++;
      else photos++;
    });

    return { total: evidence.length, photos, videos, licenses, docs };
  }, [evidence]);

  // Filtering
  const filteredItems = useMemo(() => {
    return evidence.filter((item) => {
      // Category filter
      if (activeCategory === 'photo' && !isPhotoCategory(item.category)) return false;
      if (activeCategory === 'video' && !isVideoCategory(item.category)) return false;
      if (activeCategory === 'dl' && !isDlCategory(item.category)) return false;
      if (activeCategory === 'doc' && !item.category?.includes('doc') && item.category !== 'document') return false;

      // Text query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const cat = (item.category || '').toLowerCase();
        const type = (item.file_type || '').toLowerCase();
        const url = (item.file_url || '').toLowerCase();
        const id = (item.id || '').toLowerCase();
        return cat.includes(q) || type.includes(q) || url.includes(q) || id.includes(q);
      }

      return true;
    });
  }, [evidence, activeCategory, searchQuery]);

  const activeItem = selectedItemIndex !== null ? filteredItems[selectedItemIndex] : null;

  const getCategoryMeta = (category?: string) => {
    const cat = (category || '').toLowerCase();
    if (cat === 'walkaround_video' || cat === 'video') {
      return {
        label: 'Walkaround Video',
        badgeVariant: 'warning' as const,
        color: '#8b5cf6',
        icon: Video,
        title: '360° Walkaround Video',
      };
    }
    if (cat === 'dl_front') {
      return {
        label: 'DL Front',
        badgeVariant: 'success' as const,
        color: '#10b981',
        icon: CreditCard,
        title: "Driver's License — Front",
      };
    }
    if (cat === 'dl_back') {
      return {
        label: 'DL Back',
        badgeVariant: 'success' as const,
        color: '#10b981',
        icon: CreditCard,
        title: "Driver's License — Back",
      };
    }
    if (cat.includes('doc') || cat === 'document') {
      return {
        label: 'Document',
        badgeVariant: 'neutral' as const,
        color: '#f59e0b',
        icon: FileText,
        title: 'Supporting Document',
      };
    }
    return {
      label: 'Damage Photo',
      badgeVariant: 'neutral' as const,
      color: '#3b82f6',
      icon: Camera,
      title: 'Vehicle Damage Photo',
    };
  };

  const getFormatName = (item: ClaimEvidenceItem) => {
    if (item.file_type) {
      if (item.file_type.includes('mp4')) return 'MP4';
      if (item.file_type.includes('quicktime')) return 'MOV';
      if (item.file_type.includes('png')) return 'PNG';
      if (item.file_type.includes('webp')) return 'WEBP';
      if (item.file_type.includes('pdf')) return 'PDF';
      if (item.file_type.includes('jpeg') || item.file_type.includes('jpg')) return 'JPEG';
    }
    if (isVideoCategory(item.category)) return 'MP4';
    return 'JPG';
  };

  return (
    <div className="flex flex-col gap-md">
      {/* ── Summary & Control Header ── */}
      <Card style={{ padding: '1.25rem 1.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
        <div className="flex justify-between items-center flex-wrap gap-md">
          <div>
            <div className="flex items-center gap-sm">
              <h3 className="text-base font-bold m-0" style={{ color: 'var(--text-primary)' }}>
                Client Uploaded Evidence
              </h3>
              <Badge variant="neutral" style={{ fontWeight: 600 }}>
                {stats.total} total {stats.total === 1 ? 'file' : 'files'}
              </Badge>
            </div>
            <p className="text-xs text-muted mt-1 m-0">
              Verified media and identity documents submitted by {customerName || 'client'} for claim {claimId} {claimVehicle ? `(${claimVehicle})` : ''}.
            </p>
          </div>

          {onOpenDamageAnalysis && (
            <button
              onClick={onOpenDamageAnalysis}
              className="btn btn-secondary btn-sm flex items-center gap-xs"
              style={{ fontSize: '0.8125rem' }}
            >
              <Sparkles size={14} color="var(--accent)" />
              Jump to AI Damage Assessment
            </button>
          )}
        </div>

        {/* ── Category Filter Pills & Search ── */}
        <div className="flex justify-between items-center flex-wrap gap-sm mt-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-xs flex-wrap">
            <button
              className={`agent-evidence-filter-btn ${activeCategory === 'all' ? 'active' : ''}`}
              onClick={() => setActiveCategory('all')}
            >
              <Layers size={13} /> All ({stats.total})
            </button>
            <button
              className={`agent-evidence-filter-btn ${activeCategory === 'photo' ? 'active' : ''}`}
              onClick={() => setActiveCategory('photo')}
            >
              <Camera size={13} /> Photos ({stats.photos})
            </button>
            <button
              className={`agent-evidence-filter-btn ${activeCategory === 'video' ? 'active' : ''}`}
              onClick={() => setActiveCategory('video')}
            >
              <Video size={13} /> Videos ({stats.videos})
            </button>
            <button
              className={`agent-evidence-filter-btn ${activeCategory === 'dl' ? 'active' : ''}`}
              onClick={() => setActiveCategory('dl')}
            >
              <CreditCard size={13} /> Driver License ({stats.licenses})
            </button>
            {stats.docs > 0 && (
              <button
                className={`agent-evidence-filter-btn ${activeCategory === 'doc' ? 'active' : ''}`}
                onClick={() => setActiveCategory('doc')}
              >
                <FileText size={13} /> Documents ({stats.docs})
              </button>
            )}
          </div>

          <div className="flex items-center gap-sm">
            {/* Search */}
            <div style={{ position: 'relative' }}>
              <Search size={13} color="var(--text-secondary)" style={{ position: 'absolute', left: '0.625rem', top: '50%', transform: 'translateY(-50%)' }} />
              <input
                type="text"
                placeholder="Search evidence..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  paddingLeft: '2rem',
                  paddingRight: '0.75rem',
                  paddingTop: '0.3125rem',
                  paddingBottom: '0.3125rem',
                  fontSize: '0.8125rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border)',
                  backgroundColor: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  width: '180px',
                }}
              />
            </div>

            {/* View switcher */}
            <div className="flex items-center" style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
              <button
                title="Grid View"
                onClick={() => setViewMode('grid')}
                style={{
                  background: viewMode === 'grid' ? 'var(--bg-hover)' : 'transparent',
                  border: 'none',
                  padding: '0.375rem 0.5rem',
                  cursor: 'pointer',
                  color: viewMode === 'grid' ? 'var(--text-primary)' : 'var(--text-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <Grid size={14} />
              </button>
              <button
                title="List View"
                onClick={() => setViewMode('list')}
                style={{
                  background: viewMode === 'list' ? 'var(--bg-hover)' : 'transparent',
                  border: 'none',
                  padding: '0.375rem 0.5rem',
                  cursor: 'pointer',
                  color: viewMode === 'list' ? 'var(--text-primary)' : 'var(--text-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <List size={14} />
              </button>
            </div>
          </div>
        </div>
      </Card>

      {/* ── Evidence Cards Grid or List ── */}
      {filteredItems.length === 0 ? (
        <Card style={{ padding: '3rem 1rem', textAlign: 'center', backgroundColor: 'var(--bg-secondary)' }}>
          <div style={{ maxWidth: '320px', margin: '0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: 'var(--bg-hover)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Camera size={24} color="var(--text-secondary)" />
            </div>
            <h4 style={{ margin: 0, fontSize: '0.9375rem', color: 'var(--text-primary)' }}>No Evidence Found</h4>
            <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              {searchQuery ? `No evidence matching "${searchQuery}" in this category.` : 'No files have been registered for this filter.'}
            </p>
            {searchQuery && (
              <button className="btn btn-secondary btn-sm" onClick={() => setSearchQuery('')}>
                Clear Search
              </button>
            )}
          </div>
        </Card>
      ) : viewMode === 'grid' ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: '1rem',
          }}
        >
          {filteredItems.map((item, index) => {
            const meta = getCategoryMeta(item.category);
            const Icon = meta.icon;
            const isVideo = isVideoCategory(item.category);
            const format = getFormatName(item);

            return (
              <div
                key={item.id || index}
                className="agent-evidence-card"
                onClick={() => setSelectedItemIndex(index)}
                style={{
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border)',
                  backgroundColor: 'var(--bg-secondary)',
                  overflow: 'hidden',
                  cursor: 'pointer',
                  transition: 'transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                {/* Media Stage */}
                <div
                  style={{
                    position: 'relative',
                    height: '190px',
                    backgroundColor: '#0a0d14',
                    overflow: 'hidden',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {isVideo ? (
                    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
                      <video
                        src={item.file_url}
                        muted
                        preload="metadata"
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                      <div
                        style={{
                          position: 'absolute',
                          inset: 0,
                          backgroundColor: 'rgba(0,0,0,0.3)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <div
                          style={{
                            width: '44px',
                            height: '44px',
                            borderRadius: '50%',
                            backgroundColor: 'rgba(139, 92, 246, 0.85)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
                          }}
                        >
                          <Video size={20} color="#fff" />
                        </div>
                      </div>
                    </div>
                  ) : (
                    <img
                      src={item.file_url}
                      alt={meta.title}
                      loading="lazy"
                      style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        transition: 'transform 0.3s ease',
                      }}
                      className="agent-evidence-thumbnail"
                    />
                  )}

                  {/* Badges on preview */}
                  <div
                    style={{
                      position: 'absolute',
                      top: '0.625rem',
                      left: '0.625rem',
                      display: 'flex',
                      gap: '0.375rem',
                      zIndex: 2,
                    }}
                  >
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem',
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        backgroundColor: 'rgba(0,0,0,0.7)',
                        backdropFilter: 'blur(4px)',
                        color: meta.color,
                        fontSize: '0.6875rem',
                        fontWeight: 600,
                        border: `1px solid ${meta.color}44`,
                      }}
                    >
                      <Icon size={11} /> {meta.label}
                    </span>
                  </div>

                  <div
                    style={{
                      position: 'absolute',
                      top: '0.625rem',
                      right: '0.625rem',
                      zIndex: 2,
                    }}
                  >
                    <span
                      style={{
                        padding: '0.2rem 0.45rem',
                        borderRadius: '4px',
                        backgroundColor: 'rgba(0,0,0,0.7)',
                        backdropFilter: 'blur(4px)',
                        color: 'var(--text-secondary)',
                        fontSize: '0.6875rem',
                        fontWeight: 600,
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {format}
                    </span>
                  </div>

                  {/* Hover Inspect Overlay */}
                  <div className="agent-evidence-card-overlay">
                    <span
                      className="btn btn-secondary btn-sm"
                      style={{
                        fontSize: '0.75rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                      }}
                    >
                      <Eye size={13} /> Inspect
                    </span>
                  </div>
                </div>

                {/* Card Body */}
                <div style={{ padding: '0.875rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.375rem', flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                      {meta.title} {activeCategory === 'photo' || item.category === 'photo' ? `#${index + 1}` : ''}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: '0.375rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <Calendar size={11} />
                      {item.created_at ? new Date(item.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Verified'}
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: '0.6875rem' }}>
                      {item.id ? (item.id.length > 12 ? `${item.id.slice(0, 8)}...` : item.id) : `ref-${index + 1}`}
                    </span>
                  </div>
                </div>

                {/* Card Actions Footer */}
                <div
                  style={{
                    padding: '0.5rem 0.875rem',
                    backgroundColor: 'var(--bg-primary)',
                    borderTop: '1px solid var(--border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    className="agent-evidence-action-link"
                    onClick={() => setSelectedItemIndex(index)}
                    title="Open Fullscreen Preview"
                  >
                    <Eye size={13} /> Preview
                  </button>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <a
                      href={item.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="agent-evidence-action-link"
                      title="Open in new window"
                    >
                      <ExternalLink size={13} />
                    </a>
                    <a
                      href={item.file_url}
                      download={`evidence-${claimId}-${item.category || 'file'}-${index + 1}`}
                      className="agent-evidence-action-link"
                      title="Download source media"
                    >
                      <Download size={13} />
                    </a>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* ── List View ── */
        <Card style={{ padding: 0, overflow: 'hidden', border: '1px solid var(--border)' }}>
          <div className="table-wrapper" style={{ margin: 0 }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: '80px' }}>Preview</th>
                  <th>Evidence Details</th>
                  <th>Category</th>
                  <th>Format</th>
                  <th>Uploaded</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item, index) => {
                  const meta = getCategoryMeta(item.category);
                  const Icon = meta.icon;
                  const isVideo = isVideoCategory(item.category);
                  const format = getFormatName(item);

                  return (
                    <tr
                      key={item.id || index}
                      className="interactive-row"
                      onClick={() => setSelectedItemIndex(index)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>
                        <div
                          style={{
                            width: '54px',
                            height: '40px',
                            borderRadius: 'var(--radius-sm)',
                            overflow: 'hidden',
                            backgroundColor: '#0a0d14',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            border: '1px solid var(--border)',
                          }}
                        >
                          {isVideo ? (
                            <Video size={16} color="var(--accent)" />
                          ) : (
                            <img
                              src={item.file_url}
                              alt={meta.title}
                              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                            />
                          )}
                        </div>
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>
                          {meta.title} {activeCategory === 'photo' || item.category === 'photo' ? `#${index + 1}` : ''}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {item.id || `evidence-${index + 1}`}
                        </div>
                      </td>
                      <td>
                        <Badge variant={meta.badgeVariant} style={{ fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <Icon size={11} /> {meta.label}
                        </Badge>
                      </td>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                          {format}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                        {item.created_at ? new Date(item.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Verified'}
                      </td>
                      <td style={{ textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                        <div style={{ display: 'inline-flex', gap: '0.5rem', alignItems: 'center' }}>
                          <button
                            className="btn-secondary btn-sm"
                            style={{ padding: '0.25rem 0.5rem' }}
                            onClick={() => setSelectedItemIndex(index)}
                            title="Inspect"
                          >
                            <Eye size={13} />
                          </button>
                          <a
                            href={item.file_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn-secondary btn-sm"
                            style={{ padding: '0.25rem 0.5rem' }}
                            title="Open in new window"
                          >
                            <ExternalLink size={13} />
                          </a>
                          <a
                            href={item.file_url}
                            download={`evidence-${claimId}-${index + 1}`}
                            className="btn-secondary btn-sm"
                            style={{ padding: '0.25rem 0.5rem' }}
                            title="Download"
                          >
                            <Download size={13} />
                          </a>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* ── Interactive Fullscreen / Deep Evidence Inspector Modal ── */}
      {activeItem && selectedItemIndex !== null && (
        <div
          className="agent-evidence-modal-backdrop"
          onClick={() => setSelectedItemIndex(null)}
        >
          <div
            className="agent-evidence-modal-container"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="agent-evidence-modal-header">
              <div className="flex items-center gap-sm">
                <Badge variant={getCategoryMeta(activeItem.category).badgeVariant}>
                  {getCategoryMeta(activeItem.category).label}
                </Badge>
                <span style={{ fontWeight: 600, fontSize: '0.9375rem', color: 'var(--text-primary)' }}>
                  {getCategoryMeta(activeItem.category).title}
                </span>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  ({selectedItemIndex + 1} of {filteredItems.length})
                </span>
              </div>

              <div className="flex items-center gap-sm">
                {/* Steppers */}
                <button
                  className="agent-evidence-btn-icon"
                  title="Previous (Left Arrow)"
                  onClick={() => setSelectedItemIndex((prev) => (prev !== null && prev > 0 ? prev - 1 : filteredItems.length - 1))}
                >
                  <ChevronLeft size={18} />
                </button>
                <button
                  className="agent-evidence-btn-icon"
                  title="Next (Right Arrow)"
                  onClick={() => setSelectedItemIndex((prev) => (prev !== null && prev < filteredItems.length - 1 ? prev + 1 : 0))}
                >
                  <ChevronRight size={18} />
                </button>

                <div style={{ width: '1px', height: '20px', backgroundColor: 'var(--border)' }} />

                {/* External & Download */}
                <a
                  href={activeItem.file_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="agent-evidence-btn-icon"
                  title="Open in new window"
                >
                  <ExternalLink size={16} />
                </a>
                <a
                  href={activeItem.file_url}
                  download={`evidence-${claimId}-${selectedItemIndex + 1}`}
                  className="agent-evidence-btn-icon"
                  title="Download raw file"
                >
                  <Download size={16} />
                </a>

                {/* Close */}
                <button
                  className="agent-evidence-btn-icon"
                  title="Close (Esc)"
                  onClick={() => setSelectedItemIndex(null)}
                  style={{ marginLeft: '0.25rem' }}
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Modal Body: Media Stage & Adjudicator Panel */}
            <div className="agent-evidence-modal-body">
              {/* Media Stage */}
              <div className="agent-evidence-modal-stage">
                {isVideoCategory(activeItem.category) ? (
                  <video
                    src={activeItem.file_url}
                    controls
                    autoPlay
                    playsInline
                    style={{
                      maxWidth: '100%',
                      maxHeight: '100%',
                      borderRadius: 'var(--radius-sm)',
                      boxShadow: '0 8px 30px rgba(0,0,0,0.6)',
                    }}
                  />
                ) : (
                  <div
                    style={{
                      position: 'relative',
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      overflow: 'hidden',
                    }}
                  >
                    <img
                      src={activeItem.file_url}
                      alt={getCategoryMeta(activeItem.category).title}
                      style={{
                        maxWidth: '92%',
                        maxHeight: '92%',
                        objectFit: 'contain',
                        transform: `scale(${zoomLevel}) rotate(${rotationAngle}deg)`,
                        transition: 'transform 0.15s ease-out',
                        borderRadius: 'var(--radius-sm)',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
                      }}
                    />

                    {/* Image Controls Toolbar */}
                    <div className="agent-evidence-stage-toolbar">
                      <button
                        title="Zoom In"
                        onClick={() => setZoomLevel((z) => Math.min(3, z + 0.25))}
                        disabled={zoomLevel >= 3}
                      >
                        <ZoomIn size={15} />
                      </button>
                      <button
                        title="Zoom Out"
                        onClick={() => setZoomLevel((z) => Math.max(0.5, z - 0.25))}
                        disabled={zoomLevel <= 0.5}
                      >
                        <ZoomOut size={15} />
                      </button>
                      <button
                        title="Rotate 90°"
                        onClick={() => setRotationAngle((r) => (r + 90) % 360)}
                      >
                        <RotateCw size={15} />
                      </button>
                      <button
                        title="Reset View"
                        onClick={() => {
                          setZoomLevel(1);
                          setRotationAngle(0);
                        }}
                      >
                        Reset ({Math.round(zoomLevel * 100)}%)
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Inspector Sidebar */}
              <div className="agent-evidence-modal-sidebar">
                <h4 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                  Metadata & Provenance
                </h4>

                <div className="flex flex-col gap-sm" style={{ fontSize: '0.8125rem' }}>
                  <div className="agent-evidence-meta-row">
                    <span className="text-muted">Claim Reference</span>
                    <span className="font-mono">{claimId}</span>
                  </div>
                  <div className="agent-evidence-meta-row">
                    <span className="text-muted">Category</span>
                    <span>{getCategoryMeta(activeItem.category).label}</span>
                  </div>
                  <div className="agent-evidence-meta-row">
                    <span className="text-muted">File Format</span>
                    <span className="font-mono">{getFormatName(activeItem)}</span>
                  </div>
                  <div className="agent-evidence-meta-row">
                    <span className="text-muted">Storage Protocol</span>
                    <span>Supabase Private Storage</span>
                  </div>
                  {activeItem.created_at && (
                    <div className="agent-evidence-meta-row">
                      <span className="text-muted">Uploaded</span>
                      <span>{new Date(activeItem.created_at).toLocaleString()}</span>
                    </div>
                  )}
                  {activeItem.id && (
                    <div className="agent-evidence-meta-row">
                      <span className="text-muted">Evidence UUID</span>
                      <span className="font-mono text-xs">{activeItem.id}</span>
                    </div>
                  )}
                </div>

                <div style={{ marginTop: '0.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
                  <h4 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.375rem', marginBottom: '0.75rem' }}>
                    <CheckCircle2 size={15} color="var(--success)" /> Adjuster Verification
                  </h4>
                  <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                    <li>Confirm damage angle matches incident description.</li>
                    <li>Inspect surrounding vehicle parts for unmentioned scratches.</li>
                    <li>Verify vehicle license plate or registration numbers are legible.</li>
                    <li>Compare lighting and shadows across multiple submitted angles.</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
