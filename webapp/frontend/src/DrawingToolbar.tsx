import { useState } from 'react';
import { Type, Trash2, Lock, Unlock, X, ChevronDown, Edit3 } from 'lucide-react';

export interface DrawingFormatState {
  id: string;
  kind: string;
  fillColor: string;
  fillOpacity: number; // 0 to 100
  borderColor: string;
  borderWidth: number;
  text: string;
  textColor: string;
  fontSize: number;
  bold: boolean;
  locked: boolean;
}

interface DrawingToolbarProps {
  drawing: DrawingFormatState;
  onChange: (changes: Partial<DrawingFormatState>) => void;
  onDelete: () => void;
  onClose: () => void;
}

const TV_COLORS = [
  '#ffffff', '#e0e3eb', '#b2b5be', '#787b86', '#434651', '#2a2e39', '#131722', '#000000',
  '#f23645', '#ff9800', '#ffd700', '#4caf50', '#089981', '#00bcd4', '#2962ff', '#9c27b0',
  '#ff8a80', '#ffd180', '#ffff8d', '#b9f6ca', '#a7ffeb', '#84ffff', '#82b1ff', '#ea80fc',
  '#b71c1c', '#e65100', '#f57f17', '#1b5e20', '#004d40', '#006064', '#0d47a1', '#4a148c'
];

