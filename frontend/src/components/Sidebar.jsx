import { useState } from 'react';
import { useStore } from '../store';
import { Modal } from './ui';

export default function Sidebar() {
  const {
    channels,
    currentChannelId,
    selectChannel,
    joinChannel,
    members,
    user,
    onlineUserIds,
    openDm,
    createChannel,
    openGroupDm,
  } = useStore();

  const [showCreate, setShowCreate] = useState(false);
  const [showGroup, setShowGroup] = useState(false);

  const publicChannels = channels.filter((c) => !c.isDm);
  const dms = channels.filter((c) => c.isDm);

  return (
    <>
      <div className="scroll">
        <div className="section">
          <span>Channels</span>
          <button title="Create channel" onClick={() => setShowCreate(true)}>
            +
          </button>
        </div>
        {publicChannels.map((c) => (
          <div
            key={c.id}
            className={`chan ${c.id === currentChannelId ? 'active' : ''} ${
              c.unread && !c.muted ? 'unread' : ''
            } ${c.muted ? 'muted' : ''}`}
            onClick={() => (c.isMember ? selectChannel(c.id) : joinChannel(c.id))}
          >
            <span className="hash">{c.isPrivate ? '🔒' : '#'}</span>
            <span className="name">{c.name}</span>
            {c.muted && <span className="mute-icon">🔕</span>}
            {c.unread > 0 && !c.muted && <span className="badge">{c.unread}</span>}
          </div>
        ))}

        <div className="section" style={{ marginTop: 12 }}>
          <span>Direct messages</span>
          <button title="New group message" onClick={() => setShowGroup(true)}>
            +
          </button>
        </div>
        {dms.map((c) => (
          <div
            key={c.id}
            className={`chan ${c.id === currentChannelId ? 'active' : ''} ${
              c.unread && !c.muted ? 'unread' : ''
            }`}
            onClick={() => selectChannel(c.id)}
          >
            <span
              className={`presence-dot ${
                c.peer && onlineUserIds.has(c.peer.id) ? 'online' : ''
              }`}
            />
            <span className="name">{c.isGroup ? `👥 ${c.name}` : c.name}</span>
            {c.unread > 0 && !c.muted && <span className="badge">{c.unread}</span>}
          </div>
        ))}

        <div className="section" style={{ marginTop: 12 }}>
          <span>People</span>
        </div>
        {members
          .filter((m) => m.id !== user.id)
          .map((m) => (
            <div key={m.id} className="chan" onClick={() => openDm(m.id)}>
              <span
                className={`presence-dot ${
                  onlineUserIds.has(m.id) ? 'online' : ''
                }`}
              />
              <span className="name">{m.display_name}</span>
            </div>
          ))}
      </div>

      {showCreate && (
        <CreateChannelModal
          onClose={() => setShowCreate(false)}
          onCreate={createChannel}
        />
      )}
      {showGroup && (
        <GroupDmModal
          members={members.filter((m) => m.id !== user.id)}
          onClose={() => setShowGroup(false)}
          onCreate={openGroupDm}
        />
      )}
    </>
  );
}

function GroupDmModal({ members, onClose, onCreate }) {
  const [selected, setSelected] = useState([]);
  const [error, setError] = useState('');

  const toggle = (id) =>
    setSelected((s) =>
      s.includes(id) ? s.filter((x) => x !== id) : [...s, id]
    );

  const submit = async () => {
    setError('');
    try {
      await onCreate(selected);
      onClose();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Modal title="New group message" onClose={onClose}>
      {error && <div className="error-banner">{error}</div>}
      <p style={{ color: 'var(--muted)', marginTop: 0 }}>
        Pick 2 or more people for a group conversation.
      </p>
      <div style={{ maxHeight: 280, overflowY: 'auto' }}>
        {members.map((m) => (
          <label key={m.id} className="checkbox" style={{ padding: '6px 0' }}>
            <input
              type="checkbox"
              checked={selected.includes(m.id)}
              onChange={() => toggle(m.id)}
            />
            <span>{m.display_name}</span>
          </label>
        ))}
      </div>
      <div className="actions">
        <button onClick={onClose}>Cancel</button>
        <button
          className="primary"
          onClick={submit}
          disabled={selected.length < 2}
        >
          Start ({selected.length})
        </button>
      </div>
    </Modal>
  );
}

function CreateChannelModal({ onClose, onCreate }) {
  const [name, setName] = useState('');
  const [topic, setTopic] = useState('');
  const [isPrivate, setIsPrivate] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setError('');
    try {
      await onCreate(name.trim().toLowerCase(), topic.trim(), isPrivate);
      onClose();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Modal title="Create a channel" onClose={onClose}>
      {error && <div className="error-banner">{error}</div>}
      <label>Name</label>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g. marketing"
        autoFocus
      />
      <label>Topic (optional)</label>
      <input
        type="text"
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
        placeholder="What's this channel about?"
      />
      <div className="checkbox">
        <input
          type="checkbox"
          id="private"
          checked={isPrivate}
          onChange={(e) => setIsPrivate(e.target.checked)}
        />
        <label htmlFor="private" style={{ margin: 0 }}>
          Make private
        </label>
      </div>
      <div className="actions">
        <button onClick={onClose}>Cancel</button>
        <button className="primary" onClick={submit} disabled={!name.trim()}>
          Create
        </button>
      </div>
    </Modal>
  );
}
