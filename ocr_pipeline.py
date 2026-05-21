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
from usage_tracker import UsageTracker
from langdetect import detect, DetectorFactory
from utils.anchors import AnchorDetector
import logging

# Ensure consistent language detection results
DetectorFactory.seed = 0

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
        self.translation_service = None 
        self.usage_tracker = UsageTracker()

    def set_translation_service(self, translation_service):
        self.translation_service = translation_service

    def run(self, region, enabled_iso=None, on_first_frame=None):
        """
        Fast & Accurate Full-ROI Pipeline:
        1. Quick Capture
        2. Visual Anchor Detection (Fast CV)
        3. Single Full-ROI OCR (Capped at 2000px for Speed)
        4. Robust Horizontal Merging & Multi-line Support
        5. Hinted Language Detection & Translation
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
        
        # 2. Visual Anchor Detection (Fast CV)
        with Benchmark("Visual Anchor Detection"):
            anchors = self.anchor_detector.find_anchors(merged)
        
        # 3. Single Pass Full-ROI OCR
        self.usage_tracker.increment_ocr_requests()
        
        # We cap width at 2000px in preprocess to keep detection fast (~1.2s)
        is_japan = self.ocr_service.lang == "japan"
        processed = self.preprocess_service.process_for_ocr(merged, preserve_details=is_japan)
        ocr_results = self.ocr_service.extract_text(processed)
        
        if not ocr_results:
            return []
        
        # ... (rest of logic) ...
        # (I'll just replace the whole run method to be safe and clean)

        # 4. Robust Line Merging
        # Merges words into full horizontal lines with strict X-sorting
        lines = self._merge_ocr_lines(ocr_results)
        
        # 5. Multi-line Grouping based on Anchors
        logical_messages = []
        current_msg = None
        
        # Map anchors to processed space
        scale_f = processed.shape[0] / merged.shape[0]
        
        for line in lines:
            text = line["text"].strip()
            y_center = self._get_y_center(line["bbox"])
            x_start = self._get_x_start(line["bbox"])
            
            # Check for anchor alignment
            is_head = any(abs(y_center - (a[1] * scale_f)) < 20 for a in anchors)
            
            parsed = self.parser.parse_line(text)
            
            # Heuristic: If we don't have a visual anchor, 
            # we check for explicit tags or sender patterns.
            if not is_head:
                is_head = parsed["sender"] is not None or parsed["tag"] is not None
                
            # Second heuristic: If it starts too far to the right, it's likely a continuation
            # (In Dota chat, tags/senders start at the very left)
            if x_start > 200 * scale_f:
                is_head = False

            if is_head:
                current_msg = {
                    "sender": parsed["sender"] if parsed["sender"] else "Unknown",
                    "tag": parsed["tag"],
                    "message_parts": [parsed["message"]],
                    "original_full": text,
                    "confidence": line["confidence"]
                }
                logical_messages.append(current_msg)
            elif current_msg:
                # Append continuation line
                current_msg["message_parts"].append(text)
                current_msg["original_full"] += " " + text
        
        # 6. Finalize, Translate & Deduplicate
        final_results = []
        for msg in logical_messages:
            full_message = " ".join(msg["message_parts"]).strip()
            original_full = msg["original_full"].strip()
            
            if not full_message or len(full_message) < 2:
                continue
            
            # Deduplicate on Original to allow unique foreign messages with same translation
            if not self.deduplicator.is_new(original_full):
                continue

            translated_message = full_message
            detected_lang = "unknown"
            
            if len(full_message) > 2:
                try:
                    # Hinted LangDetect
                    from langdetect import detect_langs
                    probs = detect_langs(full_message)
                    if enabled_iso:
                        enabled_probs = [p for p in probs if p.lang in enabled_iso]
                        detected_lang = enabled_probs[0].lang if enabled_probs else probs[0].lang
                    else:
                        detected_lang = probs[0].lang
                    
                    if detected_lang != 'en' and self.translation_service:
                        self.usage_tracker.increment_translation_characters(len(full_message))
                        _, translated_message = self.translation_service.translate_text(full_message)
                except Exception as e:
                    logger.warning(f"Translation error: {e}")

            lang_tag = f"[{detected_lang.upper()}] " if detected_lang != 'en' and detected_lang != 'unknown' else ""
            tag_str = f"[{msg['tag']}] " if msg["tag"] else ""
            sender = msg["sender"]
            
            final_results.append({
                "original": original_full,
                "translated": f"{lang_tag}{tag_str}{sender}: {translated_message}",
                "lang": detected_lang,
                "sender": sender,
                "message": full_message,
                "translated_message": translated_message,
                "confidence": msg["confidence"],
                "bbox": [0, 0, 0, 0]
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

    def _merge_ocr_lines(self, results, y_threshold=18):
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
