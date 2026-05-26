/**
 * MediMark AI — Main Application
 * Orchestrates auth, navigation, gallery, annotation workspace,
 * review queue, export, and AI model status views.
 */

// ─── TOAST NOTIFICATIONS ─────────────────────────────────────
function toast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;

  const icons = {
    success: '✓', error: '✕', info: 'ℹ', warning: '⚠'
  };

  el.innerHTML = `
    <span style="font-weight:700;font-size:1rem;color:var(--${
      type === 'success' ? 'green' : type === 'error' ? 'red' :
      type === 'warning' ? 'amber' : 'cyan'
    })">${icons[type]}</span>
    <span>${msg}</span>
  `;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3600);
}

// ─── MODAL ───────────────────────────────────────────────────
function showModal(html) {
  document.getElementById('modal-content').innerHTML = html;
  document.getElementById('modal-overlay').classList.remove('hidden');
}
function hideModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

// ─── UTILITIES ───────────────────────────────────────────────
function formatBytes(b) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// ─── APP STATE ───────────────────────────────────────────────
const State = {
  user: null,
  currentImage: null,
  annotations: [],
  galleryPage: 1,
  drawMode: false,
  pendingFiles: []
};

// ─── CANVAS ENGINE ───────────────────────────────────────────
let canvas;

// ─── AUTH FLOW ───────────────────────────────────────────────
function initAuth() {
  // Tab switching
  document.querySelectorAll('.auth-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.dataset.tab;
      document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
      document.getElementById(`${target}-form`).classList.add('active');
    });
  });

  // Login
  document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type=submit]');
    const loader = btn.querySelector('.btn-loader');
    const errEl = document.getElementById('login-error');
    btn.disabled = true;
    loader.classList.remove('hidden');
    errEl.classList.add('hidden');

    try {
      const data = await API.auth.login(
        document.getElementById('login-email').value,
        document.getElementById('login-password').value
      );
      API.setTokens(data.access_token, data.refresh_token);
      State.user = data.user;
      enterApp();
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove('hidden');
    } finally {
      btn.disabled = false;
      loader.classList.add('hidden');
    }
  });

  // Register
  document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('register-error');
    errEl.classList.add('hidden');

    try {
      const data = await API.auth.register({
        email: document.getElementById('reg-email').value,
        password: document.getElementById('reg-password').value,
        full_name: document.getElementById('reg-name').value,
        role: document.getElementById('reg-role').value,
        institution: document.getElementById('reg-institution').value
      });
      API.setTokens(data.access_token, data.refresh_token);
      State.user = data.user;
      enterApp();
      toast('Account created! Welcome to MediMark AI.', 'success');
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove('hidden');
    }
  });

  // Auto-login if token present
  if (API.isAuthenticated()) {
    API.auth.me().then(user => {
      State.user = user;
      enterApp();
    }).catch(() => {
      API.clearTokens();
    });
  }

  // Logout
  document.getElementById('logout-btn').addEventListener('click', () => {
    API.auth.logout();
    State.user = null;
    document.getElementById('main-app').classList.add('hidden');
    document.getElementById('auth-screen').style.display = '';
  });

  window.addEventListener('mm:logout', () => {
    document.getElementById('main-app').classList.add('hidden');
    document.getElementById('auth-screen').style.display = '';
  });
}

function enterApp() {
  document.getElementById('auth-screen').style.display = 'none';
  document.getElementById('main-app').classList.remove('hidden');

  // Update sidebar user info
  if (State.user) {
    const name = State.user.full_name || 'User';
    document.getElementById('sidebar-user-name').textContent = name;
    document.getElementById('sidebar-user-role').textContent = State.user.role || '';
    document.getElementById('user-avatar').textContent = name[0].toUpperCase();
  }

  loadDashboard();
}

// ─── NAVIGATION ──────────────────────────────────────────────
function initNav() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const view = item.dataset.view;
      navigateTo(view);
    });
  });
}

function navigateTo(view) {
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  document.querySelector(`[data-view="${view}"]`)?.classList.add('active');

  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const viewEl = document.getElementById(`view-${view}`);
  if (viewEl) viewEl.classList.add('active');

  const loaders = {
    dashboard: loadDashboard,
    gallery: loadGallery,
    annotate: () => {}, // Loaded when image is selected
    review: loadReviewQueue,
    export: () => {},
    models: loadModelStatus
  };

  if (loaders[view]) loaders[view]();
}

