import { useRef, useState } from 'react';
import { useStore } from '../store';
import { api } from '../api/client';
import { ws } from '../ws';
import EmojiPicker from './EmojiPicker';

const SPECIAL_MENTIONS = [
  { id: -1, username: 'here', display_name: 'Notify online members' },
  { id: -2, username: 'channel', display_name: 'Notify the whole channel' },
  { id: -3, username: 'everyone', display_name: 'Notify everyone' },
];

export default function Composer({ channelId, placeholder, onSend }) {
  const { members } = useStore();
  const [text, setText] = useState('');
  const [files, setFiles] = useState([]); // {id, filename}
  const [uploading, setUploading] = useState(false);
  const [mention, setMention] = useState(null); // { query, index }
  const [emojiOpen, setEmojiOpen] = useState(false);
  const taRef = useRef(null);
  const fileRef = useRef(null);
  const lastTyping = useRef(0);

  const mentionMatches = mention
    ? [...SPECIAL_MENTIONS, ...members]
        .filter((m) =>
          m.username.toLowerCase().startsWith(mention.query.toLowerCase()) ||
          m.display_name.toLowerCase().includes(mention.query.toLowerCase())
        )
        .slice(0, 6)
    : [];

  const onChange = (e) => {
    const val = e.target.value;
    setText(val);

    // Typing indicator (throttled to once per 2s).
    if (Date.now() - lastTyping.current > 2000) {
      ws.typing(channelId);
      lastTyping.current = Date.now();
    }

    // Detect "@partial" right before the caret.
    const upto = val.slice(0, e.target.selectionStart);
    const m = upto.match(/@([a-zA-Z0-9_.\-]*)$/);
    setMention(m ? { query: m[1], index: 0 } : null);
  };

  const applyMention = (memberUsername) => {
    const ta = taRef.current;
    const caret = ta.selectionStart;
    const before = text.slice(0, caret).replace(/@([a-zA-Z0-9_.\-]*)$/, `@${memberUsername} `);
    const after = text.slice(caret);
    setText(before + after);
    setMention(null);
    setTimeout(() => ta.focus(), 0);
  };

  const onKeyDown = (e) => {
    if (mention && mentionMatches.length) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMention((m) => ({ ...m, index: (m.index + 1) % mentionMatches.length }));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMention((m) => ({
          ...m,
          index: (m.index - 1 + mentionMatches.length) % mentionMatches.length,
        }));
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        applyMention(mentionMatches[mention.index].username);
        return;
      }
      if (e.key === 'Escape') {
        setMention(null);
        return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const onPickFiles = async (e) => {
    const picked = Array.from(e.target.files || []);
    e.target.value = '';
    setUploading(true);
    try {
      for (const f of picked) {
        const form = new FormData();
        form.append('file', f);
        const res = await api.upload('/files', form);
        setFiles((prev) => [...prev, res]);
      }
    } catch (err) {
      alert(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const submit = async () => {
    const content = text.trim();
    if (!content && files.length === 0) return;
    const attachmentIds = files.map((f) => f.id);
    setText('');
    setFiles([]);
    setMention(null);
    await onSend(content, attachmentIds);
  };

  return (
    <div className="composer">
      <div className="box" style={{ position: 'relative' }}>
        {mention && mentionMatches.length > 0 && (
          <div className="mention-pop">
            {mentionMatches.map((m, i) => (
              <div
                key={m.id}
                className={`item ${i === mention.index ? 'active' : ''}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  applyMention(m.username);
                }}
              >
                <strong>{m.display_name}</strong>
                <span style={{ opacity: 0.7 }}>@{m.username}</span>
              </div>
            ))}
          </div>
        )}
        <textarea
          ref={taRef}
          rows={1}
          value={text}
          onChange={onChange}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
        />
        {files.length > 0 && (
          <div className="pending-files">
            {files.map((f) => (
              <span className="pf" key={f.id}>
                📎 {f.filename}
                <button
                  onClick={() => setFiles((p) => p.filter((x) => x.id !== f.id))}
                  style={{ border: 'none', background: 'none' }}
                >
                  ✕
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="row">
          <button
            className="attach"
            title="Attach file"
            onClick={() => fileRef.current?.click()}
          >
            📎
          </button>
          <div style={{ position: 'relative' }}>
            <button
              className="attach"
              title="Emoji"
              onClick={() => setEmojiOpen((v) => !v)}
            >
              😊
            </button>
            {emojiOpen && (
              <EmojiPicker
                onSelect={(e) => {
                  setText((t) => t + e);
                  setEmojiOpen(false);
                  setTimeout(() => taRef.current?.focus(), 0);
                }}
                onClose={() => setEmojiOpen(false)}
              />
            )}
          </div>
          <input
            ref={fileRef}
            type="file"
            multiple
            hidden
            onChange={onPickFiles}
          />
          {uploading && <span style={{ color: '#888', fontSize: 13 }}>Uploading…</span>}
          <span className="spacer" />
          <button
            className="send"
            disabled={!text.trim() && files.length === 0}
            onClick={submit}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
