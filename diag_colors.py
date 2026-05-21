import cv2
import numpy as np
from PIL import Image
import os

def analyze_image(path):
    if not os.path.exists(path):
        return
    img = Image.open(path)
    # 3x scale as in the app
    img_np = np.array(img.resize((img.width*3, img.height*3), Image.Resampling.LANCZOS))
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    
    # Yellow target: Hue 30 (Dota Yellow)
    # Light Blue target: Hue 105 (Dota Light Blue)
    
    color_names = ["Blue", "Teal", "Purple", "Yellow", "Orange", "Pink", "Olive", "Light Blue", "Dark Green", "Brown"]
    dota_player_colors = [
        ((110, 150, 150), (130, 255, 255)), # 1: Blue
        ((85, 150, 150),  (95, 255, 255)),  # 2: Teal
        ((140, 150, 100), (160, 255, 255)), # 3: Purple
        ((28, 150, 150),  (32, 255, 255)),  # 4: Yellow
        ((10, 150, 150),  (18, 255, 255)),  # 5: Orange
        ((160, 100, 150), (175, 255, 255)), # 6: Pink
        ((35, 80, 100),   (55, 255, 255)),  # 7: Olive
        ((100, 150, 150), (110, 255, 255)), # 8: Light Blue
        ((55, 150, 50),   (75, 255, 255)),  # 9: Dark Green
        ((5, 100, 50),    (15, 255, 150)),  # 10: Brown
    ]
    
    print("--- Dominant Colors Analysis ---")
    for i, (lower, upper) in enumerate(dota_player_colors):
        # Use a much wider hue range and lower saturation for discovery
        l = np.array([lower[0]-10, 50, 50])
        u = np.array([upper[0]+10, 255, 255])
        mask = cv2.inRange(hsv, l, u)
        count = cv2.countNonZero(mask)
        if count > 0:
            print(f"Color {color_names[i]}: {count} pixels found.")
            # Find the largest component of this color
            num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
            for j in range(1, num):
                if stats[j, cv2.CC_STAT_AREA] > 50:
                    x, y, w, h = stats[j, :4]
                    # Sample the actual HSV values in this blob
                    roi = hsv[y:y+h, x:x+w]
                    # Mask ROI to only the component
                    blob_mask = (labels[y:y+h, x:x+w] == j).astype(np.uint8)
                    mean_hsv = cv2.mean(roi, mask=blob_mask)
                    print(f"  - Component at ({x}, {y}) Area: {stats[j,4]} | Mean HSV: {mean_hsv[:3]}")

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "ocr_debug_original.png"
    analyze_image(target)
