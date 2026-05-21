from paddleocr import PaddleOCR
import paddle
import cv2
import numpy as np
import logging
from utils.benchmark import Benchmark

import os

# Suppress PaddleOCR logging
logging.getLogger("ppocr").setLevel(logging.ERROR)

# Optimization: Bypass connectivity checks for model hosters
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

# Fix for PaddlePaddle 3.0+ regression: disable PIR API and oneDNN
try:
    paddle.set_flags({'FLAGS_enable_pir_api': 0})
except:
    pass

class OcrService:
    def __init__(self, lang='en', use_gpu=False):
        """
        Initializes PaddleOCR.
        lang: 'en', 'ru', 'japan', 'ch', etc.
        """
        self.lang = lang
        self.device = 'gpu' if use_gpu else 'cpu'
        self.ocr = self._initialize_ocr()

    def _initialize_ocr(self):
        with Benchmark(f"Initializing PaddleOCR ({self.lang})"):
            # Aligned with PaddleOCR 3.5.0 / PaddleX API
            # Explicitly mapping common languages to their PaddleX registry names
            # to avoid the slow 'server' detection model being used by default.
            
            rec_model_map = {
                'en': 'en_PP-OCRv5_mobile_rec',
                'ru': 'cyrillic_PP-OCRv5_mobile_rec',
                'ch': 'PP-OCRv5_mobile_rec', 
                'japan': 'PP-OCRv5_mobile_rec', # v5 Multilingual is excellent for Japanese
                'korean': 'korean_PP-OCRv5_mobile_rec'
            }
            
            rec_model = rec_model_map.get(self.lang, 'PP-OCRv5_mobile_rec')
            
            return PaddleOCR(
                lang=self.lang, 
                device=self.device,
                use_textline_orientation=False, 
                text_detection_model_name='PP-OCRv5_mobile_det',
                text_recognition_model_name=rec_model,
                text_det_limit_side_len=1600,   # FAST: ~1.2s on full 4K ROI
                enable_mkldnn=False,
                rec_batch_num=10
            )

    def extract_text(self, image):
        """
        Performs full OCR (Detection + Recognition) on the image.
        Used for legacy support or complex layouts.
        """
        if image is None:
            return []

        with Benchmark("PaddleOCR Full Extraction"):
            if len(image.shape) == 2:
                image_ocr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            else:
                image_ocr = image

            result = self.ocr.ocr(image_ocr)
            
        return self._parse_result(result)

    def recognize_text(self, image):
        """
        Performs recognition on a single row.
        Handles both list and dictionary result formats from PaddleOCR.
        """
        if image is None:
            return None

        # PaddleOCR recognition expects BGR
        if len(image.shape) == 2:
            image_ocr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            image_ocr = image

        with Benchmark("PaddleOCR Row Recognition"):
            result = self.ocr.ocr(image_ocr)
        
        if not result or not result[0]:
            return None
            
        data = result[0]
        
        # Format 1: Dictionary (Common in newer PaddleX-based PaddleOCR)
        # {'rec_texts': [...], 'rec_scores': [...], 'rec_boxes': [...]}
        if isinstance(data, dict):
            texts = data.get("rec_texts", [])
            scores = data.get("rec_scores", [])
            if texts:
                return {
                    "text": texts[0],
                    "confidence": scores[0] if scores else 0.0
                }
            return None

        # Format 2: List (Legacy format)
        # [ [[bbox], [text, conf]], ... ]
        if isinstance(data, list) and len(data) > 0:
            line = data[0]
            if len(line) >= 2 and isinstance(line[1], (list, tuple)):
                # Standard line: [[bbox], [text, conf]]
                text, confidence = line[1]
                return {
                    "text": text,
                    "confidence": confidence
                }
            elif isinstance(line, (list, tuple)) and len(line) == 2 and isinstance(line[0], str):
                # Recognition-only style: [text, conf]
                text, confidence = line
                return {
                    "text": text,
                    "confidence": confidence
                }
        
        return None

    def _parse_result(self, result):
        parsed_results = []
        if not result or not result[0]:
            return []

        data_block = result[0]
        
        # Format 1: Dictionary
        if isinstance(data_block, dict):
            texts = data_block.get("rec_texts", [])
            scores = data_block.get("rec_scores", [])
            boxes = data_block.get("rec_boxes", [])
            for i in range(len(texts)):
                parsed_results.append({
                    "text": texts[i],
                    "confidence": scores[i] if i < len(scores) else 0.0,
                    "bbox": boxes[i] if i < len(boxes) else []
                })
            return parsed_results

        # Format 2: List
        # Format: [ [[bbox], [text, conf]], ... ]
        for line in data_block:
            if len(line) >= 2:
                bbox = line[0]
                text, confidence = line[1]
                parsed_results.append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": bbox
                })
        
        return parsed_results

    def recognize_only(self, image):
        """
        Performs recognition ONLY by calling the underlying PaddleX recognizer component.
        This is the fastest possible way to OCR a single row.
        """
        if image is None:
            return None

        if len(image.shape) == 2:
            image_ocr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            image_ocr = image

        with Benchmark("PaddleOCR Recognition Only (Direct)"):
            try:
                # Use the internal PaddleX pipeline component if available for max speed
                if hasattr(self.ocr, 'paddlex_pipeline') and hasattr(self.ocr.paddlex_pipeline, 'text_rec_model'):
                    # The internal model takes a list of images or a single image
                    res = self.ocr.paddlex_pipeline.text_rec_model(image_ocr)
                    # Result format for text_rec_model is usually a list of dicts
                    if res and len(res) > 0:
                         data = res[0]
                         return {
                             "text": data.get("rec_text", ""),
                             "confidence": data.get("rec_score", 0.0)
                         }
                
                # Fallback to standard ocr call with det=False if above fails
                # (Note: newer PaddleOCR might still have issues with det=False, 
                # but the internal component call is the 'pro' way)
                result = self.ocr.ocr(image_ocr, det=False)
                if result and result[0]:
                    text, confidence = result[0][0]
                    return {"text": text, "confidence": confidence}
            except Exception as e:
                logging.error(f"Recognition Only Error: {e}")
        
        return None

    def batch_recognize_only(self, images):
        """
        Performs recognition on a batch of images.
        Extremely efficient for multiple small crops.
        """
        if not images:
            return []

        processed_images = []
        for img in images:
            if len(img.shape) == 2:
                processed_images.append(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
            else:
                processed_images.append(img)

        with Benchmark(f"PaddleOCR Batch Recognition ({len(images)} crops)"):
            # The ocr method can take a list of images in some versions,
            # but usually we want to call the internal predictor for batching.
            results = []
            for img in processed_images:
                # Still using ocr() for stability, but on small crops it's very fast
                res = self.ocr.ocr(img)
                results.append(res)
        
        parsed = []
        for res in results:
            if not res or not res[0]:
                parsed.append(None)
                continue
            
            data = res[0]
            if isinstance(data, dict):
                texts = data.get("rec_texts", [])
                scores = data.get("rec_scores", [])
                parsed.append({"text": texts[0] if texts else "", "confidence": scores[0] if scores else 0.0})
            else:
                # Handle list format
                try:
                    line = data[0]
                    if len(line) >= 2 and isinstance(line[1], (list, tuple)):
                        text, confidence = line[1]
                        parsed.append({"text": text, "confidence": confidence})
                    else:
                        parsed.append(None)
                except:
                    parsed.append(None)
        return parsed

    def set_language(self, lang):
        if self.lang != lang:
            self.lang = lang
            self.ocr = self._initialize_ocr()
