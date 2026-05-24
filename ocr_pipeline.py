import os
import cv2
import re
import numpy as np
from capture.capture_service import CaptureService
from preprocess.preprocess_service import PreprocessService
from ocr.ocr_service import OcrService
from translate.translation_service import TranslationService
from utils.deduplicator import Deduplicator
from utils.benchmark import Benchmark
from utils.parser import ChatParser
from utils.corrector import PostProcessor
from usage_tracker import UsageTracker
from utils.anchors import AnchorDetector
from lingua import Language, LanguageDetectorBuilder
import logging

# Ensure consistent language detection results
# Configure Lingua with realistic Dota 2 languages
SUPPORTED_LANGS = [
    Language.SWEDISH, Language.BOKMAL, Language.DANISH, 
    Language.ENGLISH, Language.SPANISH, Language.PORTUGUESE, 
    Language.RUSSIAN, Language.TURKISH, Language.GERMAN, 
    Language.FRENCH, Language.POLISH
]
detector = LanguageDetectorBuilder.from_languages(*SUPPORTED_LANGS).build()

logger = logging.getLogger(__name__)

class OcrPipeline:
    def __init__(self, config):
        self.config = config
        self.capture_service = CaptureService()
        self.preprocess_service = PreprocessService(upscale_factor=2)
        
        self.ocr_service = OcrService(lang='en', use_gpu=False)
        self.anchor_detector = AnchorDetector()
        
        self.deduplicator = Deduplicator(threshold=97)
        self.parser = ChatParser()
        self.post_processor = PostProcessor()
        self.translation_service = None 
        self.anthropic_service = None # Added for high-quality translation
        self.usage_tracker = UsageTracker()

    def set_translation_service(self, translation_service):
        self.translation_service = translation_service

    def set_anthropic_service(self, anthropic_service):
        self.anthropic_service = anthropic_service

    def run(self, region, enabled_iso=None, on_first_frame=None):
        """
        STABILIZED MODE: Surgical Slicing + Direct Recognition + Verified Post-processing.
        """
        if not region:
            return []

        # 1. Capture & Merge
        frames = self.capture_service.capture_frames(region, num_frames=3, interval_ms=10)
        if not frames:
            return []
            
        if on_first_frame and len(frames) > 0:
            on_first_frame(frames[0])

        merged = self.preprocess_service.merge_frames(frames)
        h_orig, w_orig = merged.shape[:2]
        
        # 2. SURGICAL ROW DETECTION: Use blue username anchors on raw image
        y_centers = self.anchor_detector.find_chat_line_anchors(merged)
        
        # Select best model based on hints
        if enabled_iso and any(iso in ['ru', 'zh', 'ja', 'ko'] for iso in enabled_iso):
            # Use multilingual model if non-Latin hints are present
            target_lang = 'ru' 
            if 'ja' in enabled_iso: target_lang = 'japan'
            elif 'zh' in enabled_iso: target_lang = 'ch'
            self.ocr_service.set_language(target_lang)
        
        crops = []
        row_bboxes = []
        
        if y_centers:
            # Calculate dynamic line height from gaps
            if len(y_centers) >= 2:
                avg_gap = np.mean(np.diff(y_centers))
                half_h = int(avg_gap / 2) + 5
            else:
                half_h = 25 # Fallback for 1080p
            
            for cy in y_centers:
                y1 = max(0, cy - half_h)
                y2 = min(h_orig, cy + half_h)
                
                # Slice RAW merged image (BGR) for max fidelity
                # Widened x-crop to ensure [Allies] prefix isn't cut off
                crop = merged[y1:y2, :] 
                
                # 3x Upscale for maximum recognition accuracy (Verified surgical improvement)
                hc, wc = crop.shape[:2]
                if hc > 0 and wc > 0:
                    upscaled = cv2.resize(crop, (wc*3, hc*3), interpolation=cv2.INTER_LANCZOS4)
                    crops.append(upscaled)
                    row_bboxes.append([0, y1, w_orig, y2 - y1])
        else:
            # Fallback: Detect any text bands (projection profile)
            raw_rows = self.anchor_detector.find_all_rows(merged)
            if raw_rows:
                for y1, y2 in raw_rows:
                    crop = merged[max(0, y1-5):min(h_orig, y2+5), :]
                    hc, wc = crop.shape[:2]
                    upscaled = cv2.resize(crop, (wc*2, hc*2), interpolation=cv2.INTER_LANCZOS4)
                    crops.append(upscaled)
                    row_bboxes.append([0, y1, w_orig, y2 - y1])
            else:
                # Last resort: Blind slice
                num_lines = 6
                row_h = h_orig // num_lines
                for i in range(num_lines):
                    y1, y2 = i * row_h, (i + 1) * row_h
                    crops.append(merged[y1:y2, :])
                    row_bboxes.append([0, y1, w_orig, row_h])

        # 3. BATCH RECOGNITION (Direct recognition, no detector)
        self.usage_tracker.increment_ocr_requests()
        with Benchmark(f"PaddleOCR Batch Recognition ({len(crops)} lines)"):
            rec_results = self.ocr_service.batch_recognize_only(crops)
        
        if not rec_results:
            return []

        # 4. Parse, Clean & Translate
        final_results = []
        for i, res in enumerate(rec_results):
            if not res or not res["text"] or len(res["text"].strip()) < 2:
                continue
                
            text = res["text"].strip()
            confidence = res["confidence"]
            bbox = row_bboxes[i]
            
            # DEBUG: See what the recognizer actually sees
            logger.info(f"RAW OCR Line {i} (Conf: {confidence:.2f}): '{text}'")
            
            # Apply minimal, verified cleaning
            is_sv = enabled_iso and 'sv' in enabled_iso
            text = self.post_processor.clean_text(text, is_swedish=is_sv)
            
            # Parse structure (Sender: Message)
            parsed = self.parser.parse_line(text)
            
            # Deduplicate based on original text
            if not self.deduplicator.is_new(text):
                continue

            full_message = parsed["message"] if parsed["message"] else text
            translated_message = full_message
            detected_lang = "unknown"
            
            # Language Detection & Translation
            if len(full_message) > 2:
                try:
                    # 1. Get Lingua detection as a baseline hint
                    conf_values = detector.compute_language_confidence_values(full_message)
                    top_res = conf_values[0] if conf_values else None
                    lingua_hint = None
                    if top_res:
                        lingua_hint = top_res.language.iso_code_639_1.name.lower()
                        if lingua_hint == 'nb': lingua_hint = 'no'

                    # 2. Use Anthropic for high-quality translation if available
                    if self.anthropic_service:
                        res = self.anthropic_service.translate_message(full_message, hint_lang=lingua_hint)
                        if res:
                            detected_lang = res.get("lang", lingua_hint if lingua_hint else "unknown")
                            translated_message = res.get("translation", full_message)
                    else:
                        # Fallback to Google + Lingua logic
                        detected_lang = lingua_hint if lingua_hint else "unknown"
                        
                        # Apply confidence threshold for short strings
                        word_count = len(full_message.split())
                        if top_res and word_count < 8 and top_res.value < 0.7:
                            detected_lang = "?"
                        
                        # Swedish-specific Nordic diacritic override
                        if any(c in full_message.lower() for c in 'åäö'):
                            if detected_lang in ['no', 'da']:
                                detected_lang = 'sv'
                                
                        if detected_lang not in ['en', '?'] and self.translation_service:
                            self.usage_tracker.increment_translation_characters(len(full_message))
                            _, translated_message = self.translation_service.translate_text(full_message)
                except Exception as e:
                    logger.warning(f"Translation/Detection error: {e}")

            channel_str = f"[{parsed['channel']}] " if parsed["channel"] else ""
            tag_str = f" [{parsed['tag']}]" if parsed["tag"] else ""
            sender = parsed["sender"] if parsed["sender"] else "Unknown"
            
            final_results.append({
                "original": text,
                "translated": f"{channel_str}{sender}{tag_str}: {translated_message}",
                "lang": detected_lang,
                "sender": sender,
                "message": full_message,
                "translated_message": translated_message,
                "confidence": confidence,
                "bbox": bbox
            })
        
        return final_results

    def _get_y_center(self, bbox):
        if isinstance(bbox[0], (list, np.ndarray)):
            return (bbox[0][1] + bbox[2][1]) / 2
        return (bbox[1] + bbox[3]) / 2

    def _get_x_start(self, bbox):
        if isinstance(bbox[0], (list, np.ndarray)):
            return min(p[0] for p in bbox)
        return bbox[0]

    def _merge_ocr_lines(self, results, y_threshold=30):
        """
        Groups OCR fragments into horizontal lines and sorts them by X.
        """
        if not results: return []
        
        sorted_by_y = sorted(results, key=lambda x: self._get_y_center(x["bbox"]))
        rows = []
        if not sorted_by_y: return []
        
        current_row = [sorted_by_y[0]]
        for res in sorted_by_y[1:]:
            if abs(self._get_y_center(res["bbox"]) - self._get_y_center(current_row[-1]["bbox"])) < y_threshold:
                current_row.append(res)
            else:
                rows.append(current_row)
                current_row = [res]
        rows.append(current_row)
        
        merged = []
        for row in rows:
            # STRICT X-SORTING: Fixes scrambled text
            row.sort(key=lambda x: self._get_x_start(x["bbox"]))
            
            merged_text = " ".join([r["text"] for r in row])
            merged_text = re.sub(r"\s+", " ", merged_text).strip()
            
            merged.append({
                "text": merged_text,
                "confidence": sum(r["confidence"] for r in row) / len(row),
                "bbox": row[0]["bbox"]
            })
        return merged
