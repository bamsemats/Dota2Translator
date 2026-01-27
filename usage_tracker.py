import json
import os
from datetime import datetime, timedelta

USAGE_FILE = "usage_data.json"
FREE_TIER_OCR_LIMIT = 1000  # Example: 1000 requests per month
FREE_TIER_TRANSLATION_LIMIT = 500000  # Example: 500,000 characters per month

class UsageTracker:
    def __init__(self):
        self.usage_path = os.path.join(os.path.dirname(__file__), USAGE_FILE)
        self.data = self._load_usage_data()
        self._reset_if_new_month()

    def _load_usage_data(self):
        if os.path.exists(self.usage_path):
            with open(self.usage_path, 'r') as f:
                return json.load(f)
        return {
            "last_reset_month": datetime.now().strftime("%Y-%m"),
            "ocr_requests": 0,
            "translation_characters": 0
        }

    def _save_usage_data(self):
        with open(self.usage_path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def _reset_if_new_month(self):
        current_month = datetime.now().strftime("%Y-%m")
        if self.data["last_reset_month"] != current_month:
            self.data["last_reset_month"] = current_month
            self.data["ocr_requests"] = 0
            self.data["translation_characters"] = 0
            self._save_usage_data()

    def increment_ocr_requests(self, count=1):
        self.data["ocr_requests"] += count
        self._save_usage_data()

    def increment_translation_characters(self, count):
        self.data["translation_characters"] += count
        self._save_usage_data()

    def get_ocr_requests(self):
        return self.data["ocr_requests"]

    def get_translation_characters(self):
        return self.data["translation_characters"]

    def is_ocr_limit_reached(self):
        return self.get_ocr_requests() >= FREE_TIER_OCR_LIMIT

    def is_translation_limit_reached(self):
        return self.get_translation_characters() >= FREE_TIER_TRANSLATION_LIMIT

    def get_ocr_usage_percentage(self):
        return (self.get_ocr_requests() / FREE_TIER_OCR_LIMIT) * 100

    def get_translation_usage_percentage(self):
        return (self.get_translation_characters() / FREE_TIER_TRANSLATION_LIMIT) * 100

    def get_ocr_free_tier_limit(self):
        return FREE_TIER_OCR_LIMIT

    def get_translation_free_tier_limit(self):
        return FREE_TIER_TRANSLATION_LIMIT

