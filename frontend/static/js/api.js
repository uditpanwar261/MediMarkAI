/**
 * MediMark AI — API Client
 * JWT-aware REST client with auto-refresh on 401.
 * Handles both local file paths and Cloudinary URLs for images.
 */

const API = (() => {
  const BASE = '/api';
  let _token        = localStorage.getItem('mm_token')   || null;
  let _refreshToken = localStorage.getItem('mm_refresh') || null;

  function setTokens(access, refresh) {
    _token        = access;
    _refreshToken = refresh;
    localStorage.setItem('mm_token',   access);
    if (refresh) localStorage.setItem('mm_refresh', refresh);
  }

  function clearTokens() {
    _token = null; _refreshToken = null;
    localStorage.removeItem('mm_token');
    localStorage.removeItem('mm_refresh');
  }

  function getToken()        { return _token; }
  function isAuthenticated() { return !!_token; }

  async function request(method, path, body = null, opts = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (_token) headers['Authorization'] = `Bearer ${_token}`;

    const config = { method, headers, ...opts };
    if (body instanceof FormData) {
      delete headers['Content-Type'];
      config.body = body;
    } else if (body) {
      config.body = JSON.stringify(body);
    }

    let res = await fetch(`${BASE}${path}`, config);

    // Auto-refresh on 401
    if (res.status === 401 && _refreshToken && path !== '/auth/refresh') {
      const refreshed = await tryRefresh();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${_token}`;
        config.headers = headers;
        res = await fetch(`${BASE}${path}`, config);
      } else {
        clearTokens();
        window.dispatchEvent(new Event('mm:logout'));
        throw new Error('Session expired. Please log in again.');
      }
    }

    if (!res.ok) {
      let errMsg = `HTTP ${res.status}`;
      try { const d = await res.json(); errMsg = d.error || d.message || errMsg; } catch (_) {}
      throw new Error(errMsg);
    }

    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    if (ct.includes('text/'))            return res.text();
    return res.blob();
  }

  async function tryRefresh() {
    try {
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${_refreshToken}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        setTokens(data.access_token, _refreshToken);
        return true;
      }
    } catch (_) {}
    return false;
  }

  // ── AUTH ────────────────────────────────────────────────────
  const auth = {
    login:   (email, password) => request('POST', '/auth/login',    { email, password }),
    register:(data)            => request('POST', '/auth/register',  data),
    me:      ()                => request('GET',  '/auth/me'),
    logout:  ()                => clearTokens(),
  };

  // ── IMAGES ──────────────────────────────────────────────────
  const images = {
    list: (params = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request('GET', `/images/?${qs}`);
    },
    get:    (id) => request('GET', `/images/${id}`),
    delete: (id) => request('DELETE', `/images/${id}`),
    stats:  ()   => request('GET', '/images/stats'),

    upload: (formData) => {
      const headers = {};
      if (_token) headers['Authorization'] = `Bearer ${_token}`;
      return fetch(`${BASE}/images/upload`, {
        method: 'POST', headers, body: formData
      }).then(async r => {
        if (!r.ok) {
          const d = await r.json().catch(() => ({}));
          throw new Error(d.error || `Upload failed: ${r.status}`);
        }
        return r.json();
      });
    },

    /**
     * Returns the best URL to display an image.
     * Priority: Cloudinary URL stored in file_path → API proxy route
     */
    fileUrl: (id, filePath) => {
      // If we already have the Cloudinary URL, use it directly (no auth needed)
      if (filePath && (filePath.startsWith('http://') || filePath.startsWith('https://'))) {
        return filePath;
      }
      // Otherwise go through the API (adds JWT auth header via redirect)
      return `${BASE}/images/${id}/file`;
    },

    thumbUrl: (id, thumbPath) => {
      if (thumbPath && (thumbPath.startsWith('http://') || thumbPath.startsWith('https://'))) {
        return thumbPath;
      }
      return `${BASE}/images/${id}/thumbnail`;
    },
  };

  // ── ANNOTATIONS ─────────────────────────────────────────────
  const annotations = {
    list: (imageId, params = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request('GET', `/annotations/image/${imageId}?${qs}`);
    },
    create:     (data) => request('POST',   '/annotations/',   data),
    update:     (id, data) => request('PUT', `/annotations/${id}`, data),
    delete:     (id) => request('DELETE', `/annotations/${id}`),
    approveAll: (imageId) => request('POST', `/annotations/image/${imageId}/approve`),
    exportCoco: (imageId) => request('GET',  `/annotations/export/${imageId}?format=coco`),
    exportYolo: (imageId) => request('GET',  `/annotations/export/${imageId}?format=yolo`),
  };

  // ── AI ──────────────────────────────────────────────────────
  const ai = {
    analyze:     (imageId, forceRerun = false) =>
                   request('POST', `/ai/analyze/${imageId}`, { force_rerun: forceRerun }),
    results:     (imageId) => request('GET', `/ai/results/${imageId}`),
    modelStatus: ()         => request('GET', '/ai/models/status'),
  };

  return { setTokens, clearTokens, getToken, isAuthenticated, auth, images, annotations, ai };
})();
