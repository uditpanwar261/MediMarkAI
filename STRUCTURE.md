# MediMark AI — Complete Project Structure

```
medimark-ai/                              ← Project root
│
├── app.py                                ← Flask app factory (create_app), entry point
├── manage.py                             ← CLI commands: db-init, seed, create-admin, purge-uploads
├── requirements.txt                      ← All Python dependencies (pip install -r)
├── pytest.ini                            ← Pytest configuration and test discovery
├── gunicorn.conf.py                      ← Gunicorn production server config (workers, timeouts)
├── Dockerfile                            ← Multi-stage Docker image for Flask backend
├── docker-compose.yml                    ← Full stack: MySQL + Flask + Nginx
├── nginx.conf                            ← Nginx reverse proxy config (static files, uploads)
├── .env.example                          ← Environment variable template (copy → .env)
├── .gitignore                            ← Ignores: venv, uploads/, ml_models/*.pt, .env
├── README.md                             ← Full documentation, quickstart, API reference
│
├── backend/                              ← All server-side Python code
│   ├── __init__.py
│   ├── config.py                         ← Config classes: Config, DevelopmentConfig,
│   │                                       ProductionConfig, TestingConfig
│   ├── extensions.py                     ← Flask extension singletons:
│   │                                       db, migrate, jwt, limiter
│   │
│   ├── models/                           ← SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   └── database.py                   ← Models:
│   │                                       • User            (id, email, role, specialty…)
│   │                                       • MedicalImage    (filename, modality, status…)
│   │                                       • Project         (name, target_pathology…)
│   │                                       • LabelClass      (name, color, icd_code…)
│   │                                       • Annotation      (bbox coords, segmentation,
│   │                                                          confidence, is_verified…)
│   │                                       • AIInferenceResult (detections JSON,
│   │                                                            segmentations JSON…)
│   │                                       • AuditLog        (HIPAA-compliant action log)
│   │
│   ├── routes/                           ← Flask Blueprint route handlers
│   │   ├── __init__.py
│   │   ├── auth.py                       ← POST /api/auth/login
│   │   │                                   POST /api/auth/register
│   │   │                                   GET  /api/auth/me
│   │   │                                   POST /api/auth/refresh
│   │   │
│   │   ├── images.py                     ← POST /api/images/upload (multipart)
│   │   │                                   GET  /api/images/
│   │   │                                   GET  /api/images/<id>
│   │   │                                   GET  /api/images/<id>/file
│   │   │                                   GET  /api/images/<id>/thumbnail
│   │   │                                   GET  /api/images/stats
│   │   │                                   DEL  /api/images/<id>
│   │   │
│   │   ├── annotations.py                ← GET  /api/annotations/image/<id>
│   │   │                                   POST /api/annotations/
│   │   │                                   PUT  /api/annotations/<id>
│   │   │                                   DEL  /api/annotations/<id>
│   │   │                                   POST /api/annotations/image/<id>/approve
│   │   │                                   GET  /api/annotations/export/<id>?format=coco|yolo
│   │   │
│   │   ├── ai_inference.py               ← POST /api/ai/analyze/<id>
│   │   │                                   POST /api/ai/batch-analyze
│   │   │                                   GET  /api/ai/results/<id>
│   │   │                                   GET  /api/ai/models/status
│   │   │
│   │   ├── projects.py                   ← GET  /api/projects/
│   │   │                                   POST /api/projects/
│   │   │                                   GET  /api/projects/<id>
│   │   │                                   PUT  /api/projects/<id>
│   │   │                                   POST /api/projects/<id>/label-classes
│   │   │                                   GET  /api/projects/<id>/stats
│   │   │
│   │   ├── users.py                      ← GET  /api/users/           (admin only)
│   │   │                                   GET  /api/users/<id>
│   │   │                                   PUT  /api/users/<id>
│   │   │                                   POST /api/users/<id>/deactivate
│   │   │                                   GET  /api/users/audit-log   (admin only)
│   │   │
│   │   └── dashboard.py                  ← GET / → serves frontend SPA (index.html)
│   │
│   ├── ml_models/                        ← AI inference pipeline
│   │   ├── __init__.py
│   │   ├── yolo_detector.py              ← YOLOMedicalDetector class
│   │   │                                   Backends: ultralytics → OpenCV DNN → mock
│   │   │                                   detect(image) → list of bbox dicts
│   │   │
│   │   ├── unet_segmentor.py             ← UNetSegmentor class
│   │   │                                   Backends: TensorFlow → PyTorch → mock
│   │   │                                   segment(image, bbox) → polygon + mask dicts
│   │   │
│   │   ├── preprocessor.py               ← MedicalImagePreprocessor class
│   │   │                                   load() — DICOM + standard formats
│   │   │                                   enhance() — CLAHE + denoising
│   │   │                                   thumbnail() — 256×256 with padding
│   │   │                                   metadata() — dims, intensity stats
│   │   │                                   process() — full pipeline
│   │   │
│   │   ├── inference_engine.py           ← AIInferenceEngine (orchestrator)
│   │   │                                   Combines YOLO + U-Net in one call
│   │   │                                   process_image(path) → full result dict
│   │   │                                   draw_annotations(path, dets, segs) → BGR img
│   │   │
│   │   └── visualizer.py                 ← Annotation rendering utilities
│   │                                       draw_bbox() — bbox + corner brackets + label
│   │                                       draw_segmentation() — polygon fill + outline
│   │                                       annotate_image() — render all annotations
│   │                                       save_annotated() — save rendered JPEG
│   │
│   └── utils/                            ← Shared helper modules
│       ├── __init__.py
│       ├── security.py                   ← hash_password, verify_password,
│       │                                   sanitize_string, validate_email,
│       │                                   validate_uuid, require_role() decorator,
│       │                                   get_client_ip()
│       │
│       ├── file_helpers.py               ← allowed_file, get_mime_type,
│       │                                   generate_unique_filename, safe_filename,
│       │                                   file_md5 (deduplication), ensure_dir,
│       │                                   human_readable_size
│       │
│       ├── image_utils.py                ← load_image_safe, resize_keep_aspect,
│       │                                   make_thumbnail, apply_clahe,
│       │                                   normalize_bbox, bbox_to_pixels,
│       │                                   compute_iou, contours_to_polygon,
│       │                                   encode_mask_rle, decode_mask_rle
│       │
│       └── responses.py                  ← success(), error(), paginated()
│                                           Standardised JSON response helpers
│
├── frontend/                             ← Single-page application
│   ├── templates/
│   │   └── index.html                    ← SPA shell: auth screen, sidebar,
│   │                                       5 views (dashboard/gallery/annotate/
│   │                                       review/export), modal, toasts
│   │
│   └── static/
│       ├── css/
│       │   └── main.css                  ← 700-line dark clinical design system
│       │                                   CSS variables, sidebar, canvas,
│       │                                   annotation panel, gallery cards,
│       │                                   status pills, toast animations
│       │
│       └── js/
│           ├── api.js                    ← REST API client
│           │                               JWT-aware (auto-refresh on 401)
│           │                               Modules: auth, images, annotations, ai
│           │
│           ├── canvas.js                 ← AnnotationCanvas class
│           │                               loadImage(), setAnnotations(),
│           │                               addAnnotation(), updateAnnotation()
│           │                               Renders: bbox + glow + corners + label
│           │                                        segmentation polygon fill
│           │                                        draw mode (drag to create box)
│           │                               Zoom: wheel + buttons; pan; hit-testing
│           │
│           └── app.js                    ← SPA controller (1000+ lines)
│                                           initAuth() — login / register flow
│                                           initNav() — view switching
│                                           initGallery() — upload + grid + pagination
│                                           loadDashboard() — stats + recent images
│                                           openImageForAnnotation() — full workspace
│                                           loadAnnotations() — fetch + render list
│                                           verifyAnnotation() — doctor sign-off
│                                           deleteAnnotation() — soft delete
│                                           loadReviewQueue() — AI-complete images
│                                           initExport() — COCO + YOLO download
│                                           loadModelStatus() — live/mock indicators
│
├── database/
│   └── init_schema.sql                   ← Full MySQL 8 schema
│                                           7 tables with indexes, FKs, constraints
│                                           Seed: admin user, demo project, 8 label
│                                           classes with ICD-10 codes
│
├── migrations/                           ← Flask-Migrate / Alembic
│   ├── README                            ← Migration usage instructions
│   ├── alembic.ini                       ← Alembic logging config
│   └── env.py                            ← Alembic env connecting to Flask app
│
├── ml_models/                            ← Model weights directory (git-ignored)
│   └── README.md                         ← Instructions: download links, training
│                                           code for YOLO + U-Net, public datasets
│
├── uploads/                              ← Patient image storage (git-ignored)
│   ├── README.txt
│   ├── originals/                        ← Raw uploads, never modified
│   │   └── .gitkeep
│   └── processed/                        ← Thumbnails + enhanced images
│       └── .gitkeep
│
└── tests/                                ← Pytest test suite (56 tests across 6 files)
    ├── __init__.py
    ├── conftest.py                        ← Fixtures: app, db, client, user,
    │                                        admin_user, auth_headers, sample_image_file
    ├── test_auth.py                       ← 9 tests: register, login, JWT, refresh
    ├── test_images.py                     ← 8 tests: upload, list, get, delete, stats
    ├── test_annotations.py                ← 9 tests: bbox, segmentation, update,
    │                                        delete, approve, COCO export, YOLO export
    ├── test_ai_inference.py               ← 7 tests: analyze, caching, force-rerun,
    │                                        results, model status
    ├── test_ml_models.py                  ← 16 tests: YOLO detector, U-Net segmentor,
    │                                        preprocessor (mock backends)
    └── test_projects.py                   ← 7 tests: create, list, get, update,
                                             label classes, stats
```

