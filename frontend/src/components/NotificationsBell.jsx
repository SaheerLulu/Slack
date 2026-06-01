import { useState } from 'react';
import { useStore } from '../store';
import { formatTime } from './ui';

const LABELS = { mention: 'mentioned you', reply: 'replied to you', dm: 'messaged you' };

export default function NotificationsBell() {
  const {
    notifications,
    unreadNotifications,
    markNotificationsRead,
    channels,
    selectChannel,
  } = useStore();
  const [open, setOpen] = useState(false);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && unreadNotifications > 0) markNotificationsRead();
  };

  const goTo = (n) => {
    if (n.channel) selectChannel(n.channel);
    setOpen(false);
  };

  return (
    <div style={{ position: 'relative' }}>
      <button
        className={`icon-btn ${unreadNotifications ? 'has-badge' : ''}`}
        onClick={toggle}
        title="Notifications"
      >
        🔔
        {unreadNotifications > 0 && (
          <span className="dot-badge">{unreadNotifications}</span>
        )}
      </button>
      {open && (
        <div
          className="mention-pop"
          style={{ top: '100%', bottom: 'auto', right: 0, left: 'auto', width: 320 }}
        >
          <div style={{ padding: '10px 16px', fontWeight: 800, borderBottom: '1px solid #eee' }}>
            Notifications
          </div>
          {notifications.length === 0 && (
            <div className="empty">You're all caught up 🎉</div>
          )}
          {notifications.slice(0, 20).map((n) => (
            <div
              key={n.id}
              className={`notif-item ${n.is_read ? '' : 'unread'}`}
              onClick={() => goTo(n)}
              style={{ cursor: 'pointer' }}
            >
              <span className="who">{n.actor?.display_name || 'Someone'}</span>{' '}
              {LABELS[n.type] || 'notified you'}
              <div className="when">{formatTime(n.created_at)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