export default function DrawingToolbar({
  drawing,
  onChange,
  onDelete,
  onClose
}: DrawingToolbarProps) {
  const [activeMenu, setActiveMenu] = useState<'fill' | 'border' | 'width' | 'text' | null>(null);

  const isShape = ['rectangle', 'rotated-rectangle', 'circle', 'ellipse', 'triangle'].includes(drawing.kind);

  return (
    <div style={{
      position: 'absolute',
      top: '55px',
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 30,
      backgroundColor: '#181b27',
      border: '1px solid #2a2e39',
      borderRadius: '6px',
      boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
      display: 'flex',
      alignItems: 'center',
      padding: '3px 6px',
      gap: '4px',
      color: '#d1d4dc',
      fontSize: '12px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif'
    }}>
      
      {/* 1. Background Fill Color Picker */}
      {isShape && (
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setActiveMenu(activeMenu === 'fill' ? null : 'fill')}
            style={{
              background: 'transparent',
              border: 'none',
              padding: '6px',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
            title="Background Color & Opacity"
          >
            <div style={{
              width: '18px',
              height: '18px',
              borderRadius: '3px',
              backgroundColor: drawing.fillColor,
              opacity: Math.max(0.2, drawing.fillOpacity / 100),
              border: '1px solid rgba(255,255,255,0.3)',
              boxShadow: 'inset 0 0 2px rgba(0,0,0,0.5)'
            }} />
          </button>

          {activeMenu === 'fill' && (
            <div style={{
              position: 'absolute',
              top: '36px',
              left: '0',
              backgroundColor: '#1e222d',
              border: '1px solid #2a2e39',
              borderRadius: '6px',
              padding: '12px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.7)',
              width: '230px',
              zIndex: 40
            }}>
              <div style={{ fontSize: '11px', color: '#787b86', marginBottom: '8px', fontWeight: 600 }}>
                FILL COLOR
              </div>

              {/* Color Swatch Grid */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(8, 1fr)',
                gap: '5px',
                marginBottom: '14px'
              }}>
                {TV_COLORS.map(c => (
                  <div
                    key={c}
                    onClick={() => {
                      onChange({
                        fillColor: c,
                        fillOpacity: drawing.fillOpacity === 0 ? 20 : drawing.fillOpacity
                      });
                    }}
                    style={{
                      width: '20px',
                      height: '20px',
                      borderRadius: '3px',
                      backgroundColor: c,
                      cursor: 'pointer',
                      border: drawing.fillColor === c ? '2px solid #2962ff' : '1px solid rgba(0,0,0,0.3)',
                      boxSizing: 'border-box'
                    }}
                  />
                ))}
              </div>

              {/* Opacity Slider */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#787b86' }}>
                  <span>Opacity</span>
                  <span style={{ fontWeight: 600, color: '#d1d4dc' }}>{drawing.fillOpacity}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={drawing.fillOpacity}
                  onChange={(e) => onChange({ fillOpacity: parseInt(e.target.value, 10) })}
                  style={{
                    width: '100%',
                    accentColor: '#2962ff',
                    cursor: 'pointer'
                  }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* 2. Border Color Picker */}
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setActiveMenu(activeMenu === 'border' ? null : 'border')}
          style={{
            background: 'transparent',
            border: 'none',
            padding: '6px',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}
          title="Border Color"
        >
          <div style={{
            width: '18px',
            height: '18px',
            borderRadius: '3px',
            border: `2px solid ${drawing.borderColor}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Edit3 size={10} color={drawing.borderColor} />
          </div>
        </button>

        {activeMenu === 'border' && (
          <div style={{
            position: 'absolute',
            top: '36px',
            left: '0',
            backgroundColor: '#1e222d',
            border: '1px solid #2a2e39',
            borderRadius: '6px',
            padding: '12px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.7)',
            width: '230px',
            zIndex: 40
          }}>
            <div style={{ fontSize: '11px', color: '#787b86', marginBottom: '8px', fontWeight: 600 }}>
              BORDER COLOR
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(8, 1fr)',
              gap: '5px'
            }}>
              {TV_COLORS.map(c => (
                <div
                  key={c}
                  onClick={() => onChange({ borderColor: c })}
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '3px',
                    backgroundColor: c,
                    cursor: 'pointer',
                    border: drawing.borderColor === c ? '2px solid #2962ff' : '1px solid rgba(0,0,0,0.3)'
                  }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 3. Border Width Dropdown */}
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setActiveMenu(activeMenu === 'width' ? null : 'width')}
          style={{
            background: 'transparent',
            border: 'none',
            padding: '6px 8px',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            color: '#d1d4dc',
            fontSize: '12px'
          }}
          title="Line Width"
        >
          <span>{drawing.borderWidth}px</span>
          <ChevronDown size={12} color="#787b86" />
        </button>

        {activeMenu === 'width' && (
          <div style={{
            position: 'absolute',
            top: '36px',
            left: '0',
            backgroundColor: '#1e222d',
            border: '1px solid #2a2e39',
            borderRadius: '6px',
            padding: '6px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.7)',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            minWidth: '90px',
            zIndex: 40
          }}>
            {[1, 2, 3, 4].map(w => (
              <button
                key={w}
                onClick={() => {
                  onChange({ borderWidth: w });
                  setActiveMenu(null);
                }}
                style={{
                  background: drawing.borderWidth === w ? 'rgba(41, 98, 255, 0.2)' : 'transparent',
                  color: drawing.borderWidth === w ? '#2962ff' : '#d1d4dc',
                  border: 'none',
                  borderRadius: '3px',
                  padding: '6px 10px',
                  cursor: 'pointer',
                  fontSize: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}
              >
                <span>{w}px</span>
                <div style={{ width: '30px', height: `${w}px`, backgroundColor: '#d1d4dc' }} />
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ width: '1px', height: '18px', background: '#2a2e39', margin: '0 2px' }} />

      {/* 4. Text Label Tool (T) */}
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setActiveMenu(activeMenu === 'text' ? null : 'text')}
          style={{
            background: drawing.text ? 'rgba(41, 98, 255, 0.15)' : 'transparent',
            border: 'none',
            padding: '6px 8px',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            color: drawing.text ? '#2962ff' : '#d1d4dc'
          }}
          title="Add Text Label"
        >
          <Type size={16} />
          {drawing.text && (
            <span style={{ fontSize: '11px', maxWidth: '60px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {drawing.text}
            </span>
          )}
        </button>

        {activeMenu === 'text' && (
          <div style={{
            position: 'absolute',
            top: '36px',
            left: '0',
            backgroundColor: '#1e222d',
            border: '1px solid #2a2e39',
            borderRadius: '6px',
            padding: '12px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.7)',
            width: '260px',
            zIndex: 40,
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            <div style={{ fontSize: '11px', color: '#787b86', fontWeight: 600 }}>
              LABEL TEXT
            </div>

            <input
              type="text"
              autoFocus
              placeholder="e.g. trade, Order Block, Target..."
              value={drawing.text}
              onChange={(e) => onChange({ text: e.target.value })}
              style={{
                background: '#131722',
                border: '1px solid #2a2e39',
                borderRadius: '4px',
                padding: '6px 10px',
                color: '#d1d4dc',
                fontSize: '13px',
                outline: 'none'
              }}
            />

            {/* Font Options */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              {/* Size */}
              <div style={{ display: 'flex', gap: '4px' }}>
                {[12, 14, 16, 20].map(sz => (
                  <button
                    key={sz}
                    onClick={() => onChange({ fontSize: sz })}
                    style={{
                      background: drawing.fontSize === sz ? 'rgba(41, 98, 255, 0.2)' : '#131722',
                      color: drawing.fontSize === sz ? '#2962ff' : '#787b86',
                      border: '1px solid #2a2e39',
                      borderRadius: '3px',
                      padding: '3px 6px',
                      cursor: 'pointer',
                      fontSize: '11px'
                    }}
                  >
                    {sz}
                  </button>
                ))}
              </div>

              {/* Bold */}
              <button
                onClick={() => onChange({ bold: !drawing.bold })}
                style={{
                  background: drawing.bold ? 'rgba(41, 98, 255, 0.2)' : '#131722',
                  color: drawing.bold ? '#2962ff' : '#787b86',
                  border: '1px solid #2a2e39',
                  borderRadius: '3px',
                  padding: '3px 8px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '11px'
                }}
              >
                B
              </button>
            </div>

            {/* Text Color Swatches */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(8, 1fr)',
              gap: '4px'
            }}>
              {['#ffffff', '#ffd700', '#f23645', '#089981', '#2962ff', '#ab47bc', '#ff9800', '#000000'].map(c => (
                <div
                  key={c}
                  onClick={() => onChange({ textColor: c })}
                  style={{
                    width: '18px',
                    height: '18px',
                    borderRadius: '3px',
                    backgroundColor: c,
                    cursor: 'pointer',
                    border: drawing.textColor === c ? '2px solid #2962ff' : '1px solid rgba(0,0,0,0.3)'
                  }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      <div style={{ width: '1px', height: '18px', background: '#2a2e39', margin: '0 2px' }} />

      {/* 5. Lock / Unlock */}
      <button
        onClick={() => onChange({ locked: !drawing.locked })}
        style={{
          background: 'transparent',
          border: 'none',
          padding: '6px',
          borderRadius: '4px',
          cursor: 'pointer',
          color: drawing.locked ? '#ffd700' : '#787b86'
        }}
        title={drawing.locked ? "Unlock Drawing" : "Lock Drawing"}
      >
        {drawing.locked ? <Lock size={15} /> : <Unlock size={15} />}
      </button>

      {/* 6. Trash / Delete */}
      <button
        onClick={onDelete}
        style={{
          background: 'transparent',
          border: 'none',
          padding: '6px',
          borderRadius: '4px',
          cursor: 'pointer',
          color: '#f23645'
        }}
        title="Delete Drawing (Del)"
      >
        <Trash2 size={15} />
      </button>

      {/* 7. Close */}
      <button
        onClick={onClose}
        style={{
          background: 'transparent',
          border: 'none',
          padding: '6px',
          borderRadius: '4px',
          cursor: 'pointer',
          color: '#787b86'
        }}
        title="Close Toolbar"
      >
        <X size={15} />
      </button>

    </div>
  );
}
