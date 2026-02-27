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
            ((100, 150, 50), (130, 255, 255)), # Blue
            ((80, 150, 50), (100, 255, 255)),  # Teal
            ((130, 150, 50), (160, 255, 255)), # Purple
            ((22, 150, 50), (40, 255, 255)),   # Yellow
            ((5, 150, 50), (22, 255, 255)),    # Orange
            ((140, 150, 50), (175, 255, 255)), # Pink
            ((35, 150, 50), (60, 255, 255)),   # Olive/Lime
            ((85, 150, 50), (115, 255, 255)),  # Light Blue
            ((55, 100, 40), (85, 255, 255)),   # Dark Green
            ((0, 150, 40), (15, 255, 255)),    # Brown
        ]

    def get_color_mask(self, hsv):
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for (lower, upper) in self.dota_player_colors:
            low = np.array([lower[0], 150, lower[2]]) # S > 150
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv, low, np.array(upper)))
        return mask

    def get_white_mask(self, hsv):
        h, s, v = cv2.split(hsv)
        _, v_mask = cv2.threshold(v, 185, 255, cv2.THRESH_BINARY)
        _, s_mask = cv2.threshold(s, 65, 255, cv2.THRESH_BINARY_INV)
        return cv2.bitwise_and(v_mask, s_mask)

    def denoise_ui_elements(self, combined_mask, shadow_mask):
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(combined_mask, connectivity=8)
        kernel_shadow = np.ones((5, 5), np.uint8)
        shadow_field = cv2.dilate(shadow_mask, kernel_shadow, iterations=1)
        
        candidates = []
        for i in range(1, num_labels):
            x, y, w, h, area = stats[i]
            if not (4 < h < 85 and area > 2): continue # Inclusive geometry
            
            # Shadow Check
            blob_roi = (labels[y:y+h, x:x+w] == i).astype(np.uint8) * 255
            if cv2.countNonZero(cv2.bitwise_and(blob_roi, shadow_field[y:y+h, x:x+w])) > 0:
                candidates.append(i)

        anchors = set()
        for i in candidates:
            x1, y1, w1, h1, _ = stats[i]
            y1_bottom = y1 + h1
            
            # Anchor: Requires a minimum height/area. No solidity filter.
            if h1 > 10 and stats[i, cv2.CC_STAT_AREA] > 8: # Relaxed Anchor Rules
                # Explicitly add brackets as anchors if they fit geometric profile
                if 2 < w1 < 10 and h1 > 20: # Tall and thin (like [ or ])
                    anchors.add(i)
                    continue

                for j in candidates:
                    if i == j: continue
                    y2_bottom = stats[j, cv2.CC_STAT_TOP] + stats[j, cv2.CC_STAT_HEIGHT]
                    if abs(y1_bottom - y2_bottom) < 10: 
                        if min(abs(x1 - (stats[j,0]+stats[j,2])), abs(stats[j,0] - (x1+w1))) < 150: 
                            anchors.add(i)
                            break

        clean_mask = np.zeros_like(combined_mask)
        for i in candidates:
            if i in anchors:
                clean_mask[labels == i] = 255
                continue
            x1, y1, w1, h1, _ = stats[i]
            for a_idx in anchors:
                ax, ay, aw, ah, _ = stats[a_idx]
                if abs(y1 - ay) < 40: 
                    if min(abs(x1 - (ax + aw)), abs(ax - (x1 + w1))) < 20:
                        clean_mask[labels == i] = 255
                        break
                        
        return clean_mask

    def preprocess_image(self, pil_image):
        width, height = pil_image.size
        img = pil_image.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2HSV)

    def extract_text_from_image(self, pil_image):
        pil_image.save("ocr_debug_original.png")
        try:
            hsv = self.preprocess_image(pil_image)
            v_chan = hsv[:,:,2]
            _, shadow_mask = cv2.threshold(v_chan, 60, 255, cv2.THRESH_BINARY_INV)
            
            white_mask = self.get_white_mask(hsv)
            color_mask_for_validation = self.get_color_mask(hsv) 
            
            # Combined mask for denoising includes white and player colors
            combined = cv2.bitwise_or(white_mask, color_mask_for_validation)
            
            validated_combined = self.denoise_ui_elements(combined, shadow_mask)
            
            # Use the full validated mask for the main pass
            final_msg_mask = validated_combined 
            
            proc_mask = cv2.dilate(final_msg_mask, np.ones((2, 2), np.uint8), iterations=1)
            final_mask = cv2.bitwise_not(proc_mask)
            cv2.imwrite("ocr_debug_final_mask.png", final_mask)

            data = pytesseract.image_to_data(final_mask, lang='eng+rus+spa+por+chi_sim', config='--oem 1 --psm 6', output_type=Output.DICT)

            temp_lines = defaultdict(list)
            for i in range(len(data['text'])):
                conf = int(data['conf'][i])
                text = data['text'][i].strip()
                # Use a slightly higher confidence for the main pass to reduce hallucinations
                if conf > 20 and text:
                    y_center = data['top'][i] + (data['height'][i] // 2)
                    matched_y = None
                    for ly_center in temp_lines.keys():
                        if abs(ly_center - y_center) < 25: # Group by vertical center proximity
                            matched_y = ly_center
                            break
                    if matched_y is None:
                        temp_lines[y_center].append(i)
                    else:
                        temp_lines[matched_y].append(i)

            results = []
            for y_center in sorted(temp_lines.keys()):
                indices = temp_lines[y_center]
                indices.sort(key=lambda idx: data['left'][idx])
                line_text = " ".join([data['text'][idx] for idx in indices])
                
                y_min = min(data['top'][idx] for idx in indices)
                y_max = max(data['top'][idx] + data['height'][idx] for idx in indices)
                
                # Filter noise: Must have a decent density of alphanumeric characters
                alnum_count = sum(1 for c in line_text if c.isalnum())
                if alnum_count < 2: continue # Ignore lines with < 2 alnum chars
                if len(line_text) < 4 and alnum_count < 3: continue # Ignore very short non-dense lines

                # Deduplication: If this line heavily overlaps the previous one, skip it
                if results:
                    prev_min, prev_max = results[-1]["y_bounds"]
                    overlap = min(y_max, prev_max) - max(y_min, prev_min)
                    line_height = y_max - y_min
                    if overlap > line_height * 0.5:
                        # If overlap is high, keep the one with more text
                        if len(line_text) > len(results[-1]["text"]):
                            results.pop()
                        else:
                            continue

                if line_text:
                    cleaned = line_text.strip()
                    cleaned = re.sub(r'[\s]+', ' ', cleaned).strip()
                    
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


    def extract_sender_from_line(self, hsv, y_bounds):
        y1, y2 = y_bounds
        y1_v, y2_v = max(0, y1-10), min(hsv.shape[0], y2+10)
        x_limit = int(hsv.shape[1] * 0.45)
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
            if 8 < h < 120 and area > 4: # Adjusted for 3x scale
                blob_roi = (labels[y:y+h, x:x+w]==i).astype(np.uint8)*255
                if cv2.countNonZero(cv2.bitwise_and(blob_roi, s_field[y:y+h, x:x+w])) > 0:
                    valid_c[labels==i] = 255
                    ex_x.extend([x, x+w])

        if not ex_x: return None
        name_strip = cv2.copyMakeBorder(cv2.bitwise_not(cv2.dilate(valid_c[:, max(0, min(ex_x)-20):min(valid_c.shape[1], max(ex_x)+20)], np.ones((2,2), np.uint8))), 20, 20, 40, 40, cv2.BORDER_CONSTANT, value=[255,255,255])
        cv2.imwrite("ocr_debug_sender_pass.png", name_strip)
        
        name = pytesseract.image_to_string(name_strip, lang='eng+rus+spa+por+chi_sim+tur', config='--oem 1 --psm 6').strip()
        name = re.sub(r'[^\w\d\s\._\-\[\]#]', '', name).strip()
        return name if len(name) >= 2 else None
