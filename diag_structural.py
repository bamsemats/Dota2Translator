import cv2
import numpy as np
from PIL import Image
import pytesseract
import os

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def structural_diag(path):
    img = Image.open(path)
    img_np = np.array(img.resize((img.width*3, img.height*3), Image.Resampling.LANCZOS))
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    
    # Permissive white mask
    h, s, v = cv2.split(hsv)
    _, v_mask = cv2.threshold(v, 180, 255, cv2.THRESH_BINARY)
    _, s_mask = cv2.threshold(s, 60, 255, cv2.THRESH_BINARY_INV)
    white_mask = cv2.bitwise_and(v_mask, s_mask)
    
    num, labels, stats, centroids = cv2.connectedComponentsWithStats(white_mask, connectivity=8)
    dots = []
    for i in range(1, num):
        x, y, w, h, area = stats[i]
        if 3 <= w <= 16 and 3 <= h <= 16 and 5 <= area <= 150:
            dots.append({'centroid': centroids[i], 'bbox': (x, y, w, h)})
    
    colons = []
    for i in range(len(dots)):
        for j in range(i + 1, len(dots)):
            d1, d2 = dots[i], dots[j]
            dx = abs(d1['centroid'][0] - d2['centroid'][0])
            dy = abs(d1['centroid'][1] - d2['centroid'][1])
            if dx < 10 and 8 < dy < 50:
                colons.append({
                    'x': min(d1['bbox'][0], d2['bbox'][0]),
                    'y_min': min(d1['bbox'][1], d2['bbox'][1]),
                    'y_max': max(d1['bbox'][1] + d1['bbox'][3], d2['bbox'][1] + d2['bbox'][3])
                })
    
    print(f"Found {len(colons)} potential colons.")
    
    color_names = ["Blue", "Teal", "Purple", "Yellow", "Orange", "Pink", "Olive", "Light Blue", "Dark Green", "Brown"]
    dota_player_colors = [
        ((110, 180, 180), (115, 255, 255)), # 1: Blue
        ((78, 140, 140),  (82, 255, 255)),   # 2: Teal
        ((148, 140, 100), (155, 255, 255)), # 3: Purple
        ((29, 200, 200),  (31, 255, 255)),  # 4: Yellow
        ((12, 200, 150),  (15, 255, 255)),  # 5: Orange
        ((163, 120, 150), (168, 255, 255)), # 6: Pink
        ((34, 150, 150),  (38, 255, 255)),  # 7: Olive
        ((108, 180, 180), (112, 255, 255)), # 8: Light Blue
        ((58, 180, 50),   (65, 255, 255)),  # 9: Dark Green
        ((13, 180, 50),   (18, 255, 150)),  # 10: Brown
    ]
    
    for idx, c in enumerate(colons):
        x, y1, y2 = c['x'], c['y_min'], c['y_max']
        search_width = 400
        roi_hsv = hsv[int(y1-5):int(y2+5), max(0, int(x-search_width)):int(x-5)]
        
        print(f"Colon {idx} at ({x}, {y1}-{y2}):")
        
        # Dominant color check
        for i, (lower, upper) in enumerate(dota_player_colors):
            l = np.array([lower[0]-3, 100, 100])
            u = np.array([upper[0]+3, 255, 255])
            mask = cv2.inRange(roi_hsv, l, u)
            count = cv2.countNonZero(mask)
            if count > 50:
                print(f"  - Detected Color {color_names[i]}: {count} px")
        
        # Tag check
        tag_roi = white_mask[int(y1-5):int(y2+5), max(0, int(x-search_width)):int(x-5)]
        tag_text = pytesseract.image_to_string(cv2.bitwise_not(tag_roi), config='--psm 7').strip()
        print(f"  - Tag ROI text: '{tag_text}'")

if __name__ == "__main__":
    structural_diag("ocr_debug_original.png")
