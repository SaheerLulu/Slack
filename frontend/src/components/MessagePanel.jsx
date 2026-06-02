import { useStore } from '../store';
import Message from './Message';

// Right-side panel that lists messages (used for Pinned and Saved).
export default function MessagePanel({ title, items }) {
  const { setRightPanel } = useStore();
  return (
    <div className="right-panel">
      <div className="rp-header">
        <span>{title}</span>
        <button className="close" onClick={() => setRightPanel(null)}>
          ✕
        </button>
      </div>
      <div className="rp-body">
        {(!items || items.length === 0) && (
          <div className="empty">Nothing here yet.</div>
        )}
        {items?.map((m) => (
          <Message key={m.id} message={m} showThreadLink={false} />
        ))}
      </div>
    </div>
  );
}
