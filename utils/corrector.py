import re

class PostProcessor:
    def __init__(self):
        # Common Swedish OCR misreads and merged words
        self.swedish_fixes = {
            r"\bvitestar\b": "vi testar",
            r"\bgangtil\b": "gång till",
            r"\bgang\b": "gång",
            r"\bfor\b": "för", # Caution: 'for' is also English
            r"\bpa\b": "på",
            r"\bar\b": "är",  # Caution: 'ar' is rare in EN but possible in OCR
            r"\bnagra\b": "några",
            r"\bsa\b": "så",
            r"\bman\b": "män", # Context dependent, risky
        }
        
        # Structural fixes (Channel, Tag, etc.) - handled in Parser too but good to have here
        self.structural_fixes = {
            r"[f\[\(]{1,2}(All[ie\s\|1]{1,4}s|All)[\]\)J]{1,2}": "[Allies]",
            r"[f\[\(]{1,2}Party[\]\)J]{1,2}": "[Party]",
            r"[f\[\(]{1,2}DT[\]\)J]{1,2}": "[DT]",
        }

    def clean_text(self, text, is_swedish=False):
        """
        Applies heuristic corrections to OCR text.
        """
        if not text:
            return ""

        # 1. Structural Fixes (Apply always as they are Dota specific)
        for pattern, replacement in self.structural_fixes.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # 2. Swedish Fixes (Only if Swedish is detected or likely)
        if is_swedish:
            # Fix missing diacritics in common words
            text = text.replace("aa", "å") # Common OCR artifact for å
            
            for pattern, replacement in self.swedish_fixes.items():
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # 3. General Cleanup
        # Fix common punctuation artifacts
        text = re.sub(r"\s+([:.!?,])", r"\1", text) # Remove space before punctuation
        text = re.sub(r"([:.!?,])\s+", r"\1 ", text) # Ensure space after punctuation
        
        return text.strip()

    def fix_diacritics_heuristically(self, text):
        """
        Attempts to restore Swedish diacritics based on character patterns if the model failed.
        """
        # Example: 'at' -> 'åt' if context suggests Swedish, but very risky.
        # Better to rely on the Latin model we enabled in OcrService.
        return text
