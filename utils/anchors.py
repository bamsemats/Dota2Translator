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
        Finds chat line anchors by detecting player markers with strict geometric filtering.
        """
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        h, w = image_bgr.shape[:2]
        
        # 1. Gutter Restriction: 
        # Hero icons/Markers ONLY appear in the leftmost "gutter" (approx 8% of width)
        gutter_w = int(w * 0.08)
        roi_hsv = hsv[:, :gutter_w]
        
        candidates = []
        
        for lower, upper in self.player_colors:
            l = np.array([lower[0]-5, 70, 70])
            u = np.array([upper[0]+5, 255, 255])
            mask = cv2.inRange(roi_hsv, l, u)
            
            num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
            
            for i in range(1, num):
                bw, bh, area = stats[i][2], stats[i][3], stats[i][4]
                x_c, y_c = centroids[i]
                
                # 2. Geometric Filtering:
                # Hero icons are roughly square (1:1 ratio)
                # Player bars are thin and vertical.
                aspect_ratio = bw / bh if bh > 0 else 0
                
                # We ignore anything too large (UI backgrounds) or too thin (noise)
                is_marker_shape = (0.2 < aspect_ratio < 1.5) and (area < 800)
                
                if area > 15 and is_marker_shape:
                    candidates.append((int(x_c), int(y_c)))

        if not candidates:
            return []
            
        # 3. Column Consistency Check:
        # Real chat markers will share a very similar X-coordinate.
        # We group candidates by X and pick the most frequent column.
        candidates.sort(key=lambda a: a[0])
        
        columns = []
        if candidates:
            curr_col = [candidates[0]]
            for next_c in candidates[1:]:
                if abs(next_c[0] - curr_col[0][0]) < 15: # Within 15px X-range
                    curr_col.append(next_c)
                else:
                    columns.append(curr_col)
                    curr_col = [next_c]
            columns.append(curr_col)
            
        # Pick the column with the most candidates (likely the chat gutter)
        # or all columns that look "chat-like" (vertical)
        valid_anchors = []
        for col in columns:
            if len(col) >= 1: # Even 1 is okay if it's the only one, but we prioritize the densest
                valid_anchors.extend(col)
                
        # 4. Deduplicate Y-coordinates
        valid_anchors.sort(key=lambda a: a[1])
        final_anchors = []
        if valid_anchors:
            curr = valid_anchors[0]
            for next_a in valid_anchors[1:]:
                if abs(next_a[1] - curr[1]) < 20: # Same line
                    continue 
                final_anchors.append(curr)
                curr = next_a
            final_anchors.append(curr)
            
        return final_anchors

    def find_chat_line_anchors(self, image_bgr):
        """
        Surgically finds chat line Y-centers using the blue username text as an anchor.
        Most robust method for Dota 2 chat box.
        """
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        
        # Blue username text: Hue 100-130, high saturation
        # We use a strict saturation floor to avoid background artifacts
        lower_blue = np.array([100, 150, 100])
        upper_blue = np.array([130, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        
        # Find contours of blue clusters
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        line_centers = []
        for cnt in contours:
            if cv2.contourArea(cnt) > 10: # Filter noise
                m = cv2.moments(cnt)
                if m["m00"] != 0:
                    cy = int(m["m01"] / m["m00"])
                    line_centers.append(cy)

        if not line_centers:
            return []

        # Cluster Y-centers that are close together (same line)
        line_centers.sort()
        unique_centers = []
        curr_cluster = [line_centers[0]]
        
        # Typical line height at 1080p is ~20px, at 4K ~40px. 
        # A 30px grouping threshold is a safe middle ground.
        group_thresh = 30 
        
        for cy in line_centers[1:]:
            if cy - curr_cluster[-1] < group_thresh:
                curr_cluster.append(cy)
            else:
                unique_centers.append(int(np.mean(curr_cluster)))
                curr_cluster = [cy]
        unique_centers.append(int(np.mean(curr_cluster)))
        
        return unique_centers

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