// ─── DASHBOARD ───────────────────────────────────────────────
async function loadDashboard() {
  try {
    const [stats, recentData] = await Promise.all([
      API.images.stats(),
      API.images.list({ per_page: 5, page: 1 })
    ]);

    document.getElementById('stat-total-images').textContent = stats.total_images || 0;
    document.getElementById('stat-ai-processed').textContent = stats.ai_processed || 0;
    document.getElementById('stat-annotations').textContent = stats.total_annotations || 0;
    document.getElementById('stat-approved').textContent = stats.approved || 0;

    // Recent images
    const container = document.getElementById('recent-images');
    container.innerHTML = '';
    if (!recentData.images?.length) {
      container.innerHTML = `<div class="empty-state"><p>No images yet. Upload your first medical image.</p></div>`;
    } else {
      recentData.images.forEach(img => {
        const el = document.createElement('div');
        el.className = 'recent-item';
        el.innerHTML = `
          <div class="recent-thumb">
            <img src="${API.images.thumbUrl(img.id)}" alt="${img.original_filename}"
                 onerror="this.parentElement.innerHTML='<span>No thumb</span>'" loading="lazy">
          </div>
          <div class="recent-info">
            <div class="recent-name">${img.original_filename}</div>
            <div class="recent-meta">${img.modality || '—'} · ${img.annotation_count || 0} annotations · ${formatDate(img.created_at)}</div>
          </div>
          <span class="status-pill ${img.status}">${img.status.replace('_', ' ')}</span>
        `;
        el.addEventListener('click', () => openImageForAnnotation(img));
        container.appendChild(el);
      });
    }

    // Model status
    loadModelStatusDashboard();
  } catch (err) {
    console.error('Dashboard load error:', err);
  }
}

async function loadModelStatusDashboard() {
  try {
    const status = await API.ai.modelStatus();
    const container = document.getElementById('model-status-display');
    container.innerHTML = '';

    const models = [
      { name: 'YOLO Detector', data: status.yolo },
      { name: 'U-Net Segmentor', data: status.unet }
    ];

    models.forEach(({ name, data }) => {
      const isLive = data?.status === 'loaded';
      const el = document.createElement('div');
      el.className = 'model-status-item';
      el.innerHTML = `
        <span class="model-status-name">${name}</span>
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:0.72rem;font-family:var(--font-mono);color:${isLive ? 'var(--green)' : 'var(--amber)'}">${isLive ? 'LIVE' : 'MOCK'}</span>
          <div class="status-dot ${isLive ? 'active' : 'mock'}"></div>
        </div>
      `;
      container.appendChild(el);
    });
  } catch (_) {}
}

// ─── GALLERY ─────────────────────────────────────────────────
function initGallery() {
  // File input
  document.getElementById('file-upload-input').addEventListener('change', (e) => {
    State.pendingFiles = Array.from(e.target.files);
    if (!State.pendingFiles.length) return;
    showUploadPanel();
    e.target.value = '';
  });

  document.getElementById('confirm-upload-btn').addEventListener('click', processUpload);
  document.getElementById('cancel-upload-btn').addEventListener('click', hideUploadPanel);

  // Filters
  document.getElementById('gallery-filter-status').addEventListener('change', loadGallery);
  document.getElementById('gallery-filter-modality').addEventListener('change', loadGallery);
}

function showUploadPanel() {
  const panel = document.getElementById('upload-panel');
  panel.classList.remove('hidden');
  const fileList = document.getElementById('upload-file-list');
  fileList.innerHTML = State.pendingFiles.map(f => `
    <div class="upload-file-item">
      <span class="upload-file-name">${f.name}</span>
      <span class="upload-file-size">${formatBytes(f.size)}</span>
    </div>
  `).join('');
}

function hideUploadPanel() {
  document.getElementById('upload-panel').classList.add('hidden');
  State.pendingFiles = [];
}

