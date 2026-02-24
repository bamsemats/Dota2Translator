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
        Uses expanded HSV color masking for common Dota chat colors.
        """
        numpy_image = np.array(pil_image)
        img = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Define color ranges for common Dota chat text
        # White
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 50, 255])
        white_mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # Blue (All-Chat/System/Teal)
        lower_blue = np.array([85, 100, 100])
        upper_blue = np.array([130, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # Green (Allies)
        lower_green = np.array([40, 100, 100])
        upper_green = np.array([80, 255, 255])
        green_mask = cv2.inRange(hsv, lower_green, upper_green)

        # Yellow/Gold/Orange (System/Names)
        lower_yellow = np.array([15, 100, 100])
        upper_yellow = np.array([35, 255, 255])
        yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)

        # Purple/Pink (Names)
        lower_purple = np.array([130, 100, 100])
        upper_purple = np.array([175, 255, 255])
        purple_mask = cv2.inRange(hsv, lower_purple, upper_purple)

        # Red (System/Enemies)
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        red_mask = cv2.bitwise_or(cv2.inRange(hsv, lower_red1, upper_red1), 
                                 cv2.inRange(hsv, lower_red2, upper_red2))
        
        # Combine all masks
        combined_mask = cv2.bitwise_or(white_mask, blue_mask)
        combined_mask = cv2.bitwise_or(combined_mask, green_mask)
        combined_mask = cv2.bitwise_or(combined_mask, yellow_mask)
        combined_mask = cv2.bitwise_or(combined_mask, purple_mask)
        combined_mask = cv2.bitwise_or(combined_mask, red_mask)
        
        # Clean up noise - using a slightly more balanced approach
        kernel = np.ones((1, 1), np.uint8)
        opened_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        
        # Final result: White text on black background
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
            
            # Reverting to PSM 4 which was reportedly better for character recognition
            config = '--oem 1 --psm 4'
            lang_list = 'eng+rus+spa+por+chi_sim' # Removed swe temporarily to rule out lang issues
            
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
                line_text = self.clean_ocr_text(line_text)
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

    def clean_ocr_text(self, text):
        """
        Removes common OCR artifacts and garbage characters.
        """
        text = text.strip()
        if not text:
            return ""

        # Remove very short lines that are likely just noise (e.g. single symbols)
        # but keep single words or letters if they might be part of chat.
        if len(text) == 1 and not text.isalnum():
            return ""

        # Remove common "edge noise" symbols that Tesseract often picks up from borders/icons
        # while keeping characters from supported languages.
        # We'll use a regex to keep alphanumeric, spaces, and basic punctuation
        # plus characters in the range of Russian/Chinese etc.
        # This is a bit complex, so we'll start with a simpler approach:
        # just strip some known bad characters.
        bad_chars = '§|\\_~`'
        for char in bad_chars:
            text = text.replace(char, '')

        return text.strip()
