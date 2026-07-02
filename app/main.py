from flask import Flask, render_template, request, send_from_directory, jsonify
import os
import cv2
import base64
import numpy as np
import tempfile
from pathlib import Path
from deepface import DeepFace
import warnings
warnings.filterwarnings('ignore')

# ============================================
# Helper: Decode base64 images
# ============================================
def decode_base64_image(base64_string):
    """Decode a base64 image string to OpenCV image."""
    try:
        # Remove data URL prefix if present
        if ',' in base64_string and 'base64' in base64_string.split(',')[0]:
            base64_string = base64_string.split(',')[1]
        
        img_data = base64.b64decode(base64_string)
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("Could not decode image - invalid format")
        return img
    except Exception as e:
        raise ValueError(f"Failed to decode base64 image: {str(e)}")

# ============================================
# Create Flask App
# ============================================
app = Flask(__name__)

# ============================================
# /verify-face API Endpoint
# ============================================
@app.route("/verify-face", methods=["POST"])
def verify_face():
    """
    Verify if two faces belong to the same person.
    Expects JSON: {"image1": "base64_string", "image2": "base64_string"}
    Returns: Verification result with confidence score.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        if 'image1' not in data or 'image2' not in data:
            return jsonify({'error': 'Missing image1 or image2'}), 400

        # Decode images
        img1 = decode_base64_image(data['image1'])
        img2 = decode_base64_image(data['image2'])

        # Save images temporarily for DeepFace
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f1:
            cv2.imwrite(f1.name, img1)
            path1 = f1.name
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f2:
            cv2.imwrite(f2.name, img2)
            path2 = f2.name

        try:
            # Perform face verification using DeepFace
            result = DeepFace.verify(
                img1_path=path1,
                img2_path=path2,
                model_name='Facenet',  # Lightweight and accurate
                enforce_detection=False,
                detector_backend='opencv'
            )

            # Calculate confidence
            distance = result['distance']
            confidence = (1 - distance) * 100

            response = {
                'verified': bool(result['verified']),
                'confidence': round(confidence, 2),
                'distance': round(distance, 4),
                'model': 'Facenet',
                'message': 'Faces match!' if result['verified'] else 'Faces do not match',
                'threshold': 0.6
            }
            return jsonify(response), 200

        finally:
            # Clean up temporary files
            try:
                os.unlink(path1)
                os.unlink(path2)
            except:
                pass

    except ValueError as e:
        return jsonify({'error': f'Invalid image data: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Face verification failed: {str(e)}'}), 500

# ============================================
# Health check endpoint
# ============================================
@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check for the API."""
    return jsonify({
        'status': 'healthy',
        'service': 'face-verification-api',
        'model': 'Facenet'
    }), 200

# ============================================
# Root endpoint with API info
# ============================================
@app.route("/", methods=["GET"])
def home():
    """API information and available endpoints."""
    return jsonify({
        'service': 'Face Verification API',
        'version': '1.0.0',
        'endpoints': {
            '/verify-face': {
                'method': 'POST',
                'description': 'Verify if two faces belong to the same person',
                'request': {
                    'image1': 'base64 encoded image',
                    'image2': 'base64 encoded image'
                },
                'response': {
                    'verified': 'boolean - true if faces match',
                    'confidence': 'float - confidence score (0-100%)',
                    'distance': 'float - distance metric (lower = more similar)',
                    'model': 'string - model used for verification',
                    'message': 'string - human readable result',
                    'threshold': 'float - threshold used for verification'
                }
            },
            '/health': {
                'method': 'GET',
                'description': 'Check service health status'
            }
        }
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)