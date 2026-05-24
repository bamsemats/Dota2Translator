import mss
import numpy as np
import time
from utils.benchmark import Benchmark

class CaptureService:
    def __init__(self):
        pass

    def capture_single_frame(self, region):
        """
        Captures a single frame as fast as possible.
        """
        x, y, w, h = region
        monitor = {"top": y, "left": x, "width": w, "height": h}
        with mss.mss() as sct:
            screenshot = sct.grab(monitor)
            return np.array(screenshot)[:, :, :3]

    def capture_frames(self, region, num_frames=3, interval_ms=10):
        """
        Captures multiple frames from a predefined region.
        Optimized for speed.
        """
        x, y, w, h = region
        monitor = {"top": y, "left": x, "width": w, "height": h}
        frames = []
        
        with Benchmark(f"Capturing {num_frames} frames"):
            with mss.mss() as sct:
                for i in range(num_frames):
                    screenshot = sct.grab(monitor)
                    # Convert to numpy array (BGRA to BGR)
                    img = np.array(screenshot)[:, :, :3]
                    frames.append(img)
                    if i < num_frames - 1 and interval_ms > 0:
                        time.sleep(interval_ms / 1000.0)
        
        return frames
