// Thin wrapper around fetch for the Food Redistribution API.
// Every function returns parsed JSON or throws an ApiError with a readable message.

const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
const TOKEN_KEY = 'fr_token';

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // storage can be blocked (private mode); the session then lasts until reload
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Ignore: nothing useful to do if storage is unavailable.
  }
}

let onUnauthorized = () => {};

/** Registers the function called when the API rejects the current token. */
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** FastAPI returns `detail` as a string, or as a list of validation problems (422). */
function messageFromDetail(detail, fallback) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((problem) => {
      const field = Array.isArray(problem.loc)
        ? problem.loc.filter((part) => part !== 'body').join('.')
        : '';
      const text = String(problem.msg || '').replace(/^Value error, /, '');
      return field ? `${field}: ${text}` : text;
    });
    return parts.filter(Boolean).join('. ') || fallback;
  }
  return fallback;
}

async function request(path, { method = 'GET', body, form, auth = true, handle401 = true } = {}) {
  const headers = {};
  const token = getToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let payload;
  if (form) {
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
    payload = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError('Cannot reach the server. Check your connection and try again.', 0);
  }

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    if (response.status === 401 && auth && handle401) onUnauthorized();
    throw new ApiError(
      messageFromDetail(data?.detail, `Something went wrong (error ${response.status}).`),
      response.status,
    );
  }
  return data;
}

export const api = {
  // Users
  login: (username, password) =>
    request('/users/login', { method: 'POST', form: { username, password }, auth: false }),
  register: (body) => request('/users/register', { method: 'POST', body, auth: false }),
  me: () => request('/users/me'),
  updateMe: (body) => request('/users/me', { method: 'PATCH', body }),
  changePassword: (body) =>
    request('/users/me/change-password', { method: 'POST', body, handle401: false }),
  pendingVerifications: () => request('/users/pending-verifications'),
  verifyOrganization: (userId, approve) =>
    request(`/users/${userId}/verify`, { method: 'POST', body: { approve } }),

  // Donations
  parseDonation: (text) => request('/donations/parse', { method: 'POST', body: { text } }),
  createDonation: (body) => request('/donations', { method: 'POST', body }),
  myDonations: () => request('/donations/mine'),
  donation: (id) => request(`/donations/${id}`),
  updateDonation: (id, body) => request(`/donations/${id}`, { method: 'PATCH', body }),
  cancelDonation: (id) => request(`/donations/${id}`, { method: 'DELETE' }),

  // Matches
  matches: () => request('/matches'),
  match: (id) => request(`/matches/${id}`),
  acceptMatch: (id) => request(`/matches/${id}/accept`, { method: 'POST' }),
  declineMatch: (id) => request(`/matches/${id}/decline`, { method: 'POST' }),
  confirmMatch: (id) => request(`/matches/${id}/confirm`, { method: 'POST' }),
  rejectMatch: (id, recipientAtFault) =>
    request(`/matches/${id}/reject`, {
      method: 'POST',
      body: { recipient_at_fault: recipientAtFault },
    }),

  // Disputes
  createDispute: (matchId, reason) =>
    request('/disputes', { method: 'POST', body: { match_id: matchId, reason } }),
  disputes: () => request('/disputes'),
  resolveDispute: (id) => request(`/disputes/${id}/resolve`, { method: 'POST' }),

  // Notifications, reliability, matching
  notifications: () => request('/notifications'),
  markNotificationRead: (id) => request(`/notifications/${id}/read`, { method: 'POST' }),
  reliability: (userId) => request(`/reliability/${userId}`),
  runMatching: () => request('/matching/run', { method: 'POST' }),
};
