import os
from capture.capture_service import CaptureService
from preprocess.preprocess_service import PreprocessService
from usage_tracker import UsageTracker
import cv2
import numpy as np
import re
import json
import base64
from config import AppConfig
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

CALIBRATION_FILE = "calibration.json"
CHAT_FORMAT_FILE = "chat_format.json"

class SurgicalOcrPipeline:
    def __init__(self, config=None):
        self.config = config if config else AppConfig()
        self.capture_service = CaptureService()
        self.preprocess_service = PreprocessService()
        self.usage_tracker = UsageTracker()
        self.seen_messages = set()
        
        self.translation_service = None
        self.anthropic_service = None
        self._app_ref = None
        
        # Geometry state (loaded from calibration)
        self.geo = {
            "chat_left": 95,
            "chat_top": 30,
            "chat_right": 1500,
            "chat_bottom": 360,
            "line_height": 55,
            "max_lines": 6
        }
        self.load_calibration()
        self.load_chat_format()
        self.lang = 'en'

    def load_calibration(self):
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE, "r") as f:
                    self.geo.update(json.load(f))
                logger.info(f"Loaded calibration: {self.geo}")
            except Exception as e:
                logger.error(f"Failed to load calibration: {e}")

    def save_calibration(self):
        try:
            with open(CALIBRATION_FILE, "w") as f:
                json.dump(self.geo, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")

    def load_chat_format(self):
        if not os.path.exists(CHAT_FORMAT_FILE):
            # Create a default if missing
            default = {
                "parser_regex": "^\\[?(?:Allies|All|Team|Party)\\]?\\s*(?:#[wW])?\\s*(.+?)\\s*(?:\\[\\w+\\])?\\s*[:;]\\s*(.+)",
                "system_keywords": ["bought back", "killed", "has", "tipped"],
                "sender_group": 1,
                "message_group": 2,
                "tag_label": "Allies"
            }
            with open(CHAT_FORMAT_FILE, "w") as f:
                json.dump(default, f, indent=2)
        
        try:
            with open(CHAT_FORMAT_FILE, "r") as f:
                raw_format = json.load(f)
                self.chat_format = {
                    "parser_regex": str(raw_format.get("parser_regex", "")),
                    "system_keywords": list(raw_format.get("system_keywords", [])),
                    "sender_group": int(raw_format.get("sender_group", 1)),
                    "message_group": int(raw_format.get("message_group", 2)),
                    "tag_label": str(raw_format.get("tag_label", "Chat"))
                }
        except Exception as e:
            logger.error(f"Failed to load chat format: {e}")

    def calibrate(self, region):
        """
        Auto-calibrates chat geometry using horizontal projection.
        """
        print("\n--- AUTO-CALIBRATION START ---")
        frames = self.capture_service.capture_frames(region, num_frames=1)
        if not frames: return "ERROR: Capture failed"
        
        img = frames[0]
        h, w = img.shape[:2]
        cv2.imwrite("calibration.png", img)
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        row_vars = [np.var(gray[row, :]) for row in range(h)]
        row_vars_smooth = np.convolve(row_vars, np.ones(5)/5, mode='same')
        
        peaks = []
        thresh = np.mean(row_vars_smooth) * 1.5
        for i in range(2, h-2):
            if row_vars_smooth[i] > thresh and row_vars_smooth[i] > row_vars_smooth[i-1] and row_vars_smooth[i] > row_vars_smooth[i+1]:
                if not peaks or (i - peaks[-1]) > 20:
                    peaks.append(i)
        
        if len(peaks) < 2:
            return "WARNING: Calibration needs at least 2 chat lines visible — please try again."
        
        gaps = np.diff(peaks)
        line_height = int(np.median(gaps))
        half_h = line_height // 2
        
        col_vars = np.zeros(w)
        for p in peaks:
            band = gray[max(0, p-5):min(h, p+5), :]
            for col in range(w): col_vars[col] += np.var(band[:, col])
        
        col_vars_smooth = np.convolve(col_vars, np.ones(10)/10, mode='same')
        col_thresh = np.mean(col_vars_smooth) * 0.5
        
        nonzero_cols = np.where(col_vars_smooth > col_thresh)[0]
        chat_left = int(nonzero_cols[0]) if len(nonzero_cols) > 0 else 0
        chat_right = min(int(nonzero_cols[-1]), 1500)

        self.geo.update({
            "chat_top": int(peaks[0] - half_h), "chat_bottom": int(peaks[-1] + half_h),
            "chat_left": chat_left, "chat_right": chat_right,
            "line_height": line_height, "max_lines": len(peaks)
        })
        self.save_calibration()
        print(f"CALIBRATION SUCCESS: {self.geo}")
        return "SUCCESS"

    def set_translation_service(self, translation_service):
        self.translation_service = translation_service

    def set_anthropic_service(self, anthropic_service):
        self._app_ref = None # Reset ref if explicit service injected
        self.anthropic_service = anthropic_service

    def set_language(self, lang):
        self.lang = lang
        logger.info(f"Target language context set to {lang}")

    def run(self, region, enabled_iso=None, on_first_frame=None):
        # Lazy anthropic service injection
        if self.anthropic_service is None and hasattr(self, '_app_ref') and self._app_ref is not None:
            self.anthropic_service = getattr(self._app_ref, 'anthropic_service', None)
            if self.anthropic_service is not None:
                print(f"Lazy injection result: {type(self.anthropic_service)}")
            
        print("CAPTURE START — all state cleared")
        if not region: return []

        frames = self.capture_service.capture_frames(region, num_frames=3, interval_ms=10)
        if not frames: return []
        
        if on_first_frame: on_first_frame(frames[0])
        img = self.preprocess_service.merge_frames(frames)
        h_orig, w_orig = img.shape[:2]
        print(f"Frame shape: {img.shape}")

        y_centers = []
        bottom_y = self.geo["chat_bottom"]
        for i in range(self.geo["max_lines"]):
            cy = bottom_y - (self.geo["line_height"] // 2) - (i * self.geo["line_height"])
            if cy < self.geo["chat_top"]: break
            y_centers.append(int(cy))

        raw_ocr_results = []
        self.usage_tracker.increment_ocr_requests()

        half_h = self.geo["line_height"] // 2
        for i, cy in enumerate(y_centers):
            y1, y2 = max(0, cy - half_h), min(h_orig, cy + half_h)
            x1, x2 = max(0, self.geo["chat_left"]), min(w_orig, self.geo["chat_right"])

            if x2 == w_orig:
                logger.warning("WARNING: chat_right hits frame boundary — some text may be cut off")

            if y1 >= y2 or x1 >= x2: continue

            raw_crop = img[y1:y2, x1:x2]
            if raw_crop.size == 0: continue
            
            if i < 6:
                if not os.path.exists("debug"): os.makedirs("debug")
                cv2.imwrite(f"debug/slice_{i}_raw.png", raw_crop)

            # Upscale 2x for speed
            hc, wc = raw_crop.shape[:2]
            upscaled = cv2.resize(raw_crop, (wc*2, hc*2), interpolation=cv2.INTER_LANCZOS4)
            cv2.imwrite(f"debug/step2_slice_{i}_upscaled.png", upscaled)
            
            res_text, lang, translation = "", "??", ""
            try:
                if self.anthropic_service:
                    # Use Unified Vision Service
                    _, buf = cv2.imencode('.png', upscaled)
                    b64 = base64.b64encode(buf).decode('utf-8')
                    
                    print(f"Calling Claude Vision for line {i}...")
                    vision_res = self.anthropic_service.vision_ocr_translation(b64)
                    
                    if vision_res:
                        res_text = vision_res["raw_text"]
                        lang = vision_res["lang"]
                        translation = vision_res["translation"]
                        print(f"Claude ({vision_res['model_used']}) Response: {res_text}")
                else:
                    print("WARNING: anthropic_service is None, skipping recognition.")
            except Exception as e:
                logger.error(f"Claude Vision failed: {e}")
            
            print(f"DIAGNOSTIC: RAW OCR Line {i}: '{res_text}' [{lang}]")
            
            if res_text and res_text.strip() in self.seen_messages:
                print(f"Early exit: '{res_text}' already seen.")
                break
            if res_text and len(res_text.strip()) > 1:
                self.seen_messages.add(res_text.strip())
            
            raw_ocr_results.append({
                "raw_text": res_text, 
                "lang": lang, 
                "translation": translation
            })

        # Structure Parsing
        struct_results = []
        pattern = self.chat_format.get("parser_regex")
        sys_keywords = self.chat_format.get("system_keywords", [])
        s_grp = self.chat_format.get("sender_group", 1)
        m_grp = self.chat_format.get("message_group", 2)
        
        for res in raw_ocr_results:
            raw = res["raw_text"]
            is_system = any(kw in raw.lower() for kw in sys_keywords)
            
            struct_data = {
                "tag": None, "sender": None, "message": raw.strip(),
                "lang": res["lang"], "translation": res["translation"]
            }
            
            try:
                match = re.search(pattern, raw, re.IGNORECASE)
                if is_system:
                    struct_data["tag"] = "SYSTEM"
                elif match:
                    struct_data["tag"] = self.chat_format.get("tag_label", "Chat")
                    struct_data["sender"] = match.group(s_grp).strip()
                    struct_data["message"] = match.group(m_grp).strip()
            except Exception as e:
                logger.error(f"Structure parsing failed: {e}")
            
            struct_results.append(struct_data)

        # Final Formatting
        final_output = []
        for struct in struct_results:
            msg = struct["message"]
            translation = struct["translation"]
            lang = struct["lang"]
            
            if not msg or len(msg.strip()) < 2: continue
            if not translation: translation = msg

            tag, user = struct["tag"], struct["sender"]
            
            # --- DYNAMIC POST-TRANSLATION CLEANUP ---
            if user:
                translation = re.sub(f"^{re.escape(user)}\\s*[:;\\)]?\\s*", "", translation, flags=re.IGNORECASE).strip()
                if "[" in user:
                    clean_name = user.split("[")[0].strip()
                    translation = re.sub(f"^{re.escape(clean_name)}\\s*[:;\\)]?\\s*", "", translation, flags=re.IGNORECASE).strip()

            if tag:
                translation = re.sub(f"^\\[{re.escape(tag)}\\]\\s*", "", translation, flags=re.IGNORECASE).strip()
            
            translation = re.sub(r"^[\[\(]?(?:Allies|All|Team|Party)[\]\)]?\s*[^:]+[:;]\s*", "", translation, flags=re.IGNORECASE).strip()

            prefix = f"[{tag}] " if tag else ""
            out_line = f"{prefix}{user + ': ' if user else ''}{msg} [{lang}] → \"{translation}\""
            final_output.append({
                "out_line": out_line, 
                "tag": tag,
                "sender": user,
                "message": msg, 
                "translated_message": translation, 
                "lang": lang.lower()
            })

        print("\n--- FINAL OUTPUT ---")
        for obj in final_output: print(obj["out_line"])
        return final_output

if __name__ == "__main__":
    pipeline = SurgicalOcrPipeline()
    pipeline.calibrate((0, 0, 1600, 423))
