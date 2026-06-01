import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { api } from '../api/client';
import { Avatar, formatTime, renderContent } from './ui';

export default function SearchPanel() {
  const { currentWorkspaceId, channels, selectChannel, setRightPanel } =
    useStore();
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      setSearched(false);
      return;
    }
    const t = setTimeout(async () => {
      const data = await api.get(
        `/workspaces/${currentWorkspaceId}/search?q=${encodeURIComponent(q.trim())}`
      );
      setResults(data);
      setSearched(true);
    }, 300);
    return () => clearTimeout(t);
  }, [q, currentWorkspaceId]);

  const channelName = (id) => {
    const c = channels.find((ch) => ch.id === id);
    return c ? c.name : 'channel';
  };

  return (
    <div className="right-panel">
      <div className="rp-header">
        <span>Search</span>
        <button className="close" onClick={() => setRightPanel('search')}>
          ✕
        </button>
      </div>
      <div className="search-box">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search messages…"
          autoFocus
        />
      </div>
      <div className="rp-body">
        {searched && results.length === 0 && (
          <div className="empty">No matching messages.</div>
        )}
        {results.map((m) => (
          <div
            key={m.id}
            className="search-result"
            onClick={() => selectChannel(m.channel)}
          >
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
              <Avatar user={m.user} size={22} />
              <span className="author">{m.user.display_name}</span>
              <span style={{ color: '#616061', fontSize: 12 }}>
                in #{channelName(m.channel)} · {formatTime(m.created_at)}
              </span>
            </div>
            <div className="snippet">{renderContent(m.content)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
