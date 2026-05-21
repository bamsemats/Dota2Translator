from rapidfuzz import fuzz, process
import hashlib

class Deduplicator:
    def __init__(self, threshold=85, max_history=100):
        self.threshold = threshold
        self.max_history = max_history
        self.history = [] # List of previously seen lines

    def is_new(self, text):
        """
        Checks if the text is new compared to the history using fuzzy matching.
        """
        if not text:
            return False

        clean_text = text.strip()
        if not clean_text:
            return False

        # Exact match check first
        if clean_text in self.history:
            return False

        # Fuzzy match check
        if self.history:
            # Switch to fuzz.ratio (Levenshtein) instead of token_sort_ratio
            # tokens_sort_ratio is too aggressive for chat as it ignores word order and punctuation
            match = process.extractOne(clean_text, self.history, scorer=fuzz.ratio)
            if match and match[1] >= self.threshold:
                return False

        # If it's new, add to history
        self.history.append(clean_text)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        return True

    def clear(self):
        self.history = []
