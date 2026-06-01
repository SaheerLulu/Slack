import { getAccess } from './api/client';
import { useStore } from './store';

// A small reconnecting WebSocket client. Dispatches server events into the
// store and exposes helpers to send typing/subscribe frames.
class WsClient {
  constructor() {
    this.ws = null;
    this.reconnectDelay = 1000;
    this.shouldRun = false;
    this.pingTimer = null;
  }

  connect() {
    this.shouldRun = true;
    this._open();
  }

  _open() {
    const token = getAccess();
    if (!token) return;
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    this.ws = new WebSocket(`${proto}://${location.host}/ws/?token=${token}`);

    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
      this.pingTimer = setInterval(() => this.send({ type: 'ping' }), 25000);
    };

    this.ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        if (event.type === 'pong') return;
        useStore.getState().handleWsEvent(event);
      } catch {
        /* ignore malformed frames */
      }
    };

    this.ws.onclose = () => {
      clearInterval(this.pingTimer);
      if (!this.shouldRun) return;
      setTimeout(() => this._open(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 15000);
    };

    this.ws.onerror = () => this.ws?.close();
  }

  send(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  typing(channelId) {
    this.send({ type: 'typing', channelId });
  }

  subscribe(channelId) {
    this.send({ type: 'subscribe', channelId });
  }

  close() {
    this.shouldRun = false;
    clearInterval(this.pingTimer);
    this.ws?.close();
    this.ws = null;
  }
}

export const ws = new WsClient();
// Expose for store actions that need to subscribe to new channels.
window.__ws = ws;
