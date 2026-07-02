from flask import Flask, request, jsonify
import os
import cv2
import base64
import numpy as np
import tempfile
import sys
import psutil
from deepface import DeepFace
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)

# ============================================
# Configuration
# ============================================
MAX_IMAGE_SIZE_MB = 2  # Max request size in MB
TARGET_IMAGE_SIZE = (224, 224)  # Tiny size for DeepFace
JPEG_QUALITY = 70  # Compress images

# ============================================
# Helper: Decode and resize base64 images
# ============================================
def decode_and_resize_image(base64_string, target_size=TARGET_IMAGE_SIZE):
    """Decode base64, resize aggressively, and return compressed image."""
    try:
        # Remove data URL prefix if present
        if ',' in base64_string and 'base64' in base64_string.split(',')[0]:
            base64_string = base64_string.split(',')[1]
        
        # Check size before decoding
        image_size_mb = len(base64_string) * 3 / 4 / 1024 / 1024  # Approximate
        if image_size_mb > MAX_IMAGE_SIZE_MB:
            raise ValueError(f"Image too large: {image_size_mb:.1f}MB (max {MAX_IMAGE_SIZE_MB}MB)")
        
        # Decode base64
        img_data = base64.b64decode(base64_string)
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("Could not decode image - invalid format")
        
        # Resize aggressively to reduce memory
        img = cv2.resize(img, target_size, interpolation=cv2.INTER_LANCZOS4)
        
        return img
    except Exception as e:
        raise ValueError(f"Image processing failed: {str(e)}")

# ============================================
# Helper: Check memory usage
# ============================================
def get_memory_usage():
    """Return current memory usage in MB."""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

# ============================================
# /verify-face API Endpoint
# ============================================
@app.route("/verify-face", methods=["POST"])
def verify_face():
    """
    Verify if two faces belong to the same person.
    Expects JSON: {"image1": "base64_string", "image2": "base64_string"}
    Returns: Detailed verification result with confidence score.
    """
    # Track memory usage
    memory_before = get_memory_usage()
    
    try:
        # Validate request
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No JSON data provided',
                'error': 'Request body must be JSON with image1 and image2 fields'
            }), 400
            
        if 'image1' not in data or 'image2' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields',
                'error': 'Both image1 and image2 are required',
                'received': list(data.keys())
            }), 400

        # Decode and resize images
        try:
            img1 = decode_and_resize_image(data['image1'])
            img2 = decode_and_resize_image(data['image2'])
        except ValueError as e:
            return jsonify({
                'status': 'error',
                'message': 'Image processing failed',
                'error': str(e)
            }), 400

        # Save temporarily
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f1:
            cv2.imwrite(f1.name, img1, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            path1 = f1.name
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f2:
            cv2.imwrite(f2.name, img2, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            path2 = f2.name

        try:
            # Check memory before DeepFace
            memory_before_deepface = get_memory_usage()
            
            # Perform verification with lightweight settings
            result = DeepFace.verify(
                img1_path=path1,
                img2_path=path2,
                model_name='Facenet',
                enforce_detection=False,
                detector_backend='opencv',
                silent=True
            )

            # Calculate metrics
            distance = result['distance']
            confidence = (1 - distance) * 100
            verified = bool(result['verified'])
            
            # Check memory after DeepFace
            memory_after = get_memory_usage()
            memory_used = memory_after - memory_before

            response = {
                'status': 'success',
                'verified': verified,
                'confidence': round(confidence, 2),
                'distance': round(distance, 4),
                'model': 'Facenet',
                'message': 'Faces match!' if verified else 'Faces do not match',
                'threshold': 0.6,
                'memory_usage_mb': round(memory_used, 2),
                'image_size': f"{TARGET_IMAGE_SIZE[0]}x{TARGET_IMAGE_SIZE[1]}"
            }
            return jsonify(response), 200

        except Exception as e:
            # DeepFace specific error
            return jsonify({
                'status': 'error',
                'message': 'Face verification failed',
                'error': str(e),
                'stage': 'deepface_processing'
            }), 500

        finally:
            # Clean up temp files
            try:
                os.unlink(path1)
                os.unlink(path2)
            except:
                pass

    except Exception as e:
        # Unexpected errors
        return jsonify({
            'status': 'error',
            'message': 'Unexpected server error',
            'error': str(e),
            'memory_usage_mb': round(get_memory_usage() - memory_before, 2)
        }), 500

# ============================================
# Health check endpoint
# ============================================
@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check with memory info."""
    return jsonify({
        'status': 'healthy',
        'service': 'face-verification-api',
        'model': 'Facenet',
        'memory_usage_mb': round(get_memory_usage(), 2),
        'max_image_size_mb': MAX_IMAGE_SIZE_MB
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
        'image_size': f"{TARGET_IMAGE_SIZE[0]}x{TARGET_IMAGE_SIZE[1]}",
        'max_image_size_mb': MAX_IMAGE_SIZE_MB,
        'endpoints': {
            '/verify-face': {
                'method': 'POST',
                'description': 'Verify if two faces belong to the same person',
                'request': {
                    'image1': 'base64 encoded image (max 2MB)',
                    'image2': 'base64 encoded image (max 2MB)'
                },
                'response': {
                    'status': 'success or error',
                    'verified': 'boolean - true if faces match',
                    'confidence': 'float - confidence score (0-100%)',
                    'distance': 'float - distance metric (lower = more similar)',
                    'message': 'string - human readable result',
                    'memory_usage_mb': 'float - memory used for this request'
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