from google.cloud import translate_v3 as translate
from usage_tracker import UsageTracker 
import re

class TranslationService:
    def __init__(self, project_id, target_lang="en"):
        self.project_id = project_id
        self.target_lang = target_lang
        self.client = None 
        self.usage_tracker = UsageTracker() 
        self.cache = {} # Simple translation cache: { (text, target_lang): translated_text }
        self.max_cache_size = 500

    def initialize_client(self, credentials):
        """Initializes the Google Cloud Translation client with provided credentials."""
        self.client = translate.TranslationServiceClient(credentials=credentials)

    def set_target_lang(self, lang):
        """Updates the target language for translations."""
        if self.target_lang != lang:
            self.target_lang = lang
            # Note: We don't clear the cache, as translations for other target langs might still be valid
            # and our cache key includes the target_lang.

    def _is_worth_translating(self, text):
        """Checks if the text contains enough linguistic content to be worth translating."""
        if not text or len(text.strip()) < 3:
            return False
        
        # Check if it has at least one alphabetic character (any script)
        if not re.search(r'[^\d\s\W_]', text):
            return False
            
        return True

    def translate_text(self, text, target_lang=None, source_language="und"):
        """
        Translates text using Google Cloud Translation API.
        :param text: The text to translate.
        :param target_lang: Override the default target language.
        :param source_language: The detected source language code.
        :return: (detected_lang, translated_text)
        """
        text = text.strip()
        original_text = text 
        
        # Use overridden target_lang if provided, else use default
        target = target_lang if target_lang else self.target_lang

        if not text:
            return "und", original_text

        # Check Cache
        cache_key = (text, target)
        if cache_key in self.cache:
            return self.cache[cache_key]

        if self.client is None:
            return "und", original_text

        if self.usage_tracker.is_translation_limit_reached():
            print("Warning: Translation limit reached. Check usage_data.json.")
            return "und", original_text
        
        # Don't translate if too short or if source is already the target
        if not self._is_worth_translating(text) or (source_language != "und" and source_language.lower() == target.lower()):
            return "und", original_text

        try:
            parent = f"projects/{self.project_id}/locations/global"
            
            # Use translate_text directly. If source_language_code is not provided or is "und",
            # Google will attempt to auto-detect. This saves one API call.
            request_params = {
                "parent": parent,
                "contents": [text],
                "mime_type": "text/plain",
                "target_language_code": target,
            }
            
            # Only provide source language if it's specifically known and NOT "und"
            if source_language and source_language != "und":
                request_params["source_language_code"] = source_language

            response = self.client.translate_text(request=request_params)

            if response.translations:
                translated_text = response.translations[0].translated_text
                detected_lang = response.translations[0].detected_language_code
                
                # If detected language is the same as target, don't treat as translated but return the lang
                if detected_lang == self.target_lang:
                    return detected_lang, original_text

                # Cache the result
                if len(self.cache) >= self.max_cache_size:
                    # Remove first item (primitive LRU)
                    first_key = next(iter(self.cache))
                    del self.cache[first_key]
                
                result = (detected_lang, translated_text)
                self.cache[cache_key] = result
                
                # Increment usage
                self.usage_tracker.increment_translation_characters(len(text))
                if self.usage_tracker.get_translation_usage_percentage() >= 80:
                    print(f"Warning: Translation usage at {self.usage_tracker.get_translation_usage_percentage():.0f}%")

                return result
            
        except Exception as e:
            # Handle 429 specifically if we can, or just log generic error
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print("Translation Quota Exhausted (429).")
            else:
                print(f"Error during translation: {e}")
        
        return "und", original_text
