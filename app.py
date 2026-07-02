from flask import Flask, request, jsonify
from flask_cors import CORS
from deepface import DeepFace
import base64
import cv2
import numpy as np
import os
import tempfile

app = Flask(__name__)
CORS(app)

# Pre-load the model to avoid downloading on first request
print("Loading DeepFace model...")
try:
    # This pre-loads the model
    DeepFace.build_model(model_name='Facenet')
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f"⚠️ Model loading issue: {e}")
    print("Model will be downloaded on first request")

def decode_base64_image(base64_string):
    """Decode base64 image to OpenCV format"""
    try:
        # Remove data URL prefix if present
        if ',' in base64_string and 'base64' in base64_string.split(',')[0]:
            base64_string = base64_string.split(',')[1]
        
        img_data = base64.b64decode(base64_string)
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("Could not decode image")
        return img
    except Exception as e:
        raise ValueError(f"Invalid base64 image: {str(e)}")

@app.route('/verify-face', methods=['POST'])
def verify_face():
    """
    Verify if two faces belong to the same person
    Expects JSON: {"image1": "base64_string", "image2": "base64_string"}
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
        
        # Save to temporary files (DeepFace needs file paths)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f1:
            cv2.imwrite(f1.name, img1)
            path1 = f1.name
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f2:
            cv2.imwrite(f2.name, img2)
            path2 = f2.name
        
        try:
            # Perform face verification with lighter model
            # Facenet is smaller and faster than the default
            result = DeepFace.verify(
                img1_path=path1, 
                img2_path=path2,
                model_name='Facenet',  # Lighter model
                enforce_detection=False,  # Don't fail if no face detected
                detector_backend='opencv'  # Faster detection
            )
            
            # Calculate confidence (0-100%)
            # Lower distance = more similar
            confidence = (1 - result['distance']) * 100
            
            return jsonify({
                'verified': bool(result['verified']),
                'confidence': round(confidence, 2),
                'distance': round(result['distance'], 4),
                'message': 'Faces match!' if result['verified'] else 'Faces do not match',
                'model': 'Facenet'
            }), 200
            
        finally:
            # Clean up temp files
            try:
                os.unlink(path1)
                os.unlink(path2)
            except:
                pass
            
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Face verification failed: {str(e)}'}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'service': 'Face Verification API',
        'version': '1.0.0',
        'endpoints': {
            '/verify-face': 'POST - Send two base64 images',
            '/health': 'GET - Check service status'
        }
    }), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)