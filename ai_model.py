import cv2
import numpy as np
import os
import base64

# Load standard OpenCV Haar cascade for face detection
cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
face_cascade = cv2.CascadeClassifier(cascade_path)

def has_clear_face(image_bytes):
    """
    Checks if a clear face is present in the raw image bytes before saving to DB.
    """
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        detected_faces = face_cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=4)
        return len(detected_faces) > 0
    except Exception as e:
        print(f"Face check error: {e}")
        return False

def check_duplicate_face(image_bytes, class_id):
    """
    Checks if the provided face already exists in the trained model for this class.
    Returns: (True, student_id) if duplicate found, else (False, None)
    """
    model_path = f'models/class_{class_id}.yml'
    
    if not os.path.exists(model_path) or not hasattr(cv2, 'face'):
        return False, None

    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(model_path)
        
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        detected_faces = face_cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=4)
        
        for (x, y, w, h) in detected_faces:
            face_roi = img[y:y+h, x:x+w]
            
            # Histogram Equalization to normalize lighting for accurate comparison
            face_roi = cv2.equalizeHist(face_roi) 
            
            label, confidence = recognizer.predict(face_roi)
            
            # VERY STRICT threshold to ensure we only flag true duplicates (< 60)
            if confidence < 60: 
                return True, label
                
        return False, None
    except Exception as e:
        print(f"Duplicate check error: {e}")
        return False, None

def train_class_model(class_id, students_data):
    """
    Trains an LBPH Face Recognizer for a specific class using saved student photos.
    students_data: list of dictionaries containing 'id' and 'photo_path'
    """
    if not hasattr(cv2, 'face'):
        raise AttributeError("opencv-contrib-python module is missing")
        
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    faces = []
    labels = []
    
    for student in students_data:
        path = student['photo_path']
        if not os.path.exists(path):
            continue
            
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
            
        detected_faces = face_cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=4)
        
        for (x, y, w, h) in detected_faces:
            face_roi = img[y:y+h, x:x+w]
            
            # Normalizes lighting variations during training for much higher accuracy
            face_roi = cv2.equalizeHist(face_roi) 
            
            faces.append(face_roi)
            labels.append(student['id'])
            break # Only take the primary face
            
    if faces:
        os.makedirs('models', exist_ok=True)
        model_path = f'models/class_{class_id}.yml'
        recognizer.train(faces, np.array(labels))
        recognizer.write(model_path)
        return True
        
    return False

def recognize_student(img_b64, class_id):
    """
    Analyzes a live camera feed.
    Returns: (STATUS_STRING, student_id, confidence_score)
    """
    model_path = f'models/class_{class_id}.yml'
    
    if not os.path.exists(model_path):
        return "NO_MODEL", None, 0

    if not hasattr(cv2, 'face'):
        return "MISSING_MODULE", None, 0

    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(model_path)
        
        encoded = img_b64.split(',')[1]
        nparr = np.frombuffer(base64.b64decode(encoded), np.uint8)
        live_img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        detected_faces = face_cascade.detectMultiScale(live_img, scaleFactor=1.1, minNeighbors=4, minSize=(50, 50))
        
        if len(detected_faces) == 0:
            return "NO_FACE", None, 0
            
        for (x, y, w, h) in detected_faces:
            face_roi = live_img[y:y+h, x:x+w]
            
            # Normalize live feed lighting to match the trained data
            face_roi = cv2.equalizeHist(face_roi) 
            
            label, confidence = recognizer.predict(face_roi)
            
            # STRICTER MATCHING: Lowered threshold from 85 to 65 to prevent false identity matches
            if confidence < 65: 
                return "SUCCESS", label, confidence
            else:
                return "UNKNOWN", None, confidence
                
        return "UNKNOWN", None, 0
        
    except Exception as e:
        print(f"AI Recognition Error: {e}")
        return f"ERROR: {str(e)}", None, 0