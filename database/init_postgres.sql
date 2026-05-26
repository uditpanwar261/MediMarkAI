-- MediMark AI — PostgreSQL Initialization Script
-- Used for local PostgreSQL testing.
-- On Render, SQLAlchemy creates tables automatically via db.create_all().

CREATE TABLE IF NOT EXISTS users (
    id              VARCHAR(36)   PRIMARY KEY,
    email           VARCHAR(255)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255)  NOT NULL,
    full_name       VARCHAR(255)  NOT NULL,
    role            VARCHAR(20)   NOT NULL DEFAULT 'radiologist',
    specialty       VARCHAR(100),
    institution     VARCHAR(255),
    is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP     NOT NULL DEFAULT NOW(),
    last_login      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id                VARCHAR(36)   PRIMARY KEY,
    name              VARCHAR(255)  NOT NULL,
    description       TEXT,
    modality          VARCHAR(50),
    target_pathology  VARCHAR(200),
    status            VARCHAR(20)   NOT NULL DEFAULT 'active',
    created_by        VARCHAR(36)   REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS label_classes (
    id            VARCHAR(36)  PRIMARY KEY,
    project_id    VARCHAR(36)  NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name          VARCHAR(100) NOT NULL,
    display_name  VARCHAR(150),
    color         VARCHAR(7)   DEFAULT '#FF6B6B',
    description   TEXT,
    icd_code      VARCHAR(20),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS medical_images (
    id                    VARCHAR(36)   PRIMARY KEY,
    filename              VARCHAR(500)  NOT NULL,
    original_filename     VARCHAR(500)  NOT NULL,
    file_path             VARCHAR(1000) NOT NULL,
    processed_path        VARCHAR(1000),
    thumbnail_path        VARCHAR(1000),
    file_size             BIGINT,
    mime_type             VARCHAR(100),
    modality              VARCHAR(20)   DEFAULT 'Other',
    body_part             VARCHAR(100),
    patient_id            VARCHAR(100),
    study_date            DATE,
    study_description     TEXT,
    series_uid            VARCHAR(200),
    width                 INTEGER,
    height                INTEGER,
    channels              INTEGER       DEFAULT 3,
    status                VARCHAR(20)   NOT NULL DEFAULT 'uploaded',
    ai_processed          BOOLEAN       NOT NULL DEFAULT FALSE,
    ai_processing_time    FLOAT,
    uploaded_by           VARCHAR(36)   NOT NULL REFERENCES users(id),
    project_id            VARCHAR(36)   REFERENCES projects(id) ON DELETE SET NULL,
    created_at            TIMESTAMP     NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS annotations (
    id                VARCHAR(36)   PRIMARY KEY,
    image_id          VARCHAR(36)   NOT NULL REFERENCES medical_images(id) ON DELETE CASCADE,
    label_class_id    VARCHAR(36)   REFERENCES label_classes(id) ON DELETE SET NULL,
    label_name        VARCHAR(100)  NOT NULL,
    annotation_type   VARCHAR(20)   NOT NULL DEFAULT 'bounding_box',
    source            VARCHAR(20)   NOT NULL DEFAULT 'manual',
    x_min             FLOAT,
    y_min             FLOAT,
    x_max             FLOAT,
    y_max             FLOAT,
    segmentation_data TEXT,
    mask_path         VARCHAR(500),
    confidence        FLOAT,
    is_verified       BOOLEAN       NOT NULL DEFAULT FALSE,
    is_active         BOOLEAN       NOT NULL DEFAULT TRUE,
    notes             TEXT,
    severity          VARCHAR(20),
    annotated_by      VARCHAR(36)   REFERENCES users(id) ON DELETE SET NULL,
    verified_by       VARCHAR(36)   REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMP     NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_inference_results (
    id              VARCHAR(36)   PRIMARY KEY,
    image_id        VARCHAR(36)   NOT NULL REFERENCES medical_images(id) ON DELETE CASCADE,
    model_type      VARCHAR(20)   NOT NULL,
    model_version   VARCHAR(50),
    detections      TEXT,
    segmentations   TEXT,
    inference_time  FLOAT,
    num_detections  INTEGER       DEFAULT 0,
    avg_confidence  FLOAT,
    status          VARCHAR(20)   NOT NULL DEFAULT 'pending',
    error_message   TEXT,
    created_at      TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id            BIGSERIAL     PRIMARY KEY,
    user_id       VARCHAR(36)   REFERENCES users(id) ON DELETE SET NULL,
    action        VARCHAR(100)  NOT NULL,
    resource_type VARCHAR(50),
    resource_id   VARCHAR(36),
    details       TEXT,
    ip_address    VARCHAR(45),
    user_agent    VARCHAR(500),
    timestamp     TIMESTAMP     NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_images_status     ON medical_images(status);
CREATE INDEX IF NOT EXISTS idx_images_modality   ON medical_images(modality);
CREATE INDEX IF NOT EXISTS idx_images_created    ON medical_images(created_at);
CREATE INDEX IF NOT EXISTS idx_annotations_image ON annotations(image_id);
CREATE INDEX IF NOT EXISTS idx_annotations_src   ON annotations(source);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp   ON audit_logs(timestamp);
