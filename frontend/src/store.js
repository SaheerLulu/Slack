import { create } from 'zustand';
import { api, getAccess, setTokens, clearTokens } from './api/client';

export const useStore = create((set, get) => ({
  // --- auth ---
  user: null,
  authReady: false,

  // --- workspace + channels ---
  workspaces: [],
  currentWorkspaceId: null,
  channels: [],
  currentChannelId: null,

  // --- data caches ---
  messagesByChannel: {}, // { [channelId]: Message[] }
  members: [], // current workspace members
  onlineUserIds: new Set(),
  typingByChannel: {}, // { [channelId]: { [userId]: {displayName, ts} } }

  // --- notifications ---
  notifications: [],
  unreadNotifications: 0,

  // --- thread panel ---
  thread: null, // { root, replies }

  // --- right panel: 'members' | 'search' | 'thread' | null ---
  rightPanel: null,

  // ===================== auth =====================
  async bootstrap() {
    if (!getAccess()) {
      set({ authReady: true });
      return;
    }
    try {
      const user = await api.get('/auth/me');
      set({ user });
      await get().loadWorkspaces();
    } catch {
      clearTokens();
    } finally {
      set({ authReady: true });
    }
  },

  async login(username, password) {
    const data = await api.post('/auth/login', { username, password });
    setTokens(data);
    set({ user: data.user });
    await get().loadWorkspaces();
  },

  async register(username, displayName, password) {
    const data = await api.post('/auth/register', {
      username,
      display_name: displayName,
      password,
    });
    setTokens(data);
    set({ user: data.user });
    await get().loadWorkspaces();
  },

  logout() {
    clearTokens();
    set({
      user: null,
      workspaces: [],
      currentWorkspaceId: null,
      channels: [],
      currentChannelId: null,
      messagesByChannel: {},
      members: [],
      notifications: [],
      unreadNotifications: 0,
      thread: null,
      rightPanel: null,
    });
  },

  // ===================== workspaces =====================
  async loadWorkspaces() {
    const workspaces = await api.get('/workspaces');
    set({ workspaces });
    if (workspaces.length) {
      const current = get().currentWorkspaceId;
      const exists = workspaces.some((w) => w.id === current);
      await get().selectWorkspace(exists ? current : workspaces[0].id);
    }
  },

  async createWorkspace(name) {
    const ws = await api.post('/workspaces', { name });
    set({ workspaces: [...get().workspaces, ws] });
    await get().selectWorkspace(ws.id);
    return ws;
  },

  async selectWorkspace(workspaceId) {
    set({ currentWorkspaceId: workspaceId, currentChannelId: null, thread: null });
    await Promise.all([get().loadChannels(), get().loadMembers()]);
    const { channels } = get();
    const firstJoined = channels.find((c) => c.isMember) || channels[0];
    if (firstJoined) get().selectChannel(firstJoined.id);
  },

  // ===================== channels =====================
  async loadChannels() {
    const channels = await api.get(
      `/workspaces/${get().currentWorkspaceId}/channels`
    );
    set({ channels });
  },

  async createChannel(name, topic, isPrivate) {
    const channel = await api.post(
      `/workspaces/${get().currentWorkspaceId}/channels`,
      { name, topic, isPrivate }
    );
    await get().loadChannels();
    get().selectChannel(channel.id);
    return channel;
  },

  async joinChannel(channelId) {
    await api.post(`/channels/${channelId}/join`);
    await get().loadChannels();
    window.__ws?.subscribe(channelId);
    get().selectChannel(channelId);
  },

  async openDm(userId) {
    const channel = await api.post(
      `/workspaces/${get().currentWorkspaceId}/dm/${userId}`
    );
    await get().loadChannels();
    window.__ws?.subscribe(channel.id);
    get().selectChannel(channel.id);
  },

  async selectChannel(channelId) {
    set({ currentChannelId: channelId, thread: null, rightPanel: null });
    const channel = get().channels.find((c) => c.id === channelId);
    if (channel && !channel.isMember) return; // preview-only until joined
    if (!get().messagesByChannel[channelId]) {
      await get().loadMessages(channelId);
    }
    get().markRead(channelId);
  },

  async loadMessages(channelId) {
    const messages = await api.get(`/channels/${channelId}/messages`);
    set({
      messagesByChannel: { ...get().messagesByChannel, [channelId]: messages },
    });
  },

  async loadOlder(channelId) {
    const existing = get().messagesByChannel[channelId] || [];
    if (!existing.length) return;
    const older = await api.get(
      `/channels/${channelId}/messages?before=${existing[0].id}`
    );
    if (older.length) {
      set({
        messagesByChannel: {
          ...get().messagesByChannel,
          [channelId]: [...older, ...existing],
        },
      });
    }
  },

  async sendMessage(channelId, content, attachmentIds) {
    await api.post(`/channels/${channelId}/messages`, {
      content,
      attachmentIds,
    });
    // The new message arrives via WebSocket and is appended there.
  },

  async sendReply(parentId, channelId, content) {
    await api.post(`/channels/${channelId}/messages`, {
      content,
      parent: parentId,
    });
    await get().openThread(parentId);
  },

  async editMessage(messageId, content) {
    await api.patch(`/messages/${messageId}`, { content });
  },

  async deleteMessage(messageId) {
    await api.del(`/messages/${messageId}`);
  },

  async toggleReaction(message, emoji) {
    const mine = (message.reactions || []).find(
      (r) => r.emoji === emoji && r.user_ids.includes(get().user.id)
    );
    if (mine) {
      await api.del(`/messages/${message.id}/reactions`, { emoji });
      // DELETE with body via fetch wrapper:
    } else {
      await api.put(`/messages/${message.id}/reactions`, { emoji });
    }
  },

  async markRead(channelId) {
    try {
      await api.post(`/channels/${channelId}/read`);
    } catch {
      /* ignore */
    }
    get()._setUnread(channelId, 0);
  },

  _setUnread(channelId, count) {
    set({
      channels: get().channels.map((c) =>
        c.id === channelId ? { ...c, unread: count } : c
      ),
    });
  },

  // ===================== members =====================
  async loadMembers() {
    const members = await api.get(
      `/workspaces/${get().currentWorkspaceId}/members`
    );
    set({ members });
  },

  // ===================== threads =====================
  async openThread(messageId) {
    const thread = await api.get(`/messages/${messageId}/thread`);
    set({ thread, rightPanel: 'thread' });
  },
  closeThread() {
    set({ thread: null, rightPanel: null });
  },

  // ===================== right panel =====================
  setRightPanel(panel) {
    set({ rightPanel: get().rightPanel === panel ? null : panel });
  },

  // ===================== notifications =====================
  async loadNotifications() {
    const data = await api.get('/notifications');
    set({ notifications: data.items, unreadNotifications: data.unread });
  },
  async markNotificationsRead() {
    await api.post('/notifications/read', {});
    set({
      unreadNotifications: 0,
      notifications: get().notifications.map((n) => ({ ...n, is_read: true })),
    });
  },

  // ===================== realtime event handling =====================
  handleWsEvent(event) {
    const state = get();
    switch (event.type) {
      case 'presence': {
        const online = new Set(state.onlineUserIds);
        if (event.online) online.add(event.userId);
        else online.delete(event.userId);
        set({ onlineUserIds: online });
        break;
      }
      case 'presence:init': {
        set({ onlineUserIds: new Set(event.online) });
        break;
      }
      case 'message': {
        state._appendMessage(event.message);
        break;
      }
      case 'message:edit': {
        state._replaceMessage(event.message);
        break;
      }
      case 'message:delete': {
        state._markDeleted(event.channelId, event.messageId);
        break;
      }
      case 'reaction': {
        state._applyReactions(event.messageId, event.reactions);
        break;
      }
      case 'typing': {
        state._setTyping(event.channelId, event.userId, event.displayName);
        break;
      }
      case 'notification': {
        set({
          notifications: [event.notification, ...state.notifications],
          unreadNotifications: state.unreadNotifications + 1,
        });
        break;
      }
      default:
        break;
    }
  },

  _appendMessage(message) {
    const { currentChannelId, messagesByChannel, user, thread } = get();
    // Thread reply → update open thread, not the main list.
    if (message.parent) {
      if (thread && thread.root.id === message.parent) {
        set({
          thread: { ...thread, replies: [...thread.replies, message] },
        });
      }
      // bump reply_count on the parent in the main list
      const list = messagesByChannel[message.channel] || [];
      set({
        messagesByChannel: {
          ...messagesByChannel,
          [message.channel]: list.map((m) =>
            m.id === message.parent
              ? { ...m, reply_count: (m.reply_count || 0) + 1 }
              : m
          ),
        },
      });
      return;
    }

    const list = messagesByChannel[message.channel];
    if (list) {
      if (list.some((m) => m.id === message.id)) return;
      set({
        messagesByChannel: {
          ...messagesByChannel,
          [message.channel]: [...list, message],
        },
      });
    }

    // Unread bump if it's not the active channel and not our own message.
    if (message.channel !== currentChannelId && message.user.id !== user?.id) {
      get()._setUnread(
        message.channel,
        (get().channels.find((c) => c.id === message.channel)?.unread || 0) + 1
      );
    } else if (message.channel === currentChannelId) {
      get().markRead(currentChannelId);
    }
  },

  _replaceMessage(message) {
    const { messagesByChannel, thread } = get();
    const list = messagesByChannel[message.channel];
    if (list) {
      set({
        messagesByChannel: {
          ...messagesByChannel,
          [message.channel]: list.map((m) => (m.id === message.id ? message : m)),
        },
      });
    }
    if (thread) {
      set({
        thread: {
          root: thread.root.id === message.id ? message : thread.root,
          replies: thread.replies.map((m) => (m.id === message.id ? message : m)),
        },
      });
    }
  },

  _markDeleted(channelId, messageId) {
    const { messagesByChannel } = get();
    const list = messagesByChannel[channelId];
    if (!list) return;
    set({
      messagesByChannel: {
        ...messagesByChannel,
        [channelId]: list.map((m) =>
          m.id === messageId ? { ...m, is_deleted: true, content: '' } : m
        ),
      },
    });
  },

  _applyReactions(messageId, reactions) {
    const { messagesByChannel, thread } = get();
    const updated = {};
    for (const [cid, list] of Object.entries(messagesByChannel)) {
      updated[cid] = list.map((m) =>
        m.id === messageId ? { ...m, reactions } : m
      );
    }
    set({ messagesByChannel: updated });
    if (thread) {
      set({
        thread: {
          root:
            thread.root.id === messageId
              ? { ...thread.root, reactions }
              : thread.root,
          replies: thread.replies.map((m) =>
            m.id === messageId ? { ...m, reactions } : m
          ),
        },
      });
    }
  },

  _setTyping(channelId, userId, displayName) {
    if (userId === get().user?.id) return;
    const byChannel = { ...get().typingByChannel };
    byChannel[channelId] = {
      ...(byChannel[channelId] || {}),
      [userId]: { displayName, ts: Date.now() },
    };
    set({ typingByChannel: byChannel });
    // Auto-expire after 4s.
    setTimeout(() => {
      const cur = { ...get().typingByChannel };
      const entry = cur[channelId];
      if (entry && entry[userId] && Date.now() - entry[userId].ts >= 3900) {
        const copy = { ...entry };
        delete copy[userId];
        cur[channelId] = copy;
        set({ typingByChannel: cur });
      }
    }, 4000);
  },
}));
