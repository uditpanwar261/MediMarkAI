"""
MediMark AI - AI Inference Routes
Triggers YOLO + U-Net pipeline and converts results to annotations
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.extensions import db
from backend.models.database import (
    MedicalImage, Annotation, AIInferenceResult, AuditLog
)
from backend.ml_models.inference_engine import AIInferenceEngine
import json
import logging

logger = logging.getLogger(__name__)
ai_bp = Blueprint('ai', __name__)

# Singleton inference engine
_engine = None

def get_engine() -> AIInferenceEngine:
    global _engine
    if _engine is None:
        _engine = AIInferenceEngine(
            yolo_model_path=current_app.config['YOLO_MODEL_PATH'],
            unet_model_path=current_app.config['UNET_MODEL_PATH'],
            yolo_confidence=current_app.config['YOLO_CONFIDENCE_THRESHOLD'],
            unet_threshold=current_app.config['UNET_THRESHOLD']
        )
    return _engine


@ai_bp.route('/analyze/<image_id>', methods=['POST'])
@jwt_required()
def analyze_image(image_id):
    """Run full AI pipeline on a medical image"""
    user_id = get_jwt_identity()
    image = MedicalImage.query.get_or_404(image_id)

    if image.ai_processed and not request.json.get('force_rerun', False):
        # Return cached results
        cached = AIInferenceResult.query.filter_by(
            image_id=image_id, status='complete'
        ).order_by(AIInferenceResult.created_at.desc()).first()
        if cached:
            return jsonify({
                'message': 'Using cached AI results',
                'result': cached.to_dict(),
                'cached': True
            })

    image.status = 'processing'
    db.session.commit()

    try:
        engine = get_engine()
        result = engine.process_image(image.file_path)

        # Save inference result
        inference_record = AIInferenceResult(
            image_id=image_id,
            model_type='combined',
            model_version='1.0',
            detections=json.dumps(result['detections']),
            segmentations=json.dumps(result['segmentations']),
            inference_time=result['performance']['total_ms'],
            num_detections=result['num_detections'],
            avg_confidence=result['avg_confidence'],
            status='complete'
        )
        db.session.add(inference_record)

        # Auto-create annotation records from detections
        auto_annotations_created = 0
        for det in result['detections']:
            ann = Annotation(
                image_id=image_id,
                label_name=det['label'],
                annotation_type='bounding_box',
                source='ai_yolo',
                x_min=det['x_min'],
                y_min=det['y_min'],
                x_max=det['x_max'],
                y_max=det['y_max'],
                confidence=det['confidence'],
                is_verified=False,
                annotated_by=user_id
            )
            db.session.add(ann)
            auto_annotations_created += 1

        # Auto-create segmentation annotations
        for seg in result['segmentations']:
            if seg.get('polygon_points'):
                ann = Annotation(
                    image_id=image_id,
                    label_name=seg.get('label', 'Region of Interest'),
                    annotation_type='segmentation',
                    source='ai_unet',
                    segmentation_data=json.dumps({
                        'polygon_points': seg['polygon_points'],
                        'normalized_points': seg.get('normalized_points', [])
                    }),
                    confidence=seg.get('confidence', 0.0),
                    is_verified=False,
                    annotated_by=user_id
                )
                db.session.add(ann)
                auto_annotations_created += 1

        # Update image status
        image.ai_processed = True
        image.ai_processing_time = result['performance']['total_ms'] / 1000
        image.status = 'ai_complete'
        db.session.commit()

        try:
            AuditLog.log(user_id, 'ai_analysis', 'medical_image', image_id,
                         f"AI analysis complete: {result['num_detections']} detections",
                         request.remote_addr)
        except Exception:
            pass

        return jsonify({
            'message': 'AI analysis complete',
            'result': inference_record.to_dict(),
            'annotations_created': auto_annotations_created,
            'performance': result['performance'],
            'model_info': result['model_info']
        })

    except Exception as e:
        logger.error(f"AI inference failed for image {image_id}: {e}")
        image.status = 'uploaded'
        db.session.commit()

        # Save failed result
        failed_record = AIInferenceResult(
            image_id=image_id,
            model_type='combined',
            status='failed',
            error_message=str(e)
        )
        db.session.add(failed_record)
        db.session.commit()

        return jsonify({'error': f'AI inference failed: {str(e)}'}), 500


@ai_bp.route('/batch-analyze', methods=['POST'])
@jwt_required()
def batch_analyze():
    """Queue multiple images for AI analysis"""
    user_id = get_jwt_identity()
    data = request.get_json()
    image_ids = data.get('image_ids', [])

    if not image_ids:
        return jsonify({'error': 'No image IDs provided'}), 400
    if len(image_ids) > 20:
        return jsonify({'error': 'Maximum 20 images per batch'}), 400

    results = []
    for image_id in image_ids:
        image = MedicalImage.query.get(image_id)
        if image:
            image.status = 'processing'
            results.append({'image_id': image_id, 'status': 'queued'})
    db.session.commit()

    return jsonify({
        'message': f'{len(results)} images queued for analysis',
        'queued': results
    })


@ai_bp.route('/results/<image_id>', methods=['GET'])
@jwt_required()
def get_inference_results(image_id):
    """Get AI inference results for an image"""
    results = AIInferenceResult.query.filter_by(
        image_id=image_id
    ).order_by(AIInferenceResult.created_at.desc()).all()

    return jsonify({
        'image_id': image_id,
        'results': [r.to_dict() for r in results]
    })


@ai_bp.route('/models/status', methods=['GET'])
@jwt_required()
def model_status():
    """Get AI model loading status"""
    import os
    yolo_path = current_app.config['YOLO_MODEL_PATH']
    unet_path = current_app.config['UNET_MODEL_PATH']

    return jsonify({
        'yolo': {
            'path': yolo_path,
            'exists': os.path.exists(yolo_path),
            'status': 'loaded' if os.path.exists(yolo_path) else 'mock_mode'
        },
        'unet': {
            'path': unet_path,
            'exists': os.path.exists(unet_path),
            'status': 'loaded' if os.path.exists(unet_path) else 'mock_mode'
        }
    })
