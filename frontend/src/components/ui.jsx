// Small shared presentational helpers.

const COLORS = [
  '#4a154b', '#1264a3', '#007a5a', '#e8912d', '#cd2553',
  '#7c3aed', '#0b7285', '#6b3a6b', '#2b6cb0', '#b7791f',
];

export function colorFor(id) {
  return COLORS[(id || 0) % COLORS.length];
}

export function initials(name) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function Avatar({ user, size = 36, className = '' }) {
  const name = user?.display_name || user?.username || '?';
  return (
    <div
      className={`avatar ${className}`}
      style={{
        background: colorFor(user?.id),
        width: size,
        height: size,
        fontSize: size * 0.38,
      }}
      title={name}
    >
      {initials(name)}
    </div>
  );
}

export function formatTime(iso) {
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const time = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  if (sameDay) return time;
  return `${d.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${time}`;
}

// Render message content with @mentions highlighted.
export function renderContent(text) {
  const parts = text.split(/(@[a-zA-Z0-9_.\-]{3,30})/g);
  return parts.map((part, i) =>
    part.startsWith('@') ? (
      <span className="mention" key={i}>
        {part}
      </span>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

export function Modal({ title, children, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}
