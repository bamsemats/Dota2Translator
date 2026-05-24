import os
import cv2
import numpy as np
import json
import paddle
import sys
import time
from rapidfuzz import fuzz
from ocr.ocr_service import OcrService

# CRITICAL: Disable PIR API globally for stability on CPU
paddle.set_flags({'FLAGS_enable_pir_api': 0})

class OcrTuningLab:
    def __init__(self):
        # Use the real app's OcrService for 100% parity
        self.ocr_service = OcrService(lang='ru', use_gpu=False)

    def calculate_score(self, ocr_results, expected_lines):
        if not ocr_results or not expected_lines:
            return 0.0

        # Extract text from the dict list returned by OcrService
        ocr_texts = [r['text'] for r in ocr_results]
        
        ocr_all = " ".join(ocr_texts).lower()
        exp_all = " ".join(expected_lines).lower()
        
        line_scores = []
        for exp in expected_lines:
            best_match = 0
            for ocr in ocr_texts:
                score = fuzz.ratio(exp.lower(), ocr.lower())
                best_match = max(best_match, score)
            line_scores.append(best_match)
        
        avg_line_score = sum(line_scores) / len(line_scores)
        holistic_score = fuzz.ratio(ocr_all, exp_all)
        
        return (avg_line_score * 0.8) + (holistic_score * 0.2)

    def run_permutation(self, image_path, expected_lines, params):
        img = cv2.imread(image_path)
        if img is None:
            return 0, []

        h, w = img.shape[:2]
        
        # 1. Scale
        scale = params.get('scale', 1.0)
        target_w = int(w * scale)
        if target_w > 3000:
            scale = 3000 / w
            target_w = 3000
        
        img_resized = cv2.resize(img, (target_w, int(h * scale)), interpolation=cv2.INTER_LANCZOS4)
        
        # 2. Pad
        pad_l = params.get('pad_l', 50)
        pad_t = params.get('pad_t', 30)
        img_padded = cv2.copyMakeBorder(img_resized, pad_t, 0, pad_l, 0, cv2.BORDER_CONSTANT, value=[0, 0, 0])
        
        # 3. Process
        gray = cv2.cvtColor(img_padded, cv2.COLOR_BGR2GRAY)
        clip = params.get('clahe_clip', 2.0)
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
        processed = clahe.apply(gray)
        processed = cv2.bilateralFilter(processed, 9, 75, 75)
        
        # 4. OCR using the REAL service
        results = self.ocr_service.extract_text(processed)
        
        score = self.calculate_score(results, expected_lines)
        return score, results, processed

    def optimize(self, test_case):
        image_path = test_case['image']
        expected = test_case['expected']
        
        print(f"\n[LAB] Optimizing: {image_path}")
        
        best_score = -1
        best_params = {}
        best_img = None
        
        scales = [1.0, 1.5, 2.0]
        clips = [2.0, 3.5]
        paddings = [50]
        
        total_runs = len(scales) * len(clips) * len(paddings)
        current_run = 0
        start_time = time.time()
        
        for s in scales:
            for c in clips:
                for p in paddings:
                    current_run += 1
                    print(f"      [{current_run}/{total_runs}] S:{s} C:{c} P:{p} ...", end='\r')
                    
                    params = {'scale': s, 'clahe_clip': c, 'pad_l': p, 'pad_t': 30}
                    score, output, processed_img = self.run_permutation(image_path, expected, params)
                    
                    if score > best_score:
                        best_score = score
                        best_params = params
                        best_img = processed_img
                        preview = ' '.join([r['text'] for r in output])[:60]
                        print(f"\n  >>> New Best: {score:.2f}% | \"{preview}...\"")

        if best_img is not None:
            cv2.imwrite("best_processed.png", best_img)
        
        print(f"\n[LAB] Completed in {time.time() - start_time:.1f}s")
        return best_params, best_score

if __name__ == "__main__":
    sys.path.append(os.getcwd())
    lab = OcrTuningLab()
    
    with open('tests/test_cases.json', 'r', encoding='utf-8') as f:
        cases = json.load(f)
    
    for case in cases:
        if not os.path.exists(case['image']): continue
        best_p, best_s = lab.optimize(case)
        print(f"\n[RESULT] Winner for {case['image']}: {best_s:.2f}% | Params: {best_p}")
