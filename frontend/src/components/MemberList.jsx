import { useStore } from '../store';
import { Avatar } from './ui';

export default function MemberList() {
  const { members, onlineUserIds, openDm, user, setRightPanel } = useStore();

  return (
    <div className="right-panel">
      <div className="rp-header">
        <span>Members ({members.length})</span>
        <button className="close" onClick={() => setRightPanel('members')}>
          ✕
        </button>
      </div>
      <div className="rp-body">
        {members.map((m) => (
          <div
            key={m.id}
            className="member-row"
            onClick={() => m.id !== user.id && openDm(m.id)}
          >
            <div style={{ position: 'relative' }}>
              <Avatar user={m} size={32} />
              <span
                className={`presence-dot ${
                  onlineUserIds.has(m.id) ? 'online' : ''
                }`}
              />
            </div>
            <div>
              <div style={{ fontWeight: 600 }}>
                {m.display_name}
                {m.id === user.id && ' (you)'}
              </div>
              <div style={{ color: '#616061', fontSize: 13 }}>
                {onlineUserIds.has(m.id) ? 'Active' : 'Away'}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
