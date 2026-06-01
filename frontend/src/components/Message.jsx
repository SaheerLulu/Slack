import { useState } from 'react';
import { useStore } from '../store';
import { Avatar, formatTime, renderContent } from './ui';

const QUICK_EMOJIS = ['👍', '❤️', '😄', '🎉', '🙌', '👀', '✅'];

export default function Message({ message, showThreadLink = true }) {
  const { user, editMessage, deleteMessage, toggleReaction, openThread } =
    useStore();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const [pickerOpen, setPickerOpen] = useState(false);

  const mine = message.user.id === user.id;

  const saveEdit = async () => {
    if (draft.trim() && draft !== message.content) {
      await editMessage(message.id, draft.trim());
    }
    setEditing(false);
  };

  return (
    <div className="msg">
      <Avatar user={message.user} />
      <div className="body">
        <div className="meta">
          <span className="author">{message.user.display_name}</span>
          <span className="time">{formatTime(message.created_at)}</span>
          {message.edited_at && !message.is_deleted && (
            <span className="edited">(edited)</span>
          )}
        </div>

        {message.is_deleted ? (
          <div className="content deleted">This message was deleted.</div>
        ) : editing ? (
          <div>
            <textarea
              className="edit-area"
              style={{ width: '100%', minHeight: 60 }}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
            />
            <div style={{ marginTop: 6, display: 'flex', gap: 8 }}>
              <button className="icon-btn" onClick={() => setEditing(false)}>
                Cancel
              </button>
              <button className="send" onClick={saveEdit}>
                Save
              </button>
            </div>
          </div>
        ) : (
          <div className="content">{renderContent(message.content)}</div>
        )}

        {/* attachments */}
        {message.attachments?.length > 0 && !message.is_deleted && (
          <div className="attachments">
            {message.attachments.map((a) =>
              a.content_type.startsWith('image/') ? (
                <a key={a.id} href={a.url} target="_blank" rel="noreferrer">
                  <img src={a.url} alt={a.filename} />
                </a>
              ) : (
                <a key={a.id} className="file" href={a.url} target="_blank" rel="noreferrer">
                  📎 {a.filename}
                </a>
              )
            )}
          </div>
        )}

        {/* reactions */}
        {!message.is_deleted && (
          <div className="reactions">
            {(message.reactions || []).map((r) => (
              <button
                key={r.emoji}
                className={`reaction ${
                  r.user_ids.includes(user.id) ? 'mine' : ''
                }`}
                onClick={() => toggleReaction(message, r.emoji)}
              >
                <span>{r.emoji}</span>
                <span>{r.count}</span>
              </button>
            ))}
            <div style={{ position: 'relative' }}>
              <button
                className="reaction add-reaction"
                onClick={() => setPickerOpen((v) => !v)}
              >
                😊+
              </button>
              {pickerOpen && (
                <div className="mention-pop" style={{ width: 'auto', padding: 8, display: 'flex', gap: 4 }}>
                  {QUICK_EMOJIS.map((e) => (
                    <button
                      key={e}
                      className="reaction"
                      onClick={() => {
                        toggleReaction(message, e);
                        setPickerOpen(false);
                      }}
                    >
                      {e}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {showThreadLink && message.reply_count > 0 && (
          <button className="thread-link" onClick={() => openThread(message.id)}>
            💬 {message.reply_count}{' '}
            {message.reply_count === 1 ? 'reply' : 'replies'}
          </button>
        )}
      </div>

      {!message.is_deleted && !editing && (
        <div className="msg-actions">
          {showThreadLink && (
            <button title="Reply in thread" onClick={() => openThread(message.id)}>
              💬
            </button>
          )}
          {mine && (
            <>
              <button title="Edit" onClick={() => { setDraft(message.content); setEditing(true); }}>
                ✏️
              </button>
              <button title="Delete" onClick={() => deleteMessage(message.id)}>
                🗑️
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
