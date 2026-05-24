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
        Applies aggressive preprocessing for difficult transparent backgrounds.
        Uses refined HSV masking to isolate text while minimizing UI artifacts.
        """
        with Benchmark("Image Preprocessing (Refined HSV)"):
            h, w = image.shape[:2]
            
            # 1. High-Quality Scaling
            target_w = 2500
            scale = target_w / w
            image = cv2.resize(image, (target_w, int(h * scale)), interpolation=cv2.INTER_LANCZOS4)

            # 2. HSV Color Isolation
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # White Text: Targeted range to avoid bright background elements
            white_mask = cv2.inRange(hsv, (0, 0, 180), (180, 60, 255))
            
            # Player Colors: Lower saturation threshold to capture more text
            color_mask = cv2.inRange(hsv, (0, 50, 50), (180, 255, 255))
            
            # Combine masks
            combined_mask = cv2.bitwise_or(white_mask, color_mask)
            
            # 3. Apply mask to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            masked_gray = cv2.bitwise_and(gray, gray, mask=combined_mask)

            # 4. Add Margin Padding
            processed = cv2.copyMakeBorder(masked_gray, 40, 40, 60, 40, cv2.BORDER_CONSTANT, value=[0, 0, 0])

            # 5. Contrast Enhancement (Lower clipLimit to avoid halo artifacts)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            processed = clahe.apply(processed)

            # 6. Denoising
            # Removes small artifacts without being as destructive as Morph Open
            processed = cv2.bilateralFilter(processed, 5, 60, 60)
            
            # 7. Subtle Sharpening (Avoids 'shimmer' artifacts)
            sharpen_kernel = np.array([[0, -0.5, 0], [-0.5, 3, -0.5], [0, -0.5, 0]])
            processed = cv2.filter2D(processed, -1, sharpen_kernel)

        return processed

    def get_hsv_mask(self, image, lower_hsv, upper_hsv):
        """
        Isolates bright text using HSV masking.
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower_hsv, upper_hsv)
        return mask
