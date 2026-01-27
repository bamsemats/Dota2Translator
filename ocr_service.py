import numpy as np
import cv2
import pytesseract
from PIL import Image

# NOTE: You must have Tesseract installed on your system for this to work.
# Please see the README.md for installation instructions.
# You may also need to configure the path to the Tesseract executable.
# Example for Windows:
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


class OcrService:
    def __init__(self):
        pass

    def preprocess_for_dota(self, pil_image):
        """
        Primary processing pipeline for light text on a dark/semi-transparent background.
        Uses HSV color masking.
        """
        numpy_image = np.array(pil_image)
        img = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        lower_white = np.array([0, 0, 150])
        upper_white = np.array([255, 100, 255])
        white_mask = cv2.inRange(hsv, lower_white, upper_white)
        
        lower_blue = np.array([85, 100, 200])
        upper_blue = np.array([110, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        
        combined_mask = cv2.bitwise_or(white_mask, blue_mask)
        
        kernel = np.ones((2, 2), np.uint8)
        opened_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        
        result_img = np.zeros_like(img)
        result_img[opened_mask > 0] = (255, 255, 255)
        
        return result_img

    def preprocess_for_transparent_bg(self, pil_image):
        """
        Secondary processing pipeline for light text on a complex/transparent background.
        Uses grayscale and a high binary threshold, followed by noise reduction.
        """
        numpy_image = np.array(pil_image)
        img = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply a high binary threshold to isolate very bright pixels (the text).
        _, threshold_img = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        # Use MORPH_OPEN to remove small noise artifacts after thresholding.
        kernel = np.ones((2, 2), np.uint8)
        opened_img = cv2.morphologyEx(threshold_img, cv2.MORPH_OPEN, kernel, iterations=1)

        return opened_img

    def extract_text_from_image(self, pil_image):
        """
        Extract text using a two-pass OCR strategy.
        Pass 1: Assumes a dark background.
        Pass 2: Assumes a transparent/complex background.
        """
        # DEBUG: Save the original screenshot
        pil_image.save("ocr_debug_original.png")

        try:
            # --- PASS 1: Try the method for dark backgrounds ---
            processed_img_pass1 = self.preprocess_for_dota(pil_image)
            cv2.imwrite("ocr_debug_processed_pass1.png", processed_img_pass1)
            
            config = '--oem 1 --psm 3'
            lang_list = 'eng+rus+spa+por+chi_sim+swe' # Added Swedish
            
            all_text = pytesseract.image_to_string(
                processed_img_pass1,
                lang=lang_list,
                config=config
            )

            # --- PASS 2: If Pass 1 fails, try the transparent background method ---
            if not all_text.strip():
                print("Primary OCR pass found no text. Trying secondary pass for transparent backgrounds...")
                processed_img_pass2 = self.preprocess_for_transparent_bg(pil_image)
                cv2.imwrite("ocr_debug_processed_pass2.png", processed_img_pass2)
                
                all_text = pytesseract.image_to_string(
                    processed_img_pass2,
                    lang=lang_list,
                    config=config
                )

            # --- Process and return the final result ---
            extracted_lines = []
            for line_text in all_text.split('\n'):
                line_text = line_text.strip()
                if line_text:
                    extracted_lines.append({
                        "text": line_text,
                        "language": "und" 
                    })
            
            return extracted_lines
            
        except pytesseract.TesseractNotFoundError:
            print("ERROR: Tesseract is not installed or not in your PATH.")
            return [{"text": "TESSERACT NOT FOUND. Please install it.", "language": "en"}]
        except Exception as e:
            print(f"Error during local OCR with Tesseract: {e}")
            return []
