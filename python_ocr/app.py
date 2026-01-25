import os
from flask import Flask, request, jsonify
import numpy as np
import cv2
import io
from google.cloud import vision
from google.cloud import translate_v3 as translate # Added import for Translation API
from google.oauth2 import service_account

app = Flask(__name__)
app.json.ensure_ascii = False # Try to preserve Unicode

# --- Google Cloud Vision Initialization ---
# Prioritize GOOGLE_APPLICATION_CREDENTIALS environment variable
if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
    credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    print(f"Loading credentials from GOOGLE_APPLICATION_CREDENTIALS: {credentials_path}")
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
else:
    # Fallback to local gcp_credentials.json
    credentials_path = os.path.join(os.path.dirname(__file__), 'gcp_credentials.json')
    print(f"Loading credentials from local file: {credentials_path}")
    credentials = service_account.Credentials.from_service_account_file(credentials_path)

vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# --- Google Cloud Translation Initialization --- # Added Translation Client
translate_client = translate.TranslationServiceClient(credentials=credentials)
project_id = credentials.project_id # Get project ID from credentials

def preprocess_for_dota(img):
    """
    A processing pipeline that isolates both the white chat text and
    the light-blue player names to provide full line context to the OCR.
    """
    # 1. Convert image from BGR to HSV color space
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 2. Define HSV ranges for white text and the light-blue player name.
    # Permissive White (for '[Allies]', messages, etc.)
    lower_white = np.array([0, 0, 150])
    upper_white = np.array([255, 100, 255])
    white_mask = cv2.inRange(hsv, lower_white, upper_white)

    # Light Blue (for the specific player name in debug_original.png)
    lower_blue = np.array([85, 100, 200])
    upper_blue = np.array([110, 255, 255])
    blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

    # 3. Combine the masks
    combined_mask = cv2.bitwise_or(white_mask, blue_mask)

    # 4. Clean up the mask with morphological operations
    kernel = np.ones((2, 2), np.uint8)
    cleaned_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    # 5. Create a black background and place the masked text on it
    result_img = np.zeros_like(img)
    result_img[cleaned_mask > 0] = (255, 255, 255) # Make the masked area white

    return result_img

@app.route('/ocr', methods=['POST'])
def ocr_endpoint():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    if not file:
        return "Invalid file", 400

    try:
        # Read image file into memory
        in_memory_file = io.BytesIO()
        file.save(in_memory_file)
        in_memory_file.seek(0)
        content = in_memory_file.read()
        
        # Decode image with OpenCV to preprocess it
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Call the Google Cloud Vision API with the original image content
        gcp_image = vision.Image(content=content)
        response = vision_client.text_detection(image=gcp_image)
        
        if response.error.message:
            raise Exception(f'Google Cloud Vision API error: {response.error.message}')

        extracted_lines = []
        if response.text_annotations:
            # The first text annotation is the entire page
            full_text = response.text_annotations[0].description
            # Split the full text into lines based on newline characters
            # This is a simplification; for more precise line detection,
            # one might process individual text_annotations more carefully
            lines_from_vision = full_text.split('\n')

            for line_text in lines_from_vision:
                line_text = line_text.strip()
                if line_text: # Only process non-empty lines
                    # Detect language for each line using Translation API
                    parent = f"projects/{project_id}/locations/global"
                    lang_detect_response = translate_client.detect_language(
                        parent=parent,
                        content=line_text,
                        mime_type="text/plain"
                    )
                    detected_language = "und" # Undetermined by default
                    if lang_detect_response.languages:
                        # Take the language with the highest confidence
                        detected_language = max(lang_detect_response.languages, key=lambda x: x.confidence).language_code
                    
                    extracted_lines.append({
                        "text": line_text,
                        "language": detected_language
                    })
        
        # Log for debugging
        print(f"Extracted Lines: {extracted_lines}")

        return jsonify(extracted_lines)

    except Exception as e:
        print(f"An error occurred: {e}")
        # Check for auth errors specifically
        if "Could not automatically determine credentials" in str(e):
             print("Authentication failed. Did you set the GOOGLE_APPLICATION_CREDENTIALS environment variable?")
        return f"An internal error occurred: {e}", 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)