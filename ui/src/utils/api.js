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

/** Force re-fetch the token (e.g. after a 401). */
function invalidateToken() {
  _token = null;
  _tokenPromise = null;
}

async function _doFetch(method, path, body) {
  const token = await getToken();
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(`${API}${path}`, opts);
  return r;
}

export async function api(method, path, body) {
  try {
    let r = await _doFetch(method, path, body);
    // On 401, the token may be stale — re-fetch and retry once
    if (r.status === 401) {
      invalidateToken();
      r = await _doFetch(method, path, body);
    }
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
