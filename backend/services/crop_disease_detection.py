import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image as keras_image
import numpy as np
import os
from typing import Optional, Dict, Any
from PIL import Image
import io
import base64

class CropDiseaseDetector:
    """
    Crop Disease Detection Service using TensorFlow model
    """
    
    def __init__(self, model_path: str = "models/trained_model.keras"):
        """
        Initialize the crop disease detector
        
        Args:
            model_path: Path to the trained model file
        """
        self.model_path = model_path
        self.model = None
        self.class_names = [
            'Apple___Apple_scab',
            'Apple___Black_rot',
            'Apple___Cedar_apple_rust',
            'Apple___healthy',
            'Blueberry___healthy',
            'Cherry_(including_sour)___Powdery_mildew',
            'Cherry_(including_sour)___healthy',
            'Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot',
            'Corn_(maize)___Common_rust_',
            'Corn_(maize)___Northern_Leaf_Blight',
            'Corn_(maize)___healthy',
            'Grape___Black_rot',
            'Grape___Esca_(Black_Measles)',
            'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)',
            'Grape___healthy',
            'Orange___Haunglongbing_(Citrus_greening)',
            'Peach___Bacterial_spot',
            'Peach___healthy',
            'Pepper,_bell___Bacterial_spot',
            'Pepper,_bell___healthy',
            'Potato___Early_blight',
            'Potato___Late_blight',
            'Potato___healthy',
            'Raspberry___healthy',
            'Soybean___healthy',
            'Squash___Powdery_mildew',
            'Strawberry___Leaf_scorch',
            'Strawberry___healthy',
            'Tomato___Bacterial_spot',
            'Tomato___Early_blight',
            'Tomato___Late_blight',
            'Tomato___Leaf_Mold',
            'Tomato___Septoria_leaf_spot',
            'Tomato___Spider_mites Two-spotted_spider_mite',
            'Tomato___Target_Spot',
            'Tomato___Tomato_Yellow_Leaf_Curl_Virus',
            'Tomato___Tomato_mosaic_virus',
            'Tomato___healthy'
        ]
        self.load_model()
    
    def load_model(self) -> None:
        """Load the trained TensorFlow model"""
        try:
            if os.path.exists(self.model_path):
                self.model = load_model(self.model_path)
                print(f"Model loaded successfully from {self.model_path}")
            else:
                raise FileNotFoundError(f"Model file not found at {self.model_path}")
        except Exception as e:
            print(f"Error loading model: {str(e)}")
            # Set model to None so the service can still start
            self.model = None
            print("Model loading failed. Service will start without model functionality.")
            # Don't raise the exception to allow the service to start
    
    def preprocess_image(self, image_data: bytes) -> np.ndarray:
        """
        Preprocess image for model prediction
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Preprocessed image array
        """
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize to model input size
            image = image.resize((128, 128))
            
            # Convert to array and normalize
            input_arr = keras_image.img_to_array(image)
            input_arr = np.array([input_arr])  # Convert single image to batch
            input_arr = input_arr / 255.0  # Normalize pixel values
            
            return input_arr
            
        except Exception as e:
            raise ValueError(f"Error preprocessing image: {str(e)}")
    
    def preprocess_image_from_path(self, image_path: str) -> np.ndarray:
        """
        Preprocess image from file path for model prediction
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Preprocessed image array
        """
        try:
            img = keras_image.load_img(image_path, target_size=(128, 128))
            input_arr = keras_image.img_to_array(img)
            input_arr = np.array([input_arr])  # Convert single image to batch
            input_arr = input_arr / 255.0  # Normalize pixel values
            return input_arr
        except Exception as e:
            raise ValueError(f"Error preprocessing image from path: {str(e)}")
    
    def predict_disease(self, image_data: bytes) -> Dict[str, Any]:
        """
        Predict crop disease from image data
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Dictionary containing prediction results
        """
        if self.model is None:
            return {
                'success': False,
                'error': 'Model not loaded. Please check model file and compatibility.',
                'prediction': None
            }
        
        try:
            # Preprocess image
            processed_image = self.preprocess_image(image_data)
            
            # Make prediction
            predictions = self.model.predict(processed_image)
            
            # Get prediction results
            result_index = np.argmax(predictions)
            confidence = float(np.max(predictions))
            predicted_class = self.class_names[result_index]
            
            # Extract crop and disease information
            crop_disease_parts = predicted_class.split('___')
            crop = crop_disease_parts[0].replace('_', ' ')
            disease = crop_disease_parts[1].replace('_', ' ') if len(crop_disease_parts) > 1 else 'Unknown'
            
            # Determine if healthy or diseased
            is_healthy = 'healthy' in disease.lower()
            
            return {
                'success': True,
                'prediction': {
                    'class': predicted_class,
                    'crop': crop,
                    'disease': disease,
                    'is_healthy': is_healthy,
                    'confidence': confidence,
                    'confidence_percentage': round(confidence * 100, 2)
                },
                'all_predictions': [
                    {
                        'class': self.class_names[i],
                        'confidence': float(predictions[0][i]),
                        'confidence_percentage': round(float(predictions[0][i]) * 100, 2)
                    }
                    for i in range(len(self.class_names))
                ]
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'prediction': None
            }
    
    def predict_from_path(self, image_path: str) -> Dict[str, Any]:
        """
        Predict crop disease from image file path
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing prediction results
        """
        if self.model is None:
            return {
                'success': False,
                'error': 'Model not loaded. Please check model file and compatibility.',
                'prediction': None
            }
        
        try:
            # Preprocess image
            processed_image = self.preprocess_image_from_path(image_path)
            
            # Make prediction
            predictions = self.model.predict(processed_image)
            
            # Get prediction results
            result_index = np.argmax(predictions)
            confidence = float(np.max(predictions))
            predicted_class = self.class_names[result_index]
            
            # Extract crop and disease information
            crop_disease_parts = predicted_class.split('___')
            crop = crop_disease_parts[0].replace('_', ' ')
            disease = crop_disease_parts[1].replace('_', ' ') if len(crop_disease_parts) > 1 else 'Unknown'
            
            # Determine if healthy or diseased
            is_healthy = 'healthy' in disease.lower()
            
            return {
                'success': True,
                'prediction': {
                    'class': predicted_class,
                    'crop': crop,
                    'disease': disease,
                    'is_healthy': is_healthy,
                    'confidence': confidence,
                    'confidence_percentage': round(confidence * 100, 2)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'prediction': None
            }

# Legacy function for backward compatibility
def model_prediction(test_image: str) -> int:
    """
    Legacy function for model prediction (returns only index)
    
    Args:
        test_image: Path to the test image
        
    Returns:
        Index of the predicted class
    """
    detector = CropDiseaseDetector()
    result = detector.predict_from_path(test_image)
    
    if result['success']:
        # Find the index of the predicted class
        predicted_class = result['prediction']['class']
        return detector.class_names.index(predicted_class)
    else:
        raise RuntimeError(f"Prediction failed: {result['error']}")

# Initialize global detector instance (will be created when needed)
crop_disease_detector = None

def get_crop_disease_detector():
    """Get or create the crop disease detector instance"""
    global crop_disease_detector
    if crop_disease_detector is None:
        crop_disease_detector = CropDiseaseDetector()
    return crop_disease_detector
