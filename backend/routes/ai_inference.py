"""
MediMark AI — AI Inference Routes
Works with both local file paths and Cloudinary URLs.
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.extensions import db
from backend.models.database import MedicalImage, Annotation, AIInferenceResult
from backend.ml_models.inference_engine import AIInferenceEngine
import json, logging, os, tempfile

logger = logging.getLogger(__name__)
ai_bp  = Blueprint('ai', __name__)

_engine = None

def get_engine() -> AIInferenceEngine:
    global _engine
    if _engine is None:
        _engine = AIInferenceEngine(
            yolo_model_path  = current_app.config.get('YOLO_MODEL_PATH',  'ml_models/yolo_medical.pt'),
            unet_model_path  = current_app.config.get('UNET_MODEL_PATH',  'ml_models/unet_medical.h5'),
            yolo_confidence  = current_app.config.get('YOLO_CONFIDENCE_THRESHOLD', 0.45),
            unet_threshold   = current_app.config.get('UNET_THRESHOLD', 0.5),
        )
    return _engine


def _get_local_path(image: MedicalImage) -> str:
    """
    Return a local file path suitable for OpenCV.
    If file_path is a Cloudinary URL, download it to /tmp first.
    """
    path = image.file_path
    if not path:
        raise ValueError("Image has no file path stored")

    # Already a local path that exists
    if not path.startswith('http') and os.path.exists(path):
        return path

    # Cloudinary (or any HTTP) URL — download to /tmp
    if path.startswith('http'):
        import urllib.request
        ext = os.path.splitext(image.filename)[1] or '.jpg'
        tmp_path = os.path.join('/tmp', f"medimark_infer_{image.id}{ext}")
        if not os.path.exists(tmp_path):          # cache during same process
            urllib.request.urlretrieve(path, tmp_path)
        return tmp_path

    raise FileNotFoundError(f"Image file not accessible: {path}")


@ai_bp.route('/analyze/<image_id>', methods=['POST'])
@jwt_required()
def analyze_image(image_id):
    user_id = get_jwt_identity()
    image   = MedicalImage.query.get_or_404(image_id)

    # Return cached result unless force_rerun requested
    if image.ai_processed and not request.json.get('force_rerun', False):
        cached = AIInferenceResult.query.filter_by(
            image_id=image_id, status='complete'
        ).order_by(AIInferenceResult.created_at.desc()).first()
        if cached:
            return jsonify({
                'message': 'Using cached AI results',
                'result':  cached.to_dict(),
                'cached':  True
            })

    image.status = 'processing'
    db.session.commit()

    try:
        local_path = _get_local_path(image)
        engine     = get_engine()
        result     = engine.process_image(local_path)

        # Save inference record
        inference_record = AIInferenceResult(
            image_id        = image_id,
            model_type      = 'combined',
            model_version   = '1.0',
            detections      = json.dumps(result['detections']),
            segmentations   = json.dumps(result['segmentations']),
            inference_time  = result['performance']['total_ms'],
            num_detections  = result['num_detections'],
            avg_confidence  = result['avg_confidence'],
            status          = 'complete'
        )
        db.session.add(inference_record)

        # Auto-create Annotation rows from detections
        created = 0
        for det in result['detections']:
            db.session.add(Annotation(
                image_id        = image_id,
                label_name      = det['label'],
                annotation_type = 'bounding_box',
                source          = 'ai_yolo',
                x_min           = det['x_min'],
                y_min           = det['y_min'],
                x_max           = det['x_max'],
                y_max           = det['y_max'],
                confidence      = det['confidence'],
                is_verified     = False,
                annotated_by    = user_id,
            ))
            created += 1

        # Auto-create segmentation annotations
        for seg in result['segmentations']:
            if seg.get('polygon_points'):
                db.session.add(Annotation(
                    image_id        = image_id,
                    label_name      = seg.get('label', 'Region of Interest'),
                    annotation_type = 'segmentation',
                    source          = 'ai_unet',
                    segmentation_data = json.dumps({
                        'polygon_points':    seg['polygon_points'],
                        'normalized_points': seg.get('normalized_points', []),
                    }),
                    confidence   = seg.get('confidence', 0.0),
                    is_verified  = False,
                    annotated_by = user_id,
                ))
                created += 1

        image.ai_processed      = True
        image.ai_processing_time = result['performance']['total_ms'] / 1000
        image.status             = 'ai_complete'
        db.session.commit()

        return jsonify({
            'message':             'AI analysis complete',
            'result':              inference_record.to_dict(),
            'annotations_created': created,
            'performance':         result['performance'],
            'model_info':          result['model_info'],
        })

    except Exception as e:
        logger.error(f"AI inference failed for {image_id}: {e}", exc_info=True)
        image.status = 'uploaded'
        db.session.commit()

        failed = AIInferenceResult(
            image_id=image_id, model_type='combined',
            status='failed', error_message=str(e)
        )
        db.session.add(failed)
        db.session.commit()
        return jsonify({'error': f'AI inference failed: {str(e)}'}), 500


@ai_bp.route('/batch-analyze', methods=['POST'])
@jwt_required()
def batch_analyze():
    data      = request.get_json()
    image_ids = data.get('image_ids', [])
    if not image_ids:
        return jsonify({'error': 'No image IDs provided'}), 400
    if len(image_ids) > 20:
        return jsonify({'error': 'Maximum 20 images per batch'}), 400
    results = []
    for iid in image_ids:
        img = MedicalImage.query.get(iid)
        if img:
            img.status = 'processing'
            results.append({'image_id': iid, 'status': 'queued'})
    db.session.commit()
    return jsonify({'message': f'{len(results)} images queued', 'queued': results})


@ai_bp.route('/results/<image_id>', methods=['GET'])
@jwt_required()
def get_inference_results(image_id):
    results = AIInferenceResult.query.filter_by(
        image_id=image_id
    ).order_by(AIInferenceResult.created_at.desc()).all()
    return jsonify({'image_id': image_id, 'results': [r.to_dict() for r in results]})


@ai_bp.route('/models/status', methods=['GET'])
@jwt_required()
def model_status():
    yolo_path = current_app.config.get('YOLO_MODEL_PATH', 'ml_models/yolo_medical.pt')
    unet_path = current_app.config.get('UNET_MODEL_PATH', 'ml_models/unet_medical.h5')
    return jsonify({
        'yolo': {
            'path':   yolo_path,
            'exists': os.path.exists(yolo_path),
            'status': 'loaded' if os.path.exists(yolo_path) else 'mock_mode'
        },
        'unet': {
            'path':   unet_path,
            'exists': os.path.exists(unet_path),
            'status': 'loaded' if os.path.exists(unet_path) else 'mock_mode'
        },
        'cloudinary': {
            'configured': bool(os.environ.get('CLOUDINARY_CLOUD_NAME')),
            'status': 'active' if os.environ.get('CLOUDINARY_CLOUD_NAME') else 'not_configured'
        }
    })
