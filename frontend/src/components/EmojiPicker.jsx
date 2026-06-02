import { useState } from 'react';

// A compact, dependency-free emoji picker with categories + search.
const CATEGORIES = {
  'Smileys': '😀 😃 😄 😁 😆 😅 🤣 😂 🙂 🙃 😉 😊 😇 🥰 😍 😘 😋 😛 😜 🤪 🤨 🧐 🤓 😎 🥳 😏 😒 😞 😔 😟 😕 🙁 😣 😖 😫 😩 🥺 😢 😭 😤 😠 😡 🤬 🤯 😳 🥵 🥶 😱 😨 😰 😥 🤗 🤔 🤭 🤫 😬 🙄 😴 🤤 😪 😵 🤐 🥴 🤢 🤮 🤧 😷 🤒 🤕'.split(' '),
  'Gestures': '👍 👎 👌 🤌 🤏 ✌️ 🤞 🤟 🤘 🤙 👈 👉 👆 👇 ☝️ 👋 🤚 🖐️ ✋ 🖖 👏 🙌 🤝 🙏 ✊ 👊 🤛 🤜 💪 🫶 🤲'.split(' '),
  'Hearts': '❤️ 🧡 💛 💚 💙 💜 🖤 🤍 🤎 💔 ❣️ 💕 💞 💓 💗 💖 💘 💝'.split(' '),
  'Objects': '🎉 🎊 🔥 ✨ ⭐ 🌟 💯 ✅ ❌ ❓ ❗ ⚡ 💡 📌 📎 🔔 🚀 🏆 🎯 👀 🍕 ☕ 🍻 🎂 🐛 ✔️ ➕ ➖'.split(' '),
  'Animals': '🐶 🐱 🦊 🐻 🐼 🐨 🦁 🐯 🐮 🐷 🐸 🐵 🐔 🐧 🦄 🐝 🦋 🐢 🐙 🦀'.split(' '),
};

const NAMES = {
  '😀': 'grin happy smile', '😂': 'joy laugh tears', '🤣': 'rofl laugh',
  '😍': 'love heart eyes', '🥳': 'party celebrate', '😎': 'cool sunglasses',
  '😢': 'cry sad', '😭': 'sob cry', '😡': 'angry mad', '🤔': 'thinking',
  '👍': 'thumbs up yes like', '👎': 'thumbs down no', '👌': 'ok perfect',
  '🙏': 'thanks pray please', '👏': 'clap applause', '💪': 'muscle strong',
  '❤️': 'heart love red', '🔥': 'fire lit hot', '🎉': 'party tada celebrate',
  '✅': 'check done yes', '❌': 'x no wrong', '💯': 'hundred perfect',
  '👀': 'eyes look', '🚀': 'rocket launch ship', '🏆': 'trophy win',
  '🍕': 'pizza food', '☕': 'coffee', '🎂': 'cake birthday', '🐛': 'bug',
};

export default function EmojiPicker({ onSelect, onClose }) {
  const [q, setQ] = useState('');
  const query = q.trim().toLowerCase();

  const all = Object.values(CATEGORIES).flat();
  const filtered = query
    ? all.filter((e) => (NAMES[e] || '').includes(query))
    : null;

  return (
    <div className="emoji-picker" onMouseDown={(e) => e.preventDefault()}>
      <input
        className="emoji-search"
        placeholder="Search emoji…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        autoFocus
      />
      <div className="emoji-scroll">
        {filtered ? (
          <div className="emoji-grid">
            {filtered.map((e, i) => (
              <button key={i} className="emoji-btn" onClick={() => onSelect(e)}>
                {e}
              </button>
            ))}
            {filtered.length === 0 && <div className="emoji-empty">No matches</div>}
          </div>
        ) : (
          Object.entries(CATEGORIES).map(([cat, emojis]) => (
            <div key={cat}>
              <div className="emoji-cat">{cat}</div>
              <div className="emoji-grid">
                {emojis.map((e, i) => (
                  <button
                    key={i}
                    className="emoji-btn"
                    onClick={() => onSelect(e)}
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
