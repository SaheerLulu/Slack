// Thin fetch wrapper that injects the JWT and transparently refreshes it once
// on a 401 before retrying the request.

const ACCESS_KEY = 'slackish.access';
const REFRESH_KEY = 'slackish.refresh';

export function getAccess() {
  return localStorage.getItem(ACCESS_KEY);
}
export function getRefresh() {
  return localStorage.getItem(REFRESH_KEY);
}
export function setTokens({ access, refresh }) {
  if (access) localStorage.setItem(ACCESS_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

let refreshing = null;

async function tryRefresh() {
  const refresh = getRefresh();
  if (!refresh) return false;
  if (!refreshing) {
    refreshing = fetch('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.access) {
          localStorage.setItem(ACCESS_KEY, data.access);
          return true;
        }
        return false;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function request(method, path, body, { isForm = false, retry = true } = {}) {
  const headers = {};
  const access = getAccess();
  if (access) headers.Authorization = `Bearer ${access}`;

  let payload;
  if (isForm) {
    payload = body; // FormData; let the browser set Content-Type
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  const res = await fetch(`/api${path}`, { method, headers, body: payload });

  if (res.status === 401 && retry && (await tryRefresh())) {
    return request(method, path, body, { isForm, retry: false });
  }

  if (res.status === 204) return null;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const message = data?.detail || data?.username?.[0] || data?.password?.[0]
      || 'Request failed';
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b),
  patch: (p, b) => request('PATCH', p, b),
  put: (p, b) => request('PUT', p, b),
  del: (p, b) => request('DELETE', p, b),
  upload: (p, formData) => request('POST', p, formData, { isForm: true }),
};
