import cv2
import numpy as np

class AnchorDetector:
    def __init__(self):
        # Dota 2 player colors in HSV
        self.player_colors = [
            ((105, 150, 150), (120, 255, 255)), # Blue
            ((75, 120, 120),  (85, 255, 255)),  # Teal
            ((145, 120, 100), (160, 255, 255)), # Purple
            ((25, 180, 180),  (35, 255, 255)),  # Yellow
            ((10, 180, 150),  (20, 255, 255)),  # Orange
            ((160, 100, 150), (175, 255, 255)), # Pink
            ((30, 120, 120),  (45, 255, 255)),  # Olive
            ((100, 150, 150), (115, 255, 255)), # Light Blue
            ((50, 150, 50),   (70, 255, 255)),  # Dark Green
            ((10, 150, 50),   (25, 255, 150)),  # Brown
        ]

    def find_anchors(self, image_bgr):
        """
        Finds chat line anchors (colons) using structural and color analysis.
        Returns a list of (x, y_center) coordinates.
        """
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        
        # 1. Find potential colon dots (bright spots)
        # Using a very high threshold for the dots
        _, dots_mask = cv2.threshold(v, 200, 255, cv2.THRESH_BINARY)
        
        num, labels, stats, centroids = cv2.connectedComponentsWithStats(dots_mask, connectivity=8)
        dots = []
        for i in range(1, num):
            w, hh, area = stats[i][2], stats[i][3], stats[i][4]
            # Colon dots are small and roughly square
            if 2 <= w <= 15 and 2 <= hh <= 15 and 4 <= area <= 150:
                dots.append({'centroid': centroids[i], 'bbox': stats[i]})
        
        anchors = []
        # 2. Pair dots vertically
        for i in range(len(dots)):
            for j in range(i + 1, len(dots)):
                d1, d2 = dots[i], dots[j]
                dx = abs(d1['centroid'][0] - d2['centroid'][0])
                dy = abs(d1['centroid'][1] - d2['centroid'][1])
                
                # Dota colons are vertically aligned (dx small) and have fixed gap (dy)
                if dx < 10 and 10 < dy < 45:
                    x = int((d1['centroid'][0] + d2['centroid'][0]) / 2)
                    y = int((d1['centroid'][1] + d2['centroid'][1]) / 2)
                    
                    # 3. Color Validation: Check for player color to the left
                    if self._is_player_chat(hsv, x, y):
                        anchors.append((x, y))
        
        # Deduplicate anchors that are too close (same colon detected twice)
        if not anchors:
            return []
            
        final_anchors = []
        anchors.sort(key=lambda a: (a[1], a[0])) # Sort by Y then X
        
        if anchors:
            curr = anchors[0]
            for next_a in anchors[1:]:
                if abs(next_a[1] - curr[1]) < 15 and abs(next_a[0] - curr[0]) < 20:
                    continue # Skip duplicate
                final_anchors.append(curr)
                curr = next_a
            final_anchors.append(curr)
            
        return final_anchors

    def find_all_rows(self, image_bgr):
        """
        Detects all horizontal text bands in the image using a projection profile.
        Returns a list of (y_start, y_end) tuples.
        """
        h, w = image_bgr.shape[:2]
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        
        # 1. Binarize aggressively
        _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        
        # 2. Morphological filtering to remove thin horizontal lines/noise
        # Opening with a vertical kernel removes things that aren't at least X pixels high
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        # 3. Sum pixels horizontally
        horizontal_projection = np.sum(binary, axis=1)
        
        # 4. Identify ranges with high pixel density
        rows = []
        in_row = False
        start_y = 0
        
        # Threshold: Increased to ensure we have substantial text
        min_pixels = (w // 80) * 255 # Approx 1.25% of width
        
        for y, val in enumerate(horizontal_projection):
            if not in_row and val > min_pixels:
                in_row = True
                start_y = y
            elif in_row and val <= min_pixels:
                in_row = False
                # Filter out noise: A real text line is at least 15-20px high at 4K/1080p
                if y - start_y > 15:
                    rows.append((start_y, y))
        
        if in_row:
            if h - start_y > 15:
                rows.append((start_y, h))
            
        return rows

    def _is_player_chat(self, hsv, x, y):
        """
        Validates if a colon is likely part of a player chat message.
        Checks for player colors in the ROI to the left of the colon.
        """
        search_w = 300
        roi_x1 = max(0, x - search_w)
        roi_x2 = max(0, x - 5)
        roi_y1 = max(0, y - 15)
        roi_y2 = min(hsv.shape[0], y + 15)
        
        if roi_x2 <= roi_x1:
            return False
            
        roi_hsv = hsv[roi_y1:roi_y2, roi_x1:roi_x2]
        
        for lower, upper in self.player_colors:
            # Relaxed hue range for various lighting/resolutions
            l = np.array([lower[0]-5, 80, 80])
            u = np.array([upper[0]+5, 255, 255])
            mask = cv2.inRange(roi_hsv, l, u)
            if cv2.countNonZero(mask) > 30: # Minimum color block
                return True
        return False
