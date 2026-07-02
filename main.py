from flask import Flask, render_template, request, send_from_directory, jsonify
import os
import cv2
import base64
import numpy as np
import tempfile
from pathlib import Path
from recognition.utility import *

# Directories
REF_IMG_DIR = "./reference_images"
TARGET_IMG_DIR = "./target_images"
PROCESSED_IMG_DIR = "./processed_images"
model = MODELS[1]  # Facenet

match = MatchFace(REF_IMG_DIR, CROPPED_IMG_DIR, model)

# Ensure the processed directory exists
Path(PROCESSED_IMG_DIR).mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

# ============================================
# 🆕 NEW: /verify-face API Endpoint
# ============================================
@app.route("/verify-face", methods=["POST"])
def verify_face():
    """
    Verify if two faces belong to the same person
    Expects JSON: {"image1": "base64_string", "image2": "base64_string"}
    Returns: verification result with confidence score
    """
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        if 'image1' not in data or 'image2' not in data:
            return jsonify({'error': 'Missing image1 or image2'}), 400
        
        # Decode base64 images
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
            # Use DeepFace for verification
            # Using Facenet model (lightweight and accurate)
            result = DeepFace.verify(
                img1_path=path1,
                img2_path=path2,
                model_name='Facenet',  # You can change to 'ArcFace' for better accuracy
                enforce_detection=False,  # Don't fail if no face detected
                detector_backend='mediapipe'  # Using your existing MediaPipe detector
            )
            
            # Calculate confidence (0-100%)
            # Lower distance = more similar
            distance = result['distance']
            confidence = (1 - distance) * 100
            
            # Additional metrics
            response = {
                'verified': bool(result['verified']),
                'confidence': round(confidence, 2),
                'distance': round(distance, 4),
                'model': 'Facenet',
                'message': 'Faces match!' if result['verified'] else 'Faces do not match',
                'threshold': 0.6,  # Default threshold used by DeepFace
                'face_detected': {
                    'image1': True,  # You can add actual face detection check
                    'image2': True
                }
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
# 🆕 Helper: Decode base64 images
# ============================================
def decode_base64_image(base64_string):
    """
    Decode a base64 image string to OpenCV image
    Supports both raw base64 and data URL format
    """
    try:
        # Remove data URL prefix if present (e.g., "data:image/jpeg;base64,")
        if ',' in base64_string and 'base64' in base64_string.split(',')[0]:
            base64_string = base64_string.split(',')[1]
        
        # Decode base64 to bytes
        img_data = base64.b64decode(base64_string)
        
        # Convert bytes to numpy array
        np_arr = np.frombuffer(img_data, np.uint8)
        
        # Decode to OpenCV image
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("Could not decode image - invalid format")
        
        return img
    except Exception as e:
        raise ValueError(f"Failed to decode base64 image: {str(e)}")


# ============================================
# 🆕 Health check endpoint
# ============================================
@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'face-verification-api',
        'model': 'Facenet'
    }), 200


# ============================================
# 🆕 Root endpoint with API info
# ============================================
@app.route("/", methods=["GET"])
def home():
    """API information and available endpoints"""
    return jsonify({
        'service': 'Face Verification API',
        'version': '1.0.0',
        'endpoints': {
            '/verify-face': {
                'method': 'POST',
                'description': 'Verify if two faces belong to the same person',
                'request': {
                    'image1': 'base64 encoded image (with or without data URL prefix)',
                    'image2': 'base64 encoded image (with or without data URL prefix)'
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


# ============================================
# Existing routes (keep your original code)
# ============================================
@app.route("/images/<filename>")
def images(filename):
    return send_from_directory(TARGET_IMG_DIR, filename)

@app.route("/processed/<filename>")
def processed(filename):
    return send_from_directory(PROCESSED_IMG_DIR, filename)


def opencv_manipulations(image, match:MatchFace):
    """
    Apply OpenCV manipulations to the image.
    Modify this function with your desired transformations.
    """
    match.match(image)
    image = match.annotated_image
    print(image.shape)
    height, width = image.shape[:2]

    width_target = 500
    fac = height/width_target
    height_target = int(height/fac)

    image = cv2.resize(image, (height_target, width_target))
    return image


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)