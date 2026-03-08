/**
 * API Helper — REST calls to Jarvis backend.
 *
 * On first call, fetches a per-session verification token from
 * /api/v1/bootstrap.  All subsequent requests include the token
 * as an Authorization: Bearer header so that only the legitimate
 * Control Center UI can talk to the backend.
 */

const API = "/api/v1";

let _token = null;
let _tokenPromise = null;

export async function getToken() {
  if (_token) return _token;
  if (!_tokenPromise) {
    _tokenPromise = fetch(`${API}/bootstrap`)
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        _token = data?.token || null;
        return _token;
      })
      .catch(() => null);
  }
  return _tokenPromise;
}

export async function api(method, path, body) {
  const token = await getToken();
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  try {
    const r = await fetch(`${API}${path}`, opts);
    if (!r.ok) return { error: `HTTP ${r.status}`, status: r.status };
    const text = await r.text();
    if (!text) return {};
    // Prevent precision loss for large integers (like Discord IDs)
    const safeText = text.replace(/:\s*([0-9]{16,})\b/g, ':"$1"');
    return JSON.parse(safeText);
  } catch (e) {
    console.error(`API ${method} ${path}:`, e);
    return { error: e.message };
  }
}
