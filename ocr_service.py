import numpy as np
import cv2
import pytesseract
from PIL import Image

# NOTE: You must have Tesseract installed on your system for this to work.
# Please see the README.md for installation instructions.
# You may also need to configure the path to the Tesseract executable.
# Example for Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


class OcrService:
    def __init__(self):
        # project_id is no longer needed for local OCR
        # client is no longer needed
        # OCR usage tracking is no longer needed
        pass

    def preprocess_for_dota(self, pil_image):
        """
        A processing pipeline that isolates both the white chat text and
        the light-blue player names to provide full line context to the OCR.
        This method is unchanged and is critical for Tesseract's accuracy.
        :param pil_image: PIL Image object.
        :return: OpenCV image (numpy array) with processed text.
        """
        # Convert PIL Image to OpenCV format
        numpy_image = np.array(pil_image)
        img = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)

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

    def extract_text_from_image(self, pil_image):
        """
        Extract text from a PIL Image object using local Tesseract OCR.
        :param pil_image: PIL Image object of the screenshot.
        :return: List of dicts [{"text": "...", "language": "und"}, ...] or empty list.
        """
        # DEBUG: Save the original screenshot
        pil_image.save("ocr_debug_original.png")

        # Preprocess the image to improve OCR accuracy
        processed_img_cv = self.preprocess_for_dota(pil_image)

        # DEBUG: Save the processed image
        cv2.imwrite("ocr_debug_processed.png", processed_img_cv)

        try:
            # Use pytesseract to extract text.
            # We specify common languages in Dota 2 to aid detection.
            # Tesseract will attempt to recognize characters from all these languages.
            # For a full list of languages, run: print(pytesseract.get_languages(config=''))
            config = '-c tessedit_char_blacklist=[]' # Example config
            all_text = pytesseract.image_to_string(
                processed_img_cv,
                lang='eng+rus+spa+por+chi_sim', # English, Russian, Spanish, Portuguese, Simplified Chinese
                config=config
            )

            extracted_lines = []
            for line_text in all_text.split('\n'):
                line_text = line_text.strip()
                if line_text:
                    # The return format is kept consistent with the old service.
                    # Language detection is handled by the TranslationService.
                    extracted_lines.append({
                        "text": line_text,
                        "language": "und" 
                    })
            
            return extracted_lines
        except pytesseract.TesseractNotFoundError:
            print("ERROR: Tesseract is not installed or not in your PATH.")
            print("Please install Tesseract and/or configure the path to the executable.")
            # Return an empty list to prevent crashes and show a clear error in the console.
            return [{
                "text": "TESSERACT NOT FOUND. Please install it.",
                "language": "en"
            }]
        except Exception as e:
            print(f"Error during local OCR with Tesseract: {e}")
            return []