async function processUpload() {
  if (!State.pendingFiles.length) return;
  const btn = document.getElementById('confirm-upload-btn');
  btn.disabled = true;
  btn.textContent = 'Uploading...';

  const modality = document.getElementById('upload-modality').value;
  const bodyPart = document.getElementById('upload-body-part').value;
  const patientId = document.getElementById('upload-patient-id').value;

  let success = 0, failed = 0;

  for (const file of State.pendingFiles) {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('modality', modality);
    fd.append('body_part', bodyPart);
    fd.append('patient_id', patientId);

    try {
      await API.images.upload(fd);
      success++;
    } catch (err) {
      failed++;
      console.error('Upload error:', err);
    }
  }

  btn.disabled = false;
  btn.textContent = 'Upload Selected Files';
  hideUploadPanel();

  if (success) toast(`${success} image(s) uploaded successfully`, 'success');
  if (failed) toast(`${failed} upload(s) failed`, 'error');
  loadGallery();
}

async function loadGallery(page = 1) {
  State.galleryPage = page;
  const statusFilter = document.getElementById('gallery-filter-status').value;
  const modalityFilter = document.getElementById('gallery-filter-modality').value;

  const params = { page, per_page: 24 };
  if (statusFilter) params.status = statusFilter;
  if (modalityFilter) params.modality = modalityFilter;

  const gallery = document.getElementById('image-gallery');
  gallery.innerHTML = `<div class="empty-state"><div class="loader-spinner" style="width:32px;height:32px;border-width:2px"></div></div>`;

  try {
    const data = await API.images.list(params);
    gallery.innerHTML = '';

    if (!data.images?.length) {
      gallery.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1;padding:60px">
          <svg viewBox="0 0 64 64" fill="none" width="48"><circle cx="32" cy="32" r="30" stroke="#2a3a4a" stroke-width="2"/><path d="M20 32 L44 32 M32 20 L32 44" stroke="#2a3a4a" stroke-width="2" stroke-linecap="round"/></svg>
          <p>No images found. Upload your first medical image.</p>
        </div>`;
      return;
    }

    data.images.forEach(img => {
      const card = document.createElement('div');
      card.className = 'gallery-card';
      card.innerHTML = `
        <div class="gallery-thumb">
          <img src="${API.images.thumbUrl(img.id)}" alt="${img.original_filename}"
               loading="lazy"
               onerror="this.parentElement.innerHTML=this.parentElement.innerHTML.replace(this.outerHTML,'<div class=gallery-thumb-placeholder><svg viewBox=\\'0 0 24 24\\' width=\\'28\\' fill=\\'none\\'><rect x=\\'3\\' y=\\'3\\' width=\\'18\\' height=\\'18\\' rx=\\'2\\' stroke=\\'currentColor\\' stroke-width=\\'1.5\\'/><circle cx=\\'8.5\\' cy=\\'8.5\\' r=\\'1.5\\' fill=\\'currentColor\\'/><path d=\\'M21 15l-5-5L5 21\\' stroke=\\'currentColor\\' stroke-width=\\'1.5\\'  stroke-linecap=\\'round\\'/></svg><span>${img.modality}</span></div>')">
          ${img.ai_processed ? '<span class="gallery-ai-badge">AI</span>' : ''}
        </div>
        <div class="gallery-info">
          <div class="gallery-name">${img.original_filename}</div>
          <div class="gallery-meta">
            <span class="gallery-modality">${img.modality || '—'}</span>
            <span class="status-pill ${img.status}">${img.status.replace('_', ' ')}</span>
          </div>
        </div>
      `;
      card.addEventListener('click', () => openImageForAnnotation(img));
      gallery.appendChild(card);
    });

    renderPagination(data.pages, data.current_page, loadGallery);
  } catch (err) {
    gallery.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><p style="color:var(--red)">Failed to load images: ${err.message}</p></div>`;
  }
}

function renderPagination(totalPages, currentPage, loadFn) {
  const container = document.getElementById('gallery-pagination');
  if (!container || totalPages <= 1) { if(container) container.innerHTML = ''; return; }
  container.innerHTML = '';

  const createBtn = (label, page, active = false, disabled = false) => {
    const btn = document.createElement('button');
    btn.className = `page-btn${active ? ' active' : ''}`;
    btn.textContent = label;
    btn.disabled = disabled;
    if (!disabled) btn.addEventListener('click', () => loadFn(page));
    return btn;
  };

  container.appendChild(createBtn('‹', currentPage - 1, false, currentPage <= 1));

  for (let p = 1; p <= totalPages; p++) {
    if (p === 1 || p === totalPages || Math.abs(p - currentPage) <= 2) {
      container.appendChild(createBtn(p, p, p === currentPage));
    } else if (Math.abs(p - currentPage) === 3) {
      const dots = document.createElement('span');
      dots.textContent = '…';
      dots.style.cssText = 'color:var(--text-muted);padding:0 4px;line-height:34px;';
      container.appendChild(dots);
    }
  }

  container.appendChild(createBtn('›', currentPage + 1, false, currentPage >= totalPages));
}

// ─── ANNOTATION WORKSPACE ────────────────────────────────────
async function openImageForAnnotation(img) {
  State.currentImage = img;
  navigateTo('annotate');

  document.getElementById('no-image-selected').classList.add('hidden');
  const workspace = document.getElementById('annotation-workspace');
  workspace.classList.remove('hidden');

  document.getElementById('ws-image-name').textContent = img.original_filename;
  document.getElementById('ws-image-meta').textContent =
    `${img.modality || '—'} · ${img.width || '?'}×${img.height || '?'}px`;

  const statusBadge = document.getElementById('ws-status-badge');
  statusBadge.textContent = img.status.replace('_', ' ');
  statusBadge.className = `status-badge status-pill ${img.status}`;

  // Load image onto canvas
  const loader = document.getElementById('canvas-loader');
  loader.classList.remove('hidden');
  loader.querySelector('span').textContent = 'Loading image...';

  try {
    canvas.clear();
    await canvas.loadImage(`${API.images.fileUrl(img.id)}?t=${Date.now()}`);
    loader.classList.add('hidden');
    loadAnnotations();
  } catch (err) {
    loader.querySelector('span').textContent = 'Failed to load image';
    toast('Could not load image file', 'error');
  }
}

async function loadAnnotations() {
  if (!State.currentImage) return;

  try {
    const data = await API.annotations.list(State.currentImage.id);
    State.annotations = data.annotations || [];
    canvas.setAnnotations(State.annotations);
    renderAnnotationList();
    updateAnnCountBadge();
  } catch (err) {
    toast('Failed to load annotations', 'error');
  }
}

function renderAnnotationList() {
  const container = document.getElementById('annotations-list');
  container.innerHTML = '';

  if (!State.annotations.length) {
    container.innerHTML = `
      <div class="empty-state">
        <p>No annotations yet.</p>
        <p>Click "Run AI Analysis" or draw boxes manually.</p>
      </div>`;
    return;
  }

  State.annotations.forEach(ann => {
    const el = document.createElement('div');
    const isAI = ann.source?.startsWith('ai');
    el.className = `ann-item ${ann.is_verified ? 'verified' : ''} ${isAI ? 'ai-source' : ''}`;
    el.dataset.annId = ann.id;

    const confPct = ann.confidence ? Math.round(ann.confidence * 100) : 0;
    const bboxStr = ann.bbox
      ? `[${ann.bbox.x_min?.toFixed(2)}, ${ann.bbox.y_min?.toFixed(2)}, ${ann.bbox.x_max?.toFixed(2)}, ${ann.bbox.y_max?.toFixed(2)}]`
      : ann.annotation_type;

    el.innerHTML = `
      <div class="ann-header">
        <span class="ann-label">${ann.label_name || 'Unknown'}</span>
        <span class="ann-source-badge ${ann.source || 'manual'}">${(ann.source || 'manual').replace('_', ' ')}</span>
      </div>
      <div class="ann-meta">${bboxStr}${ann.severity ? ' · ' + ann.severity : ''}</div>
      ${ann.confidence ? `
      <div class="ann-confidence">
        <div class="conf-bar-track">
          <div class="conf-bar-fill" style="width:${confPct}%"></div>
        </div>
        <span class="conf-label">${confPct}%</span>
      </div>` : ''}
      <div class="ann-actions">
        <button class="ann-verify-btn ${ann.is_verified ? 'verified-state' : ''}" data-id="${ann.id}">
          ${ann.is_verified ? '✓ Verified' : 'Verify'}
        </button>
        <button class="btn-danger" data-delete="${ann.id}">Delete</button>
      </div>
    `;

    // Verify
    el.querySelector('.ann-verify-btn').addEventListener('click', () => verifyAnnotation(ann.id));
    // Delete
    el.querySelector('[data-delete]').addEventListener('click', () => deleteAnnotation(ann.id));
    // Highlight on canvas
    el.addEventListener('mouseenter', () => highlightAnnotation(ann.id));
    el.addEventListener('mouseleave', () => canvas.render());

    container.appendChild(el);
  });
}

function highlightAnnotation(id) {
  const ann = State.annotations.find(a => a.id === id);
  if (!ann) return;
  canvas.render();
  const ctx = canvas.ctx;
  if (ann.annotation_type === 'bounding_box' && ann.bbox) {
    const tl = canvas._imageToCanvas(ann.bbox.x_min, ann.bbox.y_min);
    const br = canvas._imageToCanvas(ann.bbox.x_max, ann.bbox.y_max);
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 3;
    ctx.setLineDash([]);
    ctx.strokeRect(tl.x, tl.y, br.x - tl.x, br.y - tl.y);
  }
}

function updateAnnCountBadge() {
  document.getElementById('ann-count-badge').textContent = State.annotations.length;
}

async function verifyAnnotation(id) {
  const ann = State.annotations.find(a => a.id === id);
  if (!ann) return;

  try {
    const updated = await API.annotations.update(id, { is_verified: !ann.is_verified });
    const idx = State.annotations.findIndex(a => a.id === id);
    State.annotations[idx] = updated.annotation;
    canvas.updateAnnotation(id, updated.annotation);
    renderAnnotationList();
    toast(updated.annotation.is_verified ? 'Annotation verified ✓' : 'Verification removed', 'success');
  } catch (err) {
    toast('Failed to update annotation', 'error');
  }
}

async function deleteAnnotation(id) {
  try {
    await API.annotations.delete(id);
    State.annotations = State.annotations.filter(a => a.id !== id);
    canvas.removeAnnotation(id);
    renderAnnotationList();
    updateAnnCountBadge();
    toast('Annotation deleted', 'info');
  } catch (err) {
    toast('Failed to delete annotation', 'error');
  }
}

function initAnnotationWorkspace() {
  // AI Analysis button
  document.getElementById('btn-run-ai').addEventListener('click', async () => {
    if (!State.currentImage) return toast('No image selected', 'warning');
    const loader = document.getElementById('canvas-loader');
    loader.classList.remove('hidden');
    loader.querySelector('span').textContent = 'Running AI Analysis...';

    try {
      const result = await API.ai.analyze(State.currentImage.id);
      loader.classList.add('hidden');
      toast(`AI found ${result.annotations_created} annotations in ${result.performance?.total_ms?.toFixed(0)}ms`, 'success');
      loadAnnotations();
      loadDashboard();
    } catch (err) {
      loader.classList.add('hidden');
      toast(`AI analysis failed: ${err.message}`, 'error');
    }
  });

  // Draw mode
  let drawModeActive = false;
  document.getElementById('btn-add-bbox').addEventListener('click', () => {
    drawModeActive = !drawModeActive;
    canvas.setDrawMode(drawModeActive);
    const btn = document.getElementById('btn-add-bbox');
    if (drawModeActive) {
      btn.style.borderColor = 'var(--cyan)';
      btn.style.color = 'var(--cyan)';
    } else {
      btn.style.borderColor = '';
      btn.style.color = '';
    }
  });

  // Canvas box drawn callback
  canvas.onBoxDrawn = (x_min, y_min, x_max, y_max) => {
    // Populate form inputs
    document.getElementById('bb-x1').value = x_min.toFixed(4);
    document.getElementById('bb-y1').value = y_min.toFixed(4);
    document.getElementById('bb-x2').value = x_max.toFixed(4);
    document.getElementById('bb-y2').value = y_max.toFixed(4);

    // Switch to "Add" tab
    document.querySelector('[data-panel="add"]').click();
    canvas.setDrawMode(false);
    drawModeActive = false;
    const btn = document.getElementById('btn-add-bbox');
    btn.style.borderColor = '';
    btn.style.color = '';

    toast('Box drawn! Fill in the label and save.', 'info');
  };

  // Approve all
  document.getElementById('btn-approve-all').addEventListener('click', async () => {
    if (!State.currentImage) return;
    try {
      await API.annotations.approveAll(State.currentImage.id);
      State.currentImage.status = 'approved';
      document.getElementById('ws-status-badge').textContent = 'approved';
      document.getElementById('ws-status-badge').className = 'status-badge status-pill approved';
      toast('All annotations approved ✓', 'success');
      loadAnnotations();
    } catch (err) {
      toast('Approval failed: ' + err.message, 'error');
    }
  });

  // Panel tabs
  document.querySelectorAll('.panel-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.dataset.panel;
      document.querySelectorAll('.panel-content').forEach(p => p.classList.remove('active'));
      document.getElementById(`panel-${target}`).classList.add('active');
    });
  });

  // Save annotation form
  document.getElementById('btn-save-annotation').addEventListener('click', async () => {
    if (!State.currentImage) return toast('No image selected', 'warning');
    const label = document.getElementById('new-label').value.trim();
    if (!label) return toast('Label is required', 'warning');

    const x_min = parseFloat(document.getElementById('bb-x1').value);
    const y_min = parseFloat(document.getElementById('bb-y1').value);
    const x_max = parseFloat(document.getElementById('bb-x2').value);
    const y_max = parseFloat(document.getElementById('bb-y2').value);
    const hasBox = !isNaN(x_min) && !isNaN(y_min) && !isNaN(x_max) && !isNaN(y_max);

    const payload = {
      image_id: State.currentImage.id,
      label_name: label,
      annotation_type: document.getElementById('new-type').value,
      source: 'manual',
      notes: document.getElementById('new-notes').value,
      severity: document.getElementById('new-severity').value || null
    };

    if (hasBox) {
      payload.x_min = x_min;
      payload.y_min = y_min;
      payload.x_max = x_max;
      payload.y_max = y_max;
    }

    try {
      const data = await API.annotations.create(payload);
      State.annotations.push(data.annotation);
      canvas.addAnnotation(data.annotation);
      renderAnnotationList();
      updateAnnCountBadge();
      // Reset form
      ['new-label', 'new-notes', 'bb-x1', 'bb-y1', 'bb-x2', 'bb-y2'].forEach(id => {
        document.getElementById(id).value = '';
      });
      document.getElementById('new-severity').value = '';
      document.querySelector('[data-panel="annotations"]').click();
      toast('Annotation saved', 'success');
    } catch (err) {
      toast('Failed to save: ' + err.message, 'error');
    }
  });

  // Zoom controls
  document.getElementById('zoom-in-btn').addEventListener('click', () => canvas.zoomIn());
  document.getElementById('zoom-out-btn').addEventListener('click', () => canvas.zoomOut());
  document.getElementById('zoom-reset-btn').addEventListener('click', () => canvas.zoomReset());

  // Annotation click → scroll to item in list
  canvas.onAnnotationClick = (ann) => {
    document.querySelector('[data-panel="annotations"]').click();
    const el = document.querySelector(`[data-ann-id="${ann.id}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.style.boxShadow = '0 0 0 2px var(--cyan)';
      setTimeout(() => { el.style.boxShadow = ''; }, 1500);
    }
  };
}

// ─── REVIEW QUEUE ────────────────────────────────────────────
async function loadReviewQueue() {
  const container = document.getElementById('review-list');
  container.innerHTML = `<div class="empty-state"><div class="loader-spinner" style="width:28px;height:28px;border-width:2px"></div></div>`;

  try {
    const data = await API.images.list({ status: 'ai_complete', per_page: 50 });
    container.innerHTML = '';

    if (!data.images?.length) {
      container.innerHTML = `<div class="empty-state"><p>No images pending review. Great job!</p></div>`;
      return;
    }

    data.images.forEach(img => {
      const card = document.createElement('div');
      card.className = 'review-card';
      card.innerHTML = `
        <div class="review-thumb">
          <img src="${API.images.thumbUrl(img.id)}" alt="${img.original_filename}"
               onerror="this.textContent='📷'" loading="lazy">
        </div>
        <div class="review-info">
          <div class="review-name">${img.original_filename}</div>
          <div class="review-detail">
            ${img.modality || '—'} · ${img.annotation_count || 0} AI annotations · Uploaded ${formatDate(img.created_at)}
          </div>
        </div>
        <div class="review-actions">
          <button class="btn-ghost review-open-btn">Review</button>
          <button class="btn-success review-approve-btn" data-id="${img.id}">Quick Approve</button>
        </div>
      `;
      card.querySelector('.review-open-btn').addEventListener('click', () => openImageForAnnotation(img));
      card.querySelector('.review-approve-btn').addEventListener('click', async () => {
        try {
          await API.annotations.approveAll(img.id);
          card.remove();
          toast(`${img.original_filename} approved`, 'success');
        } catch (err) {
          toast('Approval failed', 'error');
        }
      });
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state"><p style="color:var(--red)">Failed to load review queue</p></div>`;
  }
}