---

## File Count Summary

| Layer            | Files |
|------------------|-------|
| Backend routes   | 7     |
| Backend models   | 1     |
| ML pipeline      | 5     |
| Utils            | 4     |
| Frontend         | 4     |
| Tests            | 6     |
| Database         | 1     |
| DevOps           | 6     |
| Config / Root    | 8     |
| **Total**        | **56** |

---

## Data Flow

```
Doctor uploads image
       │
       ▼
POST /api/images/upload
  └─ OpenCV reads dims → thumbnail generated → saved to MySQL
       │
       ▼
POST /api/ai/analyze/<id>
  └─ MedicalImagePreprocessor.process()
       └─ YOLOMedicalDetector.detect()    → bounding boxes
       └─ UNetSegmentor.segment()         → polygon masks
       └─ AIInferenceResult saved (JSON)
       └─ Annotation rows auto-created
       │
       ▼
GET /api/annotations/image/<id>
  └─ Frontend canvas renders boxes + overlays
       │
       ▼
Doctor adjusts / verifies via canvas draw mode
  └─ PUT /api/annotations/<id>  { is_verified: true }
       │
       ▼
POST /api/annotations/image/<id>/approve
  └─ Image status → "approved"
       │
       ▼
GET /api/annotations/export/<id>?format=coco|yolo
  └─ Training-ready labels downloaded
```

