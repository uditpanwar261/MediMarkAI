-- ─────────────────────────────────────────────────────────────
-- MediMark AI — MySQL Database Initialization Schema
-- Run: mysql -u root -p < database/init_schema.sql
-- ─────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS medimark_ai
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE medimark_ai;

-- Create application user
CREATE USER IF NOT EXISTS 'medimark_user'@'localhost'
  IDENTIFIED BY 'medimark_pass';

GRANT ALL PRIVILEGES ON medimark_ai.* TO 'medimark_user'@'localhost';
FLUSH PRIVILEGES;

-- ─── TABLES ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id              VARCHAR(36)   PRIMARY KEY,
    email           VARCHAR(255)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255)  NOT NULL,
    full_name       VARCHAR(255)  NOT NULL,
    role            ENUM('radiologist','oncologist','pathologist','admin','researcher')
                                  NOT NULL DEFAULT 'radiologist',
    specialty       VARCHAR(100),
    institution     VARCHAR(255),
    is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login      DATETIME,
    INDEX idx_email (email),
    INDEX idx_role  (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS projects (
    id                VARCHAR(36)   PRIMARY KEY,
    name              VARCHAR(255)  NOT NULL,
    description       TEXT,
    modality          VARCHAR(50),
    target_pathology  VARCHAR(200),
    status            ENUM('active','paused','completed','archived')
                                    NOT NULL DEFAULT 'active',
    created_by        VARCHAR(36),
    created_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS medical_images (
    id                    VARCHAR(36)   PRIMARY KEY,
    filename              VARCHAR(500)  NOT NULL,
    original_filename     VARCHAR(500)  NOT NULL,
    file_path             VARCHAR(1000) NOT NULL,
    processed_path        VARCHAR(1000),
    thumbnail_path        VARCHAR(1000),
    file_size             BIGINT,
    mime_type             VARCHAR(100),

    -- Medical metadata
    modality              ENUM('CT','MRI','X-Ray','Ultrasound','PET','Mammography','Endoscopy','Other')
                                        DEFAULT 'Other',
    body_part             VARCHAR(100),
    patient_id            VARCHAR(100),
    study_date            DATE,
    study_description     TEXT,
    series_uid            VARCHAR(200),

    -- Image properties
    width                 INT,
    height                INT,
    channels              INT           DEFAULT 3,

    -- Status
    status                ENUM('uploaded','processing','ai_complete','under_review','approved','rejected')
                                        NOT NULL DEFAULT 'uploaded',
    ai_processed          BOOLEAN       NOT NULL DEFAULT FALSE,
    ai_processing_time    FLOAT         COMMENT 'seconds',

    -- Relations
    uploaded_by           VARCHAR(36)   NOT NULL,
    project_id            VARCHAR(36),
    created_at            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (uploaded_by) REFERENCES users(id)    ON DELETE RESTRICT,
    FOREIGN KEY (project_id)  REFERENCES projects(id) ON DELETE SET NULL,
    INDEX idx_status       (status),
    INDEX idx_modality     (modality),
    INDEX idx_uploaded_by  (uploaded_by),
    INDEX idx_created_at   (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS label_classes (
    id            VARCHAR(36)  PRIMARY KEY,
    project_id    VARCHAR(36)  NOT NULL,
    name          VARCHAR(100) NOT NULL,
    display_name  VARCHAR(150),
    color         VARCHAR(7)   DEFAULT '#FF6B6B',
    description   TEXT,
    icd_code      VARCHAR(20)  COMMENT 'ICD-10 code',
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    INDEX idx_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS annotations (
    id                VARCHAR(36)   PRIMARY KEY,
    image_id          VARCHAR(36)   NOT NULL,
    label_class_id    VARCHAR(36),
    label_name        VARCHAR(100)  NOT NULL,

    -- Type & source
    annotation_type   ENUM('bounding_box','segmentation','polygon','point','classification')
                                    NOT NULL DEFAULT 'bounding_box',
    source            ENUM('manual','ai_yolo','ai_unet','ai_assisted')
                                    NOT NULL DEFAULT 'manual',

    -- Bounding box (normalized 0–1)
    x_min             FLOAT,
    y_min             FLOAT,
    x_max             FLOAT,
    y_max             FLOAT,

    -- Segmentation
    segmentation_data MEDIUMTEXT    COMMENT 'JSON: polygon points or RLE',
    mask_path         VARCHAR(500),

    -- Quality
    confidence        FLOAT         COMMENT 'AI confidence score 0–1',
    is_verified       BOOLEAN       NOT NULL DEFAULT FALSE,
    is_active         BOOLEAN       NOT NULL DEFAULT TRUE,
    notes             TEXT,
    severity          ENUM('normal','mild','moderate','severe','critical'),

    -- Tracking
    annotated_by      VARCHAR(36),
    verified_by       VARCHAR(36),
    created_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (image_id)       REFERENCES medical_images(id) ON DELETE CASCADE,
    FOREIGN KEY (label_class_id) REFERENCES label_classes(id)  ON DELETE SET NULL,
    FOREIGN KEY (annotated_by)   REFERENCES users(id)           ON DELETE SET NULL,
    FOREIGN KEY (verified_by)    REFERENCES users(id)           ON DELETE SET NULL,
    INDEX idx_image_id   (image_id),
    INDEX idx_source     (source),
    INDEX idx_verified   (is_verified),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS ai_inference_results (
    id              VARCHAR(36)   PRIMARY KEY,
    image_id        VARCHAR(36)   NOT NULL,
    model_type      ENUM('yolo','unet','combined') NOT NULL,
    model_version   VARCHAR(50),

    -- Results (JSON)
    detections      MEDIUMTEXT    COMMENT 'JSON array of YOLO detections',
    segmentations   MEDIUMTEXT    COMMENT 'JSON array of U-Net masks',

    -- Metrics
    inference_time  FLOAT         COMMENT 'milliseconds',
    num_detections  INT           DEFAULT 0,
    avg_confidence  FLOAT,

    -- Status
    status          ENUM('pending','complete','failed') NOT NULL DEFAULT 'pending',
    error_message   TEXT,

    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (image_id) REFERENCES medical_images(id) ON DELETE CASCADE,
    INDEX idx_image_id  (image_id),
    INDEX idx_status    (status),
    INDEX idx_created   (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS audit_logs (
    id            BIGINT        PRIMARY KEY AUTO_INCREMENT,
    user_id       VARCHAR(36),
    action        VARCHAR(100)  NOT NULL,
    resource_type VARCHAR(50),
    resource_id   VARCHAR(36),
    details       TEXT,
    ip_address    VARCHAR(45),
    user_agent    VARCHAR(500),
    timestamp     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id   (user_id),
    INDEX idx_action    (action),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─── SEED DATA ───────────────────────────────────────────────

-- Default admin user (password: demo1234)
INSERT IGNORE INTO users (id, email, password_hash, full_name, role, specialty, institution, is_active, is_verified)
VALUES (
    'admin-0000-0000-0000-000000000001',
    'admin@medimark.ai',
    -- bcrypt hash of 'demo1234' with 13 rounds
    '$2b$13$K9uYXPQRJJdSL2B0L1qXfutHFg1bqIzDPz9VpqKGHxHBOijzAb1sS',
    'Dr. Admin User',
    'admin',
    'Radiology',
    'MediMark Medical Center',
    TRUE,
    TRUE
);

-- Demo project
INSERT IGNORE INTO projects (id, name, description, modality, target_pathology, status, created_by)
VALUES (
    'proj-0000-0000-0000-000000000001',
    'Chest X-Ray Pneumonia Detection',
    'Annotating chest X-rays for pneumonia, pleural effusion, and cardiomegaly detection.',
    'X-Ray',
    'Pneumonia, Pleural Effusion, Cardiomegaly',
    'active',
    'admin-0000-0000-0000-000000000001'
);

-- Common label classes
INSERT IGNORE INTO label_classes (id, project_id, name, display_name, color, icd_code, is_active) VALUES
('lc01-0000-0000-0000-000000000001', 'proj-0000-0000-0000-000000000001', 'Pulmonary Nodule',     'Pulmonary Nodule',     '#FF4757', 'J98.4',  TRUE),
('lc02-0000-0000-0000-000000000001', 'proj-0000-0000-0000-000000000001', 'Mass Lesion',          'Mass Lesion',          '#FF3742', 'R91.1',  TRUE),
('lc03-0000-0000-0000-000000000001', 'proj-0000-0000-0000-000000000001', 'Ground-glass Opacity', 'Ground-glass Opacity', '#FFA502', 'J18.0',  TRUE),
('lc04-0000-0000-0000-000000000001', 'proj-0000-0000-0000-000000000001', 'Consolidation',        'Consolidation',        '#2ED573', 'J18.9',  TRUE),
('lc05-0000-0000-0000-000000000001', 'proj-0000-0000-0000-000000000001', 'Pleural Effusion',     'Pleural Effusion',     '#5352ED', 'J90',    TRUE),
('lc06-0000-0000-0000-000000000001', 'proj-0000-0000-0000-000000000001', 'Cardiomegaly',         'Cardiomegaly',         '#FF6B81', 'I51.7',  TRUE),
('lc07-0000-0000-0000-000000000001', 'proj-0000-0000-0000-000000000001', 'Pneumothorax',         'Pneumothorax',         '#ECCC68', 'J93.1',  TRUE),
('lc08-0000-0000-0000-000000000001', 'proj-0000-0000-0000-000000000001', 'Normal',               'Normal / No Finding',  '#00E676', 'Z00.00', TRUE);
