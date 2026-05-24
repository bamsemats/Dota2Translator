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
    def __init__(self, lang='en', use_gpu=False, det_db_unclip_ratio=2.0, det_limit_side_len=1600):
        """
        Initializes PaddleOCR.
        lang: 'en', 'ru', 'japan', 'ch', etc.
        """
        self.lang = lang
        self.device = 'gpu' if use_gpu else 'cpu'
        self.det_db_unclip_ratio = det_db_unclip_ratio
        self.det_limit_side_len = det_limit_side_len
        self.ocr = self._initialize_ocr()

    def _initialize_ocr(self):
        with Benchmark(f"Initializing PaddleOCR ({self.lang})"):
            # RESTORE: Specific models are more precise than general multilingual for these scripts.
            rec_model_map = {
                'en': 'latin_PP-OCRv3_mobile_rec', # Latin model handles Swedish diacritics better than plain English
                'latin': 'latin_PP-OCRv3_mobile_rec',
                'ru': 'cyrillic_PP-OCRv5_mobile_rec',
                'ch': 'PP-OCRv5_mobile_rec', 
                'japan': 'PP-OCRv5_mobile_rec',
                'korean': 'korean_PP-OCRv5_mobile_rec'
            }
            rec_model = rec_model_map.get(self.lang, 'latin_PP-OCRv3_mobile_rec')
            
            # Note: We still use 'en' as the primary lang for detector/recognizer components
            # but the actual weights will be the v5 mobile ones where available.
            return PaddleOCR(
                lang='latin' if self.lang in ['en', 'latin'] else self.lang, 
                device=self.device,
                use_textline_orientation=False, 
                text_detection_model_name='PP-OCRv5_mobile_det',
                text_recognition_model_name=rec_model,
                text_det_limit_side_len=self.det_limit_side_len,
                # REFINED PARAMETERS:
                det_db_unclip_ratio=self.det_db_unclip_ratio, 
                det_db_thresh=0.4,        # Restore balanced sensitivity
                det_db_box_thresh=0.6,    # Slightly stricter box filtering
                enable_mkldnn=False,
                rec_batch_num=6
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
        
        # Format 1: Dictionary (Paddlex)
        if isinstance(data_block, dict):
            texts = data_block.get("rec_texts", [])
            scores = data_block.get("rec_scores", [])
            # Favor polys for better geometry, fallback to boxes
            shapes = data_block.get("rec_polys", data_block.get("rec_boxes", []))
            
            for i in range(len(texts)):
                bbox = shapes[i]
                # Ensure bbox is a standard list
                if hasattr(bbox, 'tolist'):
                    bbox = bbox.tolist()
                
                parsed_results.append({
                    "text": texts[i],
                    "confidence": scores[i] if i < len(scores) else 0.0,
                    "bbox": bbox
                })
            return parsed_results

        # Format 2: List (Legacy)
        # Format: [ [[bbox], [text, conf]], ... ]
        for line in data_block:
            try:
                if len(line) >= 2 and isinstance(line[1], (list, tuple)):
                    bbox = line[0]
                    text, confidence = line[1]
                    parsed_results.append({
                        "text": text,
                        "confidence": confidence,
                        "bbox": bbox
                    })
            except:
                continue
        
        return parsed_results

    def recognize_only(self, image):
        """
        Performs recognition ONLY by calling the underlying PaddleX recognizer component.
        This is the fastest possible way to OCR a single row.
        """
        if image is None or image.size == 0:
            return None

        if len(image.shape) == 2:
            image_ocr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            image_ocr = image

        with Benchmark("PaddleOCR Recognition Only (Direct)"):
            try:
                # Use the internal PaddleX pipeline component if available for max speed
                if hasattr(self.ocr, 'paddlex_pipeline'):
                    pipeline = self.ocr.paddlex_pipeline
                    # Check for text_rec_model (PaddleX 3.x)
                    if hasattr(pipeline, 'text_rec_model'):
                        # PaddleX models return a generator, convert to list
                        res = list(pipeline.text_rec_model(image_ocr))
                        if res and len(res) > 0:
                            data = res[0]
                            # PaddleX 3.x output format
                            return {
                                "text": data.get("rec_text", ""),
                                "confidence": data.get("rec_score", 0.0)
                            }
                
                # Fallback to standard ocr call (might fail on 3.x if det=False is removed)
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
        valid_indices = []
        for i, img in enumerate(images):
            if img is not None and img.size > 0:
                if len(img.shape) == 2:
                    processed_images.append(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
                else:
                    processed_images.append(img)
                valid_indices.append(i)

        if not processed_images:
            return [None] * len(images)

        results = [None] * len(images)
        with Benchmark(f"PaddleOCR Batch Recognition ({len(processed_images)} valid crops)"):
            try:
                batch_res = []
                if hasattr(self.ocr, 'paddlex_pipeline'):
                    pipeline = self.ocr.paddlex_pipeline
                    if hasattr(pipeline, 'text_rec_model'):
                        # Batch call to text_rec_model
                        batch_res = pipeline.text_rec_model(processed_images)
                
                if batch_res:
                    for idx, data in zip(valid_indices, batch_res):
                        results[idx] = {
                            "text": data.get("rec_text", ""),
                            "confidence": data.get("rec_score", 0.0)
                        }
                else:
                    # Fallback
                    for idx, img in zip(valid_indices, processed_images):
                        res = self.ocr.ocr(img, det=False)
                        if res and res[0]:
                            text, confidence = res[0][0]
                            results[idx] = {"text": text, "confidence": confidence}
            except Exception as e:
                logging.error(f"Batch Recognition Error: {e}")
        
        return results

    def set_language(self, lang):
        if self.lang != lang:
            self.lang = lang
            self.ocr = self._initialize_ocr()
