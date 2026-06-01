import { useState } from 'react';
import { useStore } from '../store';

export default function Login() {
  const { login, register } = useStore();
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (mode === 'login') {
        await login(username.trim(), password);
      } else {
        await register(username.trim(), displayName.trim(), password);
      }
    } catch (err) {
      setError(err.message || 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <h1>Slack-ish</h1>
        <p className="sub">
          {mode === 'login' ? 'Sign in to your workspace' : 'Create your account'}
        </p>
        {error && <div className="error-banner">{error}</div>}

        <label>Username</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoFocus
          placeholder="e.g. ada"
        />

        {mode === 'register' && (
          <>
            <label>Display name</label>
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Ada Lovelace"
            />
          </>
        )}

        <label>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="At least 6 characters"
        />

        <button className="primary" disabled={busy}>
          {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>

        <div className="toggle">
          {mode === 'login' ? (
            <>
              New here?{' '}
              <a onClick={() => { setMode('register'); setError(''); }}>
                Create an account
              </a>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <a onClick={() => { setMode('login'); setError(''); }}>Sign in</a>
            </>
          )}
        </div>
      </form>
    </div>
  );
}