---

## API Endpoint Map

```
/api/auth/
  POST  /login           → { access_token, refresh_token, user }
  POST  /register        → { access_token, refresh_token, user }
  GET   /me              → user object
  POST  /refresh         → { access_token }

/api/images/
  POST  /upload          → { image }   multipart/form-data
  GET   /                → { images[], total, pages }
  GET   /<id>            → { ...image, annotations[] }
  GET   /<id>/file       → raw image file
  GET   /<id>/thumbnail  → JPEG thumbnail
  GET   /stats           → { total_images, ai_processed, … }
  DEL   /<id>            → { message }

/api/annotations/
  GET   /image/<id>      → { annotations[] }
  POST  /                → { annotation }
  PUT   /<id>            → { annotation }
  DEL   /<id>            → { message }
  POST  /image/<id>/approve → { image_status }
  GET   /export/<id>     → COCO JSON or YOLO TXT file

/api/ai/
  POST  /analyze/<id>    → { result, annotations_created, performance }
  POST  /batch-analyze   → { queued[] }
  GET   /results/<id>    → { results[] }
  GET   /models/status   → { yolo: {…}, unet: {…} }

/api/projects/
  GET   /                → { projects[] }
  POST  /                → { project }
  GET   /<id>            → { project, label_classes[] }
  PUT   /<id>            → { project }
  POST  /<id>/label-classes → { label_class }
  GET   /<id>/stats      → { total_images, approved, completion_pct }

/api/users/   (admin role required for list/deactivate)
  GET   /                → { users[] }
  GET   /<id>            → { user }
  PUT   /<id>            → { user }
  POST  /<id>/deactivate → { message }
  GET   /audit-log       → { logs[], total }
```

---

## Database Schema

```
users ──────────────────────── id, email, password_hash, full_name,
                                role, specialty, institution,
                                is_active, is_verified, last_login

projects ──────────────────── id, name, description, modality,
                                target_pathology, status, created_by→users

label_classes ─────────────── id, project_id→projects, name,
                                display_name, color, icd_code, is_active

medical_images ────────────── id, filename, original_filename,
                                file_path, thumbnail_path, file_size,
                                modality, body_part, patient_id,
                                width, height, channels,
                                status, ai_processed, ai_processing_time,
                                uploaded_by→users, project_id→projects

annotations ───────────────── id, image_id→medical_images,
                                label_class_id→label_classes, label_name,
                                annotation_type, source,
                                x_min, y_min, x_max, y_max,   ← normalised 0-1
                                segmentation_data (JSON),
                                confidence, is_verified, severity,
                                annotated_by→users, verified_by→users

ai_inference_results ──────── id, image_id→medical_images,
                                model_type, model_version,
                                detections (JSON), segmentations (JSON),
                                inference_time, num_detections,
                                avg_confidence, status, error_message

audit_logs ────────────────── id, user_id→users, action,
                                resource_type, resource_id,
                                details, ip_address, timestamp
```
