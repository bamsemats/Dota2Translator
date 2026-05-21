import cv2
import numpy as np
from utils.benchmark import Benchmark

class PreprocessService:
    def __init__(self, upscale_factor=2):
        self.upscale_factor = upscale_factor

    def merge_frames(self, frames):
        """
        Merges multiple frames using max-blending to eliminate background noise.
        """
        if not frames:
            return None
        
        with Benchmark("Max-blending frames"):
            combined = np.max(frames, axis=0)
        return combined

    def process_for_ocr(self, image, preserve_details=False):
        """
        Applies stable grayscale preprocessing.
        Caps width at 2000px to ensure sub-2s latency on 4K systems.
        """
        with Benchmark("Image Preprocessing (Capped)"):
            h, w = image.shape[:2]
            
            # 1. Scaling (Crucial for Speed on 4K)
            # We cap width at 2000px. This is high enough for Japanese
            # but low enough to avoid PaddleOCR lag spikes.
            MAX_W = 2000
            scale = 1.0
            
            if w > MAX_W:
                scale = MAX_W / w
            elif w < 1000:
                scale = 2.0 # Upscale small regions
            
            if scale != 1.0:
                image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4)

            # 2. Grayscale & Contrast
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            processed = clahe.apply(gray)

            # 3. Denoise
            processed = cv2.bilateralFilter(processed, 9, 75, 75)

        return processed

    def get_hsv_mask(self, image, lower_hsv, upper_hsv):
        """
        Isolates bright text using HSV masking.
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower_hsv, upper_hsv)
        return mask
