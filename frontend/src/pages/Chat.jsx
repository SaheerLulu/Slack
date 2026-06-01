import { useState } from 'react';
import { useStore } from '../store';
import { Avatar, initials, colorFor, Modal } from '../components/ui';
import Sidebar from '../components/Sidebar';
import MessageList from '../components/MessageList';
import Composer from '../components/Composer';
import ThreadPanel from '../components/ThreadPanel';
import MemberList from '../components/MemberList';
import SearchPanel from '../components/SearchPanel';
import NotificationsBell from '../components/NotificationsBell';

export default function Chat() {
  const {
    user,
    logout,
    workspaces,
    currentWorkspaceId,
    selectWorkspace,
    createWorkspace,
    channels,
    currentChannelId,
    sendMessage,
    joinChannel,
    rightPanel,
    setRightPanel,
    typingByChannel,
    onlineUserIds,
  } = useStore();

  const [showCreateWs, setShowCreateWs] = useState(false);

  const channel = channels.find((c) => c.id === currentChannelId);
  const currentWs = workspaces.find((w) => w.id === currentWorkspaceId);

  const typers = Object.values(typingByChannel[currentChannelId] || {})
    .map((t) => t.displayName)
    .slice(0, 3);

  return (
    <div className={`app ${rightPanel ? 'with-right' : ''}`}>
      {/* Workspace rail */}
      <div className="rail">
        {workspaces.map((w) => (
          <button
            key={w.id}
            className={`ws-btn ${w.id === currentWorkspaceId ? 'active' : ''}`}
            title={w.name}
            onClick={() => selectWorkspace(w.id)}
          >
            {initials(w.name)}
          </button>
        ))}
        <button
          className="ws-btn add"
          title="Create workspace"
          onClick={() => setShowCreateWs(true)}
        >
          +
        </button>
        <div className="spacer" />
        <div className="me" title={`${user.display_name} — sign out`} onClick={logout}
             style={{ background: colorFor(user.id), cursor: 'pointer' }}>
          {initials(user.display_name)}
        </div>
      </div>

      {/* Sidebar */}
      <div className="sidebar">
        <div className="ws-header">
          <span>{currentWs?.name || 'Workspace'}</span>
        </div>
        <Sidebar />
      </div>

      {/* Main column */}
      <div className="main">
        {channel ? (
          <>
            <div className="main-header">
              <span className="title">
                {channel.isDm ? (
                  <>
                    <span
                      className={`presence-dot ${
                        channel.peer && onlineUserIds.has(channel.peer.id)
                          ? 'online'
                          : ''
                      }`}
                      style={{ marginRight: 6 }}
                    />
                    {channel.name}
                  </>
                ) : (
                  <>
                    {channel.isPrivate ? '🔒 ' : '# '}
                    {channel.name}
                  </>
                )}
              </span>
              {channel.topic && <span className="topic">{channel.topic}</span>}
              <span className="spacer" />
              {!channel.isDm && (
                <button
                  className="icon-btn"
                  onClick={() => setRightPanel('members')}
                >
                  👥 Members
                </button>
              )}
              <button className="icon-btn" onClick={() => setRightPanel('search')}>
                🔍 Search
              </button>
              <NotificationsBell />
            </div>

            {channel.isMember ? (
              <>
                <MessageList channelId={channel.id} />
                <div className="typing">
                  {typers.length === 1 && `${typers[0]} is typing…`}
                  {typers.length === 2 && `${typers[0]} and ${typers[1]} are typing…`}
                  {typers.length > 2 && 'Several people are typing…'}
                </div>
                <Composer
                  channelId={channel.id}
                  placeholder={
                    channel.isDm
                      ? `Message ${channel.name}`
                      : `Message #${channel.name}`
                  }
                  onSend={(content, attachmentIds) =>
                    sendMessage(channel.id, content, attachmentIds)
                  }
                />
              </>
            ) : (
              <div className="preview-join">
                <p>You're previewing <strong>#{channel.name}</strong>.</p>
                <button onClick={() => joinChannel(channel.id)}>
                  Join channel
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="empty" style={{ marginTop: 80 }}>
            Select a channel to start chatting.
          </div>
        )}
      </div>

      {/* Right panel */}
      {rightPanel === 'thread' && <ThreadPanel />}
      {rightPanel === 'members' && <MemberList />}
      {rightPanel === 'search' && <SearchPanel />}

      {showCreateWs && (
        <CreateWorkspaceModal
          onClose={() => setShowCreateWs(false)}
          onCreate={createWorkspace}
        />
      )}
    </div>
  );
}

function CreateWorkspaceModal({ onClose, onCreate }) {
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const submit = async () => {
    try {
      await onCreate(name.trim());
      onClose();
    } catch (err) {
      setError(err.message);
    }
  };
  return (
    <Modal title="Create a workspace" onClose={onClose}>
      {error && <div className="error-banner">{error}</div>}
      <label>Workspace name</label>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g. Acme Inc"
        autoFocus
      />
      <div className="actions">
        <button onClick={onClose}>Cancel</button>
        <button className="primary" onClick={submit} disabled={!name.trim()}>
          Create
        </button>
      </div>
    </Modal>
  );
}
