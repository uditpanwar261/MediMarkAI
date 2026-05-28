/**
 * MediMark AI — Canvas Annotation Engine
 * Handles rendering medical images, bounding boxes, segmentation overlays,
 * and interactive drawing of new annotations.
 */

class AnnotationCanvas {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');

    this.image = null;         // HTMLImageElement
    this.imageNaturalW = 0;
    this.imageNaturalH = 0;

    this.annotations = [];     // [{id, label, type, bbox, polygon, confidence, source, verified}]
    this.scale = 1;
    this.offsetX = 0;
    this.offsetY = 0;

    // Drawing state
    this.drawMode = false;
    this.isDrawing = false;
    this.drawStart = null;
    this.drawCurrent = null;

    // Callbacks
    this.onBoxDrawn = null;    // (x_min, y_min, x_max, y_max) normalized
    this.onAnnotationClick = null;

    this._bindEvents();
  }

  // ─── IMAGE LOADING ───────────────────────────────────────────
  loadImage(src) {
    return new Promise((resolve, reject) => {
      const tryLoad = (url, crossOrigin) => {
        const img = new Image();
        if (crossOrigin) img.crossOrigin = crossOrigin;

        img.onload = () => {
          this.image = img;
          this.imageNaturalW = img.naturalWidth;
          this.imageNaturalH = img.naturalHeight;
          this._fitToContainer();
          this.render();
          resolve(img);
        };

        img.onerror = () => {
          // If anonymous CORS failed, retry without crossOrigin
          if (crossOrigin === 'anonymous') {
            tryLoad(url, null);
          } else {
            reject(new Error(`Failed to load image: ${url}`));
          }
        };

        img.src = url;
      };

      // Cloudinary / external URLs: try anonymous first
      const isExternal = src.startsWith('http://') || src.startsWith('https://');
      tryLoad(src, isExternal ? 'anonymous' : 'use-credentials');
    });
  }

  _fitToContainer() {
    const container = this.canvas.parentElement;
    const cw = container.clientWidth;
    const ch = container.clientHeight;

    const scaleX = cw / this.imageNaturalW;
    const scaleY = ch / this.imageNaturalH;
    this.scale = Math.min(scaleX, scaleY, 1) * 0.92;

    this.canvas.width = cw;
    this.canvas.height = ch;

    this.offsetX = (cw - this.imageNaturalW * this.scale) / 2;
    this.offsetY = (ch - this.imageNaturalH * this.scale) / 2;
  }

  // ─── ANNOTATIONS ────────────────────────────────────────────
  setAnnotations(anns) {
    this.annotations = anns.map(a => this._normalizeAnnotation(a));
    this.render();
  }

  addAnnotation(ann) {
    this.annotations.push(this._normalizeAnnotation(ann));
    this.render();
  }

  updateAnnotation(id, ann) {
    const idx = this.annotations.findIndex(a => a.id === id);
    if (idx >= 0) {
      this.annotations[idx] = this._normalizeAnnotation(ann);
      this.render();
    }
  }

  removeAnnotation(id) {
    this.annotations = this.annotations.filter(a => a.id !== id);
    this.render();
  }

  _normalizeAnnotation(a) {
    return {
      id: a.id,
      label: a.label_name || a.label || 'Unknown',
      type: a.annotation_type || 'bounding_box',
      source: a.source || 'manual',
      verified: a.is_verified || false,
      confidence: a.confidence || 0,
      bbox: a.bbox || null,
      segmentation: a.segmentation_data
        ? (typeof a.segmentation_data === 'string'
            ? (() => { try { return JSON.parse(a.segmentation_data); } catch { return null; } })()
            : a.segmentation_data)
        : null,
      notes: a.notes || '',
      severity: a.severity || ''
    };
  }

  // ─── RENDER ─────────────────────────────────────────────────
  render() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // Dark background
    ctx.fillStyle = '#020609';
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    if (!this.image) return;

    // Draw image
    const dw = this.imageNaturalW * this.scale;
    const dh = this.imageNaturalH * this.scale;
    ctx.drawImage(this.image, this.offsetX, this.offsetY, dw, dh);

    // Draw segmentation overlays (behind bboxes)
    this.annotations.forEach(ann => {
      if (ann.type === 'segmentation') this._drawSegmentation(ann);
    });

    // Draw bounding boxes
    this.annotations.forEach(ann => {
      if (ann.type === 'bounding_box' && ann.bbox) this._drawBBox(ann);
    });

    // Draw points
    this.annotations.forEach(ann => {
      if (ann.type === 'point') this._drawPoint(ann);
    });

    // Draw active bounding box being drawn
    if (this.isDrawing && this.drawStart && this.drawCurrent) {
      this._drawActiveBBox();
    }
  }

  _getColor(ann) {
    const COLORS = {
      'Pulmonary Nodule':       '#FF4757',
      'Mass Lesion':            '#FF3742',
      'Ground-glass Opacity':   '#FFA502',
      'Consolidation':          '#2ED573',
      'Pleural Effusion':       '#5352ED',
      'Cardiomegaly':           '#FF6B81',
      'Pneumothorax':           '#ECCC68',
      'Calcification':          '#70A1FF',
      'Atelectasis':            '#FF7F50',
      'Infiltrate':             '#1E90FF',
      'Tumor':                  '#FF1744',
      'Normal':                 '#00E676',
      'Region of Interest':     '#00D4FF',
    };
    if (ann.verified) return '#22c55e';
    return COLORS[ann.label] || '#00D4FF';
  }

  _imageToCanvas(nx, ny) {
    return {
      x: this.offsetX + nx * this.imageNaturalW * this.scale,
      y: this.offsetY + ny * this.imageNaturalH * this.scale
    };
  }

  _drawBBox(ann) {
    const ctx = this.ctx;
    const { bbox } = ann;
    const tl = this._imageToCanvas(bbox.x_min, bbox.y_min);
    const br = this._imageToCanvas(bbox.x_max, bbox.y_max);
    const w = br.x - tl.x;
    const h = br.y - tl.y;
    const color = this._getColor(ann);

    // Shadow/glow
    ctx.shadowColor = color;
    ctx.shadowBlur = ann.verified ? 12 : 6;

    // Box
    ctx.strokeStyle = color;
    ctx.lineWidth = ann.verified ? 2.5 : 1.8;
    ctx.setLineDash(ann.source === 'manual' ? [] : []);
    ctx.strokeRect(tl.x, tl.y, w, h);

    // Fill
    ctx.fillStyle = color + '18';
    ctx.fillRect(tl.x, tl.y, w, h);

    ctx.shadowBlur = 0;
    ctx.setLineDash([]);

    // Corner brackets
    const blen = Math.min(w, h) * 0.18;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    [[tl.x, tl.y, 1, 1], [br.x, tl.y, -1, 1],
     [tl.x, br.y, 1, -1], [br.x, br.y, -1, -1]].forEach(([cx, cy, dx, dy]) => {
      ctx.beginPath();
      ctx.moveTo(cx + dx * blen, cy);
      ctx.lineTo(cx, cy);
      ctx.lineTo(cx, cy + dy * blen);
      ctx.stroke();
    });

    // Label pill
    this._drawLabel(ann, tl.x, tl.y, color);
  }

  _drawLabel(ann, x, y, color) {
    const ctx = this.ctx;
    const conf = ann.confidence ? ` ${(ann.confidence * 100).toFixed(0)}%` : '';
    const verify = ann.verified ? ' ✓' : '';
    const text = `${ann.label}${conf}${verify}`;
    const fontSize = Math.max(10, Math.min(13, this.scale * 18));
    ctx.font = `600 ${fontSize}px 'DM Mono', monospace`;
    const tw = ctx.measureText(text).width;
    const ph = fontSize + 6;
    const pw = tw + 12;
    const lx = Math.max(0, x);
    const ly = Math.max(ph, y) - ph - 2;

    // Pill background
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.roundRect(lx, ly, pw, ph, 4);
    ctx.fill();

    // Text
    ctx.fillStyle = '#080d14';
    ctx.fillText(text, lx + 6, ly + fontSize);
  }

  _drawSegmentation(ann) {
    if (!ann.segmentation) return;
    const ctx = this.ctx;
    const pts = ann.segmentation.polygon_points || ann.segmentation.normalized_points;
    if (!pts || pts.length < 3) return;

    const color = this._getColor(ann);
    const isNorm = ann.segmentation.normalized_points ? true : false;

    ctx.beginPath();
    pts.forEach(([px, py], i) => {
      let cx, cy;
      if (isNorm) {
        const c = this._imageToCanvas(px, py);
        cx = c.x; cy = c.y;
      } else {
        cx = this.offsetX + px * this.scale;
        cy = this.offsetY + py * this.scale;
      }
      i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
    });
    ctx.closePath();

    ctx.fillStyle = color + '30';
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  _drawPoint(ann) {
    if (!ann.bbox) return;
    const ctx = this.ctx;
    const { x_min: nx, y_min: ny } = ann.bbox;
    const c = this._imageToCanvas(nx, ny);
    const color = this._getColor(ann);

    ctx.beginPath();
    ctx.arc(c.x, c.y, 6, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  _drawActiveBBox() {
    const ctx = this.ctx;
    const x = Math.min(this.drawStart.x, this.drawCurrent.x);
    const y = Math.min(this.drawStart.y, this.drawCurrent.y);
    const w = Math.abs(this.drawCurrent.x - this.drawStart.x);
    const h = Math.abs(this.drawCurrent.y - this.drawStart.y);

    ctx.strokeStyle = '#00D4FF';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 3]);
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = '#00D4FF18';
    ctx.fillRect(x, y, w, h);
    ctx.setLineDash([]);

    // Size label
    const imgW = Math.round(w / this.scale);
    const imgH = Math.round(h / this.scale);
    ctx.font = '11px DM Mono, monospace';
    ctx.fillStyle = '#00D4FF';
    ctx.fillText(`${imgW} × ${imgH}px`, x + 4, y - 4);
  }

  // ─── EVENTS ─────────────────────────────────────────────────
  _bindEvents() {
    this.canvas.addEventListener('mousedown', e => this._onMouseDown(e));
    this.canvas.addEventListener('mousemove', e => this._onMouseMove(e));
    this.canvas.addEventListener('mouseup',   e => this._onMouseUp(e));
    this.canvas.addEventListener('mouseleave', () => {
      if (this.isDrawing) { this.isDrawing = false; this.render(); }
    });
    this.canvas.addEventListener('click', e => this._onClick(e));
    this.canvas.addEventListener('wheel', e => this._onWheel(e), { passive: false });

    window.addEventListener('resize', () => {
      if (this.image) { this._fitToContainer(); this.render(); }
    });
  }

  _canvasPos(e) {
    const r = this.canvas.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  _canvasToNorm(cx, cy) {
    return {
      nx: Math.max(0, Math.min(1, (cx - this.offsetX) / (this.imageNaturalW * this.scale))),
      ny: Math.max(0, Math.min(1, (cy - this.offsetY) / (this.imageNaturalH * this.scale)))
    };
  }

  _onMouseDown(e) {
    if (!this.drawMode || !this.image) return;
    const pos = this._canvasPos(e);
    this.isDrawing = true;
    this.drawStart = pos;
    this.drawCurrent = pos;
  }

  _onMouseMove(e) {
    if (!this.isDrawing) return;
    this.drawCurrent = this._canvasPos(e);
    this.render();
  }

  _onMouseUp(e) {
    if (!this.isDrawing || !this.drawMode) return;
    this.isDrawing = false;
    const pos = this._canvasPos(e);
    const start = this._canvasToNorm(this.drawStart.x, this.drawStart.y);
    const end = this._canvasToNorm(pos.x, pos.y);

    const x_min = Math.min(start.nx, end.nx);
    const y_min = Math.min(start.ny, end.ny);
    const x_max = Math.max(start.nx, end.nx);
    const y_max = Math.max(start.ny, end.ny);

    if ((x_max - x_min) > 0.01 && (y_max - y_min) > 0.01) {
      if (typeof this.onBoxDrawn === 'function') {
        this.onBoxDrawn(x_min, y_min, x_max, y_max);
      }
    }

    this.drawStart = null;
    this.drawCurrent = null;
    this.render();
  }

  _onClick(e) {
    if (this.drawMode) return;
    const pos = this._canvasPos(e);
    const norm = this._canvasToNorm(pos.x, pos.y);

    // Hit-test annotations
    for (let i = this.annotations.length - 1; i >= 0; i--) {
      const ann = this.annotations[i];
      if (ann.type === 'bounding_box' && ann.bbox) {
        const { x_min, y_min, x_max, y_max } = ann.bbox;
        if (norm.nx >= x_min && norm.nx <= x_max &&
            norm.ny >= y_min && norm.ny <= y_max) {
          if (typeof this.onAnnotationClick === 'function') {
            this.onAnnotationClick(ann);
          }
          return;
        }
      }
    }
  }

  _onWheel(e) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.85 : 1.18;
    const pos = this._canvasPos(e);
    const oldScale = this.scale;
    this.scale = Math.max(0.1, Math.min(8, this.scale * delta));
    // Zoom toward cursor
    this.offsetX = pos.x - (pos.x - this.offsetX) * (this.scale / oldScale);
    this.offsetY = pos.y - (pos.y - this.offsetY) * (this.scale / oldScale);
    this.render();
    this._updateZoomLabel();
  }

  // ─── ZOOM ────────────────────────────────────────────────────
  zoomIn()   { this.scale = Math.min(8, this.scale * 1.25); this.render(); this._updateZoomLabel(); }
  zoomOut()  { this.scale = Math.max(0.1, this.scale * 0.8); this.render(); this._updateZoomLabel(); }
  zoomReset(){ if (this.image) { this._fitToContainer(); this.render(); this._updateZoomLabel(); } }

  _updateZoomLabel() {
    const el = document.getElementById('zoom-level');
    if (el) el.textContent = `${Math.round(this.scale * 100)}%`;
  }

  setDrawMode(enabled) {
    this.drawMode = enabled;
    this.canvas.style.cursor = enabled ? 'crosshair' : 'default';

    // Show/hide indicator
    let indicator = document.getElementById('draw-mode-indicator');
    if (enabled) {
      if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'draw-mode-indicator';
        indicator.className = 'draw-mode-indicator';
        indicator.textContent = '✏ DRAW MODE — drag to place box';
        this.canvas.parentElement.appendChild(indicator);
      }
    } else {
      indicator?.remove();
    }
  }

  clear() {
    this.image = null;
    this.annotations = [];
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.ctx.fillStyle = '#020609';
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
  }
}
