# 🏥 MediMark AI — Medical Image Annotation Platform

> AI-assisted medical image annotation with YOLO detection + U-Net segmentation, built for clinical radiology workflows.

![Stack](https://img.shields.io/badge/Python-3.11-blue) ![Flask](https://img.shields.io/badge/Flask-3.0-green) ![OpenCV](https://img.shields.io/badge/OpenCV-4.9-red) ![MySQL](https://img.shields.io/badge/MySQL-8.0-orange)

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **AI Detection** | YOLOv8/v5 auto-generates bounding boxes for 10+ pathologies |
| **AI Segmentation** | U-Net pixel-level segmentation masks per detected region |
| **Interactive Canvas** | Zoom, pan, draw boxes, click-to-select annotations |
| **Doctor Review** | Verify, edit, approve/reject AI annotations per image |
| **Audit Logging** | HIPAA-compliant full action trail |
| **Export** | COCO JSON + YOLO TXT for training pipelines |
| **Multi-modality** | CT, MRI, X-Ray, Ultrasound, Mammography, DICOM |
| **Role-based Access** | Radiologist, Oncologist, Pathologist, Admin, Researcher |

---

## 🏗️ Architecture

```
medimark-ai/
├── app.py                          # Flask app factory
├── backend/
│   ├── config.py                   # Configuration (Dev/Prod/Test)
│   ├── extensions.py               # SQLAlchemy, JWT, Limiter
│   ├── models/
│   │   └── database.py             # ORM: User, MedicalImage, Annotation, ...
│   ├── routes/
│   │   ├── auth.py                 # POST /api/auth/login|register
│   │   ├── images.py               # GET/POST /api/images/
│   │   ├── annotations.py          # CRUD /api/annotations/
│   │   ├── ai_inference.py         # POST /api/ai/analyze/<id>
│   │   └── dashboard.py            # Serves frontend SPA
│   └── ml_models/
│       └── inference_engine.py     # YOLO + U-Net pipeline
├── frontend/
│   ├── templates/index.html        # Single-page app shell
│   └── static/
│       ├── css/main.css            # Dark clinical design system
│       ├── js/api.js               # REST API client (JWT-aware)
│       ├── js/canvas.js            # Canvas annotation engine
│       └── js/app.js               # SPA controller
├── database/
│   └── init_schema.sql             # Full MySQL schema + seed data
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## 🚀 Quick Start

### Option A: Docker Compose (Recommended)

```bash
git clone https://github.com/your-org/medimark-ai.git
cd medimark-ai
cp .env.example .env

docker-compose up --build
```

App available at **http://localhost:80**

### Option B: Local Development

**1. Database**
```bash
mysql -u root -p < database/init_schema.sql
```

**2. Python environment**
```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**3. Environment**
```bash
cp .env.example .env
# Edit .env with your MySQL credentials
```

**4. Run**
```bash
flask db upgrade      # Run migrations
python app.py         # Development server → http://localhost:5000
```

**Demo credentials:** `admin@medimark.ai` / `demo1234`

---

## 🤖 AI Model Integration

MediMark AI runs in **mock mode** when no model files are present — it generates plausible synthetic annotations using OpenCV image statistics. This lets you run and demo the full platform without GPU/model files.

### YOLO Integration

Place your model at `ml_models/yolo_medical.pt`:

```bash
# Download a pre-trained medical YOLO model or train your own:
# yolo train data=chest_xray.yaml model=yolov8n.pt epochs=100

# Or use ultralytics hub:
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.train(data='your_medical_data.yaml', epochs=100)
model.save('ml_models/yolo_medical.pt')
```

### U-Net Integration

Place your model at `ml_models/unet_medical.h5`:

```python
# TensorFlow/Keras U-Net
import tensorflow as tf

model = build_unet(input_shape=(256, 256, 3))
model.compile(optimizer='adam', loss='binary_crossentropy')
model.fit(X_train, y_train, epochs=50)
model.save('ml_models/unet_medical.h5')
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Authenticate, receive JWT |
| `POST` | `/api/auth/register` | Create doctor account |
| `GET`  | `/api/images/` | List images (paginated, filterable) |
| `POST` | `/api/images/upload` | Upload medical image (multipart) |
| `GET`  | `/api/images/<id>/file` | Serve image file |
| `GET`  | `/api/images/stats` | Dashboard statistics |
| `POST` | `/api/ai/analyze/<id>` | Run YOLO + U-Net on image |
| `GET`  | `/api/ai/models/status` | Check model loading status |
| `GET`  | `/api/annotations/image/<id>` | Get all annotations for image |
| `POST` | `/api/annotations/` | Create annotation |
| `PUT`  | `/api/annotations/<id>` | Update / verify annotation |
| `DELETE` | `/api/annotations/<id>` | Soft-delete annotation |
| `POST` | `/api/annotations/image/<id>/approve` | Doctor approves all |
| `GET`  | `/api/annotations/export/<id>?format=coco` | Export COCO JSON |
| `GET`  | `/api/annotations/export/<id>?format=yolo` | Export YOLO TXT |

---

## 🗄️ Database Schema

```
users ──────────────────────────────────────────────────┐
  id, email, password_hash, full_name, role, ...        │
                                                         │
projects ────────────────────────────────────┐           │
  id, name, description, modality, ...       │           │
                                             │           │
medical_images ──────────────────────────────┤───────────┘
  id, filename, modality, body_part,         │  uploaded_by → users.id
  patient_id, width, height, status,         │  project_id  → projects.id
  ai_processed, ...                          │
                                             │
label_classes ───────────────────────────────┘
  id, name, color, icd_code, ...               project_id → projects.id

annotations ─────────────────────────────────────────────┐
  id, image_id, label_name,                              │
  annotation_type, source,                               │
  x_min/y_min/x_max/y_max,                               │
  segmentation_data (JSON),                              │
  confidence, is_verified, ...                           │
                                                         │
ai_inference_results ────────────────────────────────────┘
  id, image_id, model_type,
  detections (JSON), segmentations (JSON),
  inference_time, num_detections, ...

audit_logs ──────────────────────────────────────────────
  id, user_id, action, resource_type,
  resource_id, ip_address, timestamp, ...
```

---

## 🔐 Security

- **JWT** with 8-hour access tokens + 30-day refresh tokens
- **bcrypt** password hashing (13 rounds)
- **Rate limiting** via Flask-Limiter
- **HIPAA-compliant audit log** on all data access/mutations
- **Soft deletes** preserve data integrity for annotations
- Patient IDs are stored as anonymized references only

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask 3.0 |
| Database | MySQL 8.0 (via SQLAlchemy ORM) |
| AI Detection | YOLO (ultralytics) / OpenCV DNN |
| AI Segmentation | U-Net (TensorFlow/Keras or PyTorch) |
| Image Processing | OpenCV 4.9, NumPy, Pillow |
| Auth | JWT (Flask-JWT-Extended) |
| Frontend | Vanilla JS + Canvas API |
| Fonts | Sora + DM Mono + Space Grotesk |
| Deployment | Docker, Gunicorn, Nginx |

---

## 📄 License

MIT License — see `LICENSE` for details.

Built for clinical research and AI model training data management.
**Not FDA-approved for diagnostic use.**