// ─── EXPORT ──────────────────────────────────────────────────
function initExport() {
  document.getElementById('btn-export-coco').addEventListener('click', async () => {
    const id = document.getElementById('export-image-id-coco').value.trim();
    if (!id) return toast('Enter an image UUID', 'warning');
    try {
      const data = await API.annotations.exportCoco(id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      downloadBlob(blob, `${id}_coco.json`);
      toast('COCO JSON exported', 'success');
    } catch (err) {
      toast('Export failed: ' + err.message, 'error');
    }
  });

  document.getElementById('btn-export-yolo').addEventListener('click', async () => {
    const id = document.getElementById('export-image-id-yolo').value.trim();
    if (!id) return toast('Enter an image UUID', 'warning');
    try {
      const data = await API.annotations.exportYolo(id);
      const blob = new Blob([data], { type: 'text/plain' });
      downloadBlob(blob, `${id}.txt`);
      toast('YOLO TXT exported', 'success');
    } catch (err) {
      toast('Export failed: ' + err.message, 'error');
    }
  });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ─── MODEL STATUS ────────────────────────────────────────────
async function loadModelStatus() {
  const container = document.getElementById('models-detail-grid');
  container.innerHTML = '';

  try {
    const status = await API.ai.modelStatus();

    const models = [
      {
        name: 'YOLO Detector',
        desc: 'Real-time bounding box detection',
        data: status.yolo,
        details: [
          ['Architecture', 'YOLOv8 / YOLOv5'],
          ['Task', 'Object Detection'],
          ['Input Size', '640×640 px'],
          ['Framework', 'Ultralytics / OpenCV DNN'],
          ['Output', 'Bounding Boxes + Confidence'],
          ['Pathologies', 'Nodules, Masses, Effusions...']
        ]
      },
      {
        name: 'U-Net Segmentor',
        desc: 'Pixel-level segmentation masks',
        data: status.unet,
        details: [
          ['Architecture', 'U-Net Encoder-Decoder'],
          ['Task', 'Semantic Segmentation'],
          ['Input Size', '256×256 px'],
          ['Framework', 'TensorFlow / PyTorch'],
          ['Output', 'Binary Masks + Polygons'],
          ['Post-processing', 'Contour extraction (OpenCV)']
        ]
      }
    ];

    models.forEach(({ name, desc, data, details }) => {
      const isLive = data?.status === 'loaded';
      const card = document.createElement('div');
      card.className = 'model-card';
      card.innerHTML = `
        <div class="model-card-header">
          <div>
            <div class="model-card-name">${name}</div>
            <div style="font-size:0.8rem;color:var(--text-muted);margin-top:2px">${desc}</div>
          </div>
          <span class="model-card-badge ${isLive ? 'badge-live' : 'badge-mock'}">
            ${isLive ? '● LIVE' : '◎ MOCK MODE'}
          </span>
        </div>
        <div class="model-detail-row">
          <span class="model-detail-key">Model Path</span>
          <span class="model-detail-val" style="font-size:0.72rem;max-width:180px;overflow:hidden;text-overflow:ellipsis">${data?.path || '—'}</span>
        </div>
        ${details.map(([k, v]) => `
          <div class="model-detail-row">
            <span class="model-detail-key">${k}</span>
            <span class="model-detail-val">${v}</span>
          </div>
        `).join('')}
        ${!isLive ? `
          <div style="margin-top:14px;padding:12px;background:var(--amber-dim);border:1px solid #f59e0b33;border-radius:var(--radius-md);font-size:0.8rem;color:var(--amber)">
            ⚠ Running in mock mode. Place your model file at <code style="font-family:var(--font-mono)">${data?.path || 'ml_models/'}</code> to enable real inference.
          </div>
        ` : ''}
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state"><p style="color:var(--red)">Failed to load model status: ${err.message}</p></div>`;
  }
}

// ─── INIT ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Initialize canvas
  canvas = new AnnotationCanvas('annotation-canvas');

  // Initialize modal close
  document.getElementById('modal-close-btn').addEventListener('click', hideModal);
  document.getElementById('modal-overlay').addEventListener('click', (e) => {
    if (e.target === document.getElementById('modal-overlay')) hideModal();
  });

  initAuth();
  initNav();
  initGallery();
  initAnnotationWorkspace();
  initExport();
});
