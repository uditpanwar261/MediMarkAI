"""
MediMark AI — Flask Application Factory
"""

from flask import Flask
from flask_cors import CORS
from backend.config import Config
from backend.extensions import db, migrate, jwt, limiter
from backend.routes.auth import auth_bp
from backend.routes.images import images_bp
from backend.routes.annotations import annotations_bp
from backend.routes.ai_inference import ai_bp
from backend.routes.dashboard import dashboard_bp
from backend.routes.projects import projects_bp
from backend.routes.users import users_bp
import logging
import os


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder='frontend/templates',
        static_folder='frontend/static'
    )
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.register_blueprint(auth_bp,        url_prefix='/api/auth')
    app.register_blueprint(images_bp,      url_prefix='/api/images')
    app.register_blueprint(annotations_bp, url_prefix='/api/annotations')
    app.register_blueprint(ai_bp,          url_prefix='/api/ai')
    app.register_blueprint(projects_bp,    url_prefix='/api/projects')
    app.register_blueprint(users_bp,       url_prefix='/api/users')
    app.register_blueprint(dashboard_bp,   url_prefix='/')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    os.makedirs(app.config['UPLOAD_FOLDER'],    exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
