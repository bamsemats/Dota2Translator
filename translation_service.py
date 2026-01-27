from google.cloud import translate_v3 as translate
from usage_tracker import UsageTracker # Import UsageTracker

TARGET_LANGUAGE = "en" # Always translate to English

class TranslationService:
    def __init__(self, project_id):
        self.project_id = project_id
        self.client = None # Will be initialized after OAuth
        self.usage_tracker = UsageTracker() # Instantiate UsageTracker

    def initialize_client(self, credentials):
        """Initializes the Google Cloud Translation client with provided credentials."""
        self.client = translate.TranslationServiceClient(credentials=credentials)

    def translate_text(self, text, source_language="und"):
        """
        Translates text using Google Cloud Translation API.
        :param text: The text to translate.
        :param source_language: The detected source language code (e.g., 'es', 'fr', 'und' for undetermined).
        :return: Translated text.
        """
        original_text = text # Store original text

        if self.client is None:
            print("Translation client not initialized. Cannot perform translation.")
            return original_text, original_text

        if self.usage_tracker.is_translation_limit_reached():
            print("Warning: Translation free tier limit reached for this month. Further translation requests are blocked.")
            return original_text, original_text
        
        if not text.strip() or source_language.lower() == TARGET_LANGUAGE:
            return original_text, original_text # No need to translate empty text or if already target language

        try:
            parent = f"projects/{self.project_id}/locations/global"
            
            # First, attempt language detection if source_language is undetermined
            if source_language == "und":
                lang_detect_response = self.client.detect_language(
                    parent=parent,
                    content=text,
                    mime_type="text/plain"
                )
                if lang_detect_response.languages:
                    source_language = max(lang_detect_response.languages, key=lambda x: x.confidence).language_code
                else:
                    source_language = "en" # Default to English if detection fails

            # Skip translation if source is already target language
            if source_language.lower() == TARGET_LANGUAGE:
                return original_text, original_text

            # Perform translation
            response = self.client.translate_text(
                request={
                    "parent": parent,
                    "contents": [text],
                    "mime_type": "text/plain",
                    "source_language_code": source_language,
                    "target_language_code": TARGET_LANGUAGE,
                }
            )

            self.usage_tracker.increment_translation_characters(len(text))
            if self.usage_tracker.get_translation_usage_percentage() >= 80:
                print(f"Warning: Translation usage is at {self.usage_tracker.get_translation_usage_percentage():.0f}% of the free tier limit ({self.usage_tracker.get_translation_characters()}/{self.usage_tracker.get_translation_free_tier_limit()} characters).")


            if response.translations:
                translated_text = response.translations[0].translated_text
                return original_text, translated_text
            
        except Exception as e:
            print(f"Error during translation: {e}")
        
        return original_text, original_text # Return original text on error
