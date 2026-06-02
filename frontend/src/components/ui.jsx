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

// Inline markdown: `code`, **bold**, ~~strike~~, *italic*/_italic_,
// [text](url), bare URLs, and @mentions (incl. @here/@channel/@everyone).
const INLINE =
  /(`[^`]+`)|(\*\*[^*]+\*\*)|(~~[^~]+~~)|(\*[^*\n]+\*)|(_[^_\n]+_)|(\[[^\]]+\]\(https?:\/\/[^\s)]+\))|(https?:\/\/[^\s]+)|(@(?:here|channel|everyone|[a-zA-Z0-9_.\-]{3,30}))/g;

function parseInline(text) {
  const nodes = [];
  let last = 0;
  let m;
  let i = 0;
  INLINE.lastIndex = 0;
  while ((m = INLINE.exec(text))) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    if (m[1]) nodes.push(<code className="md-code" key={i}>{tok.slice(1, -1)}</code>);
    else if (m[2]) nodes.push(<strong key={i}>{tok.slice(2, -2)}</strong>);
    else if (m[3]) nodes.push(<del key={i}>{tok.slice(2, -2)}</del>);
    else if (m[4] || m[5]) nodes.push(<em key={i}>{tok.slice(1, -1)}</em>);
    else if (m[6]) {
      const lm = tok.match(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/);
      nodes.push(
        <a key={i} href={lm[2]} target="_blank" rel="noreferrer">{lm[1]}</a>
      );
    } else if (m[7]) {
      nodes.push(<a key={i} href={tok} target="_blank" rel="noreferrer">{tok}</a>);
    } else if (m[8]) {
      nodes.push(<span className="mention" key={i}>{tok}</span>);
    }
    last = m.index + tok.length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

// Render message content: fenced ```code blocks``` + inline markdown.
export function renderContent(text) {
  if (!text) return null;
  const parts = text.split(/```\n?([\s\S]*?)```/g);
  return parts.map((part, idx) =>
    idx % 2 === 1 ? (
      <pre className="md-pre" key={`p${idx}`}><code>{part}</code></pre>
    ) : (
      <span key={`t${idx}`}>{parseInline(part)}</span>
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
