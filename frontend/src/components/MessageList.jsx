import { useEffect, useRef } from 'react';
import { useStore } from '../store';
import Message from './Message';

export default function MessageList({ channelId }) {
  const { messagesByChannel, loadOlder } = useStore();
  const messages = messagesByChannel[channelId] || [];
  const bottomRef = useRef(null);
  const containerRef = useRef(null);
  const prevLen = useRef(0);

  // Auto-scroll to bottom when new messages arrive (if already near bottom).
  useEffect(() => {
    const c = containerRef.current;
    if (!c) return;
    const nearBottom = c.scrollHeight - c.scrollTop - c.clientHeight < 200;
    if (messages.length > prevLen.current && nearBottom) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    prevLen.current = messages.length;
  }, [messages.length]);

  // Jump to bottom on channel switch.
  useEffect(() => {
    bottomRef.current?.scrollIntoView();
    prevLen.current = messages.length;
  }, [channelId]);

  return (
    <div className="messages" ref={containerRef}>
      {messages.length >= 50 && (
        <div className="load-more">
          <button onClick={() => loadOlder(channelId)}>Load earlier messages</button>
        </div>
      )}
      {messages.length === 0 && (
        <div className="empty">
          This is the very beginning of this conversation. Say hi! 👋
        </div>
      )}
      {messages.map((m) => (
        <Message key={m.id} message={m} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
