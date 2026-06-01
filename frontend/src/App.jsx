import { useEffect } from 'react';
import { useStore } from './store';
import { ws } from './ws';
import Login from './pages/Login';
import Chat from './pages/Chat';

export default function App() {
  const { user, authReady, bootstrap } = useStore();

  useEffect(() => {
    bootstrap();
  }, []);

  // Manage the WebSocket lifecycle alongside auth.
  useEffect(() => {
    if (user) {
      ws.connect();
      useStore.getState().loadNotifications();
      return () => ws.close();
    }
  }, [user]);

  if (!authReady) {
    return <div className="splash">Loading…</div>;
  }
  return user ? <Chat /> : <Login />;
}
