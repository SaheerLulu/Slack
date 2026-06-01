import { useStore } from '../store';
import Message from './Message';
import Composer from './Composer';

export default function ThreadPanel() {
  const { thread, closeThread, sendReply, currentChannelId } = useStore();
  if (!thread) return null;

  return (
    <div className="right-panel">
      <div className="rp-header">
        <span>Thread</span>
        <button className="close" onClick={closeThread}>
          ✕
        </button>
      </div>
      <div className="rp-body">
        <Message message={thread.root} showThreadLink={false} />
        <div
          style={{
            padding: '6px 18px',
            color: '#616061',
            fontSize: 13,
            borderTop: '1px solid #f0f0f0',
          }}
        >
          {thread.replies.length}{' '}
          {thread.replies.length === 1 ? 'reply' : 'replies'}
        </div>
        {thread.replies.map((m) => (
          <Message key={m.id} message={m} showThreadLink={false} />
        ))}
      </div>
      <Composer
        channelId={currentChannelId}
        placeholder="Reply…"
        onSend={(content) =>
          sendReply(thread.root.id, currentChannelId, content)
        }
      />
    </div>
  );
}
