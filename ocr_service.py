import numpy as np
import cv2
import pytesseract
from pytesseract import Output
from PIL import Image
import re
from collections import defaultdict

# NOTE: You must have Tesseract installed on your system for this to work.
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OcrService:
    def __init__(self):
        # Precise HSV ranges for the 10 Dota 2 player colors
        self.dota_player_colors = [
            ((100, 120, 50), (130, 255, 255)), # Blue
            ((80, 120, 50), (105, 255, 255)),  # Teal
            ((130, 120, 50), (160, 255, 255)), # Purple
            ((22, 120, 50), (40, 255, 255)),   # Yellow
            ((5, 120, 50), (22, 255, 255)),    # Orange
            ((140, 100, 50), (175, 255, 255)), # Pink
            ((35, 100, 50), (65, 255, 255)),   # Olive/Lime
            ((85, 100, 50), (115, 255, 255)),  # Light Blue
            ((55, 80, 40), (85, 255, 255)),    # Dark Green
            ((0, 100, 40), (15, 255, 255)),    # Brown
        ]

    def get_color_mask(self, hsv):
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for (lower, upper) in self.dota_player_colors:
            # Enforce saturation for name pass
            low = np.array([lower[0], 120, lower[2]])
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv, low, np.array(upper)))
        return mask

    def get_white_mask(self, hsv):
        h, s, v = cv2.split(hsv)
        _, v_mask = cv2.threshold(v, 185, 255, cv2.THRESH_BINARY)
        _, s_mask = cv2.threshold(s, 65, 255, cv2.THRESH_BINARY_INV)
        return cv2.bitwise_and(v_mask, s_mask)

    def denoise_ui_elements(self, combined_mask, shadow_mask):
        """
        Validates all UI elements (Tag, Name, Msg) together.
        Ensures neighbors exist across color boundaries.
        """
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(combined_mask, connectivity=8)
        shadow_field = cv2.dilate(shadow_mask, np.ones((5, 5), np.uint8), iterations=1)
        
        candidates = []
        for i in range(1, num_labels):
            x, y, w, h, area = stats[i]
            if not (4 < h < 85 and area > 2): continue
            
            # Shadow Check
            blob_roi = (labels[y:y+h, x:x+w] == i).astype(np.uint8) * 255
            if cv2.countNonZero(cv2.bitwise_and(blob_roi, shadow_field[y:y+h, x:x+w])) > 0:
                candidates.append(i)

        anchors = set()
        for i in candidates:
            x1, y1, w1, h1, _ = stats[i]
            y1_bottom = y1 + h1
            
            # Check for ANY neighbor (color or white) on the same baseline
            for j in candidates:
                if i == j: continue
                y2_bottom = stats[j, cv2.CC_STAT_TOP] + stats[j, cv2.CC_STAT_HEIGHT]
                if abs(y1_bottom - y2_bottom) < 8: # Baseline tolerance
                    x2 = stats[j, cv2.CC_STAT_LEFT]
                    w2 = stats[j, cv2.CC_STAT_WIDTH]
                    if min(abs(x1 - (x2 + w2)), abs(x2 - (x1 + w1))) < 120: 
                        anchors.add(i)
                        break

        clean_mask = np.zeros_like(combined_mask)
        for i in candidates:
            if i in anchors:
                clean_mask[labels == i] = 255
            else:
                # Keep if very close to an anchor (handles dots/commas)
                x1, y1, w1, h1, _ = stats[i]
                for a_idx in anchors:
                    ax, ay, aw, ah, _ = stats[a_idx]
                    if abs(y1 - ay) < 40 and min(abs(x1 - (ax + aw)), abs(ax - (x1 + w1))) < 15:
                        clean_mask[labels == i] = 255
                        break
        return clean_mask

    def extract_text_from_image(self, pil_image):
        pil_image.save("ocr_debug_original.png")
        try:
            hsv = self.preprocess_image(pil_image)
            v_chan = hsv[:,:,2]
            _, shadow_mask = cv2.threshold(v_chan, 60, 255, cv2.THRESH_BINARY_INV)
            
            white_mask = self.get_white_mask(hsv)
            color_mask = self.get_color_mask(hsv)
            combined = cv2.bitwise_or(white_mask, color_mask)
            
            # Denoise all elements together to preserve first/last words
            validated_combined = self.denoise_ui_elements(combined, shadow_mask)
            
            # But for the Message pass, we only want the WHITE pixels
            final_white_mask = cv2.bitwise_and(validated_combined, white_mask)
            
            kernel = np.ones((2, 2), np.uint8)
            proc_mask = cv2.dilate(final_white_mask, kernel, iterations=1)
            final_mask = cv2.bitwise_not(proc_mask)
            cv2.imwrite("ocr_debug_final_mask.png", final_mask)

            data = pytesseract.image_to_data(final_mask, lang='eng+rus+spa+por+chi_sim', config='--psm 6', output_type=Output.DICT)

            # Group by BASELINE (Bottom Y)
            lines = defaultdict(list)
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 20:
                    text = data['text'][i].strip()
                    if text:
                        # Use bottom coordinate for grouping
                        y_bottom = data['top'][i] + data['height'][i]
                        matched_y = None
                        for ly in lines.keys():
                            if abs(ly - y_bottom) < 15: # 15px baseline tolerance
                                matched_y = ly
                                break
                        if matched_y is None:
                            lines[y_bottom].append(i)
                        else:
                            lines[matched_y].append(i)

            results = []
            for y in sorted(lines.keys()):
                indices = lines[y]
                indices.sort(key=lambda idx: data['left'][idx])
                line_text = " ".join([data['text'][idx] for idx in indices])
                y_min = min(data['top'][idx] for idx in indices)
                y_max = max(data['top'][idx] + data['height'][idx] for idx in indices)
                
                if line_text and any(c.isalnum() for c in line_text):
                    cleaned = re.sub(r'[§|\\_~`©®°¶†‡»«#@]', '', line_text).strip()
                    if len(cleaned) >= 2:
                        results.append({
                            "text": cleaned,
                            "y_bounds": (y_min, y_max),
                            "full_hsv": hsv
                        })
            return results
        except Exception as e:
            print(f"Error: {e}")
            return []

    def preprocess_image(self, pil_image):
        width, height = pil_image.size
        img = pil_image.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2HSV)

    def extract_sender_from_line(self, hsv, y_bounds):
        y1, y2 = y_bounds
        y1_v, y2_v = max(0, y1-10), min(hsv.shape[0], y2+10)
        x_limit = int(hsv.shape[1] * 0.4)
        line_hsv = hsv[y1_v:y2_v, 0:x_limit]
        
        c_mask = self.get_color_mask(line_hsv)
        v_chan = line_hsv[:,:,2]
        _, s_mask = cv2.threshold(v_chan, 60, 255, cv2.THRESH_BINARY_INV)
        s_field = cv2.dilate(s_mask, np.ones((7,7), np.uint8), iterations=1)
        
        num, labels, stats, _ = cv2.connectedComponentsWithStats(c_mask, connectivity=8)
        valid_c = np.zeros_like(c_mask)
        ex_x = []
        for i in range(1, num):
            x, y, w, h, area = stats[i]
            if 8 < h < 80 and area > 4:
                if cv2.countNonZero(cv2.bitwise_and((labels[y:y+h, x:x+w]==i).astype(np.uint8)*255, s_field[y:y+h, x:x+w])) > 0:
                    valid_c[labels==i] = 255
                    ex_x.extend([x, x+w])

        if not ex_x: return None
        name_strip = cv2.copyMakeBorder(cv2.bitwise_not(cv2.dilate(valid_c[:, max(0, min(ex_x)-20):min(valid_c.shape[1], max(ex_x)+20)], np.ones((2,2), np.uint8))), 15, 15, 30, 30, cv2.BORDER_CONSTANT, value=[255,255,255])
        cv2.imwrite("ocr_debug_sender_pass.png", name_strip)
        name = pytesseract.image_to_string(name_strip, lang='eng+rus+spa+por+chi_sim', config='--psm 7').strip()
        return re.sub(r'[^\w\d\s\._\-\[\]#]', '', name).strip() if len(name) >= 2 else None
