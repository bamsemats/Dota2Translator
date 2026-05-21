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
        self._reset_if_needed()

    def _load_usage_data(self):
        if os.path.exists(self.usage_path):
            try:
                with open(self.usage_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "last_reset_month": datetime.now().strftime("%Y-%m"),
            "last_reset_day": datetime.now().strftime("%Y-%m-%d"),
            "ocr_requests": 0,
            "translation_characters": 0,
            "daily_translation_characters": 0
        }

    def _save_usage_data(self):
        with open(self.usage_path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def _reset_if_needed(self):
        current_month = datetime.now().strftime("%Y-%m")
        current_day = datetime.now().strftime("%Y-%m-%d")
        modified = False

        if self.data.get("last_reset_month") != current_month:
            self.data["last_reset_month"] = current_month
            self.data["ocr_requests"] = 0
            self.data["translation_characters"] = 0
            modified = True
        
        if self.data.get("last_reset_day") != current_day:
            self.data["last_reset_day"] = current_day
            self.data["daily_translation_characters"] = 0
            modified = True

        if modified:
            self._save_usage_data()

    def increment_ocr_requests(self, count=1):
        self.data["ocr_requests"] += count
        self._save_usage_data()

    def increment_translation_characters(self, count):
        self.data["translation_characters"] = self.data.get("translation_characters", 0) + count
        self.data["daily_translation_characters"] = self.data.get("daily_translation_characters", 0) + count
        self._save_usage_data()

    def get_ocr_requests(self):
        return self.data.get("ocr_requests", 0)

    def get_translation_characters(self):
        return self.data.get("translation_characters", 0)

    def get_daily_translation_characters(self):
        return self.data.get("daily_translation_characters", 0)

    def is_ocr_limit_reached(self):
        return self.get_ocr_requests() >= FREE_TIER_OCR_LIMIT

    def is_translation_limit_reached(self):
        # We don't have a hard daily limit here, but we could set one if we knew it.
        # Google's default daily limit is often 1,000,000 characters, which is more than the free tier monthly.
        # However, the user might have set a lower limit.
        return self.get_translation_characters() >= FREE_TIER_TRANSLATION_LIMIT

    def get_ocr_usage_percentage(self):
        return (self.get_ocr_requests() / FREE_TIER_OCR_LIMIT) * 100

    def get_translation_usage_percentage(self):
        return (self.get_translation_characters() / FREE_TIER_TRANSLATION_LIMIT) * 100

    def get_ocr_free_tier_limit(self):
        return FREE_TIER_OCR_LIMIT

    def get_translation_free_tier_limit(self):
        return FREE_TIER_TRANSLATION_LIMIT

