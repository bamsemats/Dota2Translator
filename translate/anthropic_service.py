import anthropic
import json
import logging
import re
import base64
from usage_tracker import UsageTracker

logger = logging.getLogger(__name__)

class AnthropicTranslationService:
    def __init__(self, api_key, target_lang="en"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.target_lang = target_lang
        self.usage_tracker = UsageTracker()
        self.cache = {}
        self.max_cache_size = 500
        
        # Progressive model list: try latest sonnet, then haiku aliases, then specific versions
        self.models = [
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest"
        ]

    def vision_ocr_translation(self, image_b64):
        """
        Unified Vision OCR + Translation in a single pass.
        """
        for model in self.models:
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=400,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                            {"type": "text", "text": "Transcribe all text in this image exactly, then on a new line output only a JSON object: {\"lang\": \"<ISO code>\", \"translation\": \"<English translation>\"}. If already English, use the original as translation. Preserve all special characters, diacritics (å, ä, ö, etc.), Cyrillic, Chinese, and other scripts exactly in transcription. Output ONLY the text then the JSON, no other chatter."}
                        ]
                    }]
                )
                
                full_text = response.content[0].text.strip()
                
                # Parse: split on last newline or look for JSON
                res_text = ""
                lang = "??"
                translation = ""
                
                # Extract JSON object using regex
                json_match = re.search(r"(\{.*\})", full_text, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        lang = data.get("lang", "??").upper()
                        translation = data.get("translation", "")
                        # Remove the JSON part to get the pure transcription
                        res_text = full_text[:json_match.start()].strip()
                    except:
                        res_text = full_text
                else:
                    res_text = full_text

                return {
                    "raw_text": res_text,
                    "lang": lang,
                    "translation": translation,
                    "model_used": model
                }

            except anthropic.NotFoundError as e:
                logger.warning(f"Model {model} not found (404). Details: {e}")
                continue
            except Exception as e:
                if "404" in str(e):
                    logger.warning(f"Model {model} returned 404 error. Details: {e}")
                    continue
                logger.error(f"Claude Vision Error ({model}): {e}")
                break
        
        return None

    def translate_message(self, text, hint_lang=None):
        if not text or len(text.strip()) < 2:
            return None

        text = text.strip()
        if text in self.cache:
            return self.cache[text]

        for model in self.models:
            try:
                message = self.client.messages.create(
                    model=model,
                    max_tokens=1000,
                    system=(
                        "You are a translation assistant. Given a short chat message, "
                        "respond with only a JSON object: {\"lang\": \"<ISO-639-1 code>\", "
                        "\"translation\": \"<English translation>\"}. If the message is "
                        "already in English, still return the JSON with lang and the "
                        "original text as translation."
                    ),
                    messages=[
                        {"role": "user", "content": f"Message: '{text}'\nHint Language: {hint_lang if hint_lang else 'unknown'}"}
                    ]
                )
                
                response_text = message.content[0].text.strip()
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                    
                    if len(self.cache) >= self.max_cache_size:
                        first_key = next(iter(self.cache))
                        del self.cache[first_key]
                    self.cache[text] = result
                    
                    return result
            except anthropic.NotFoundError:
                continue
            except Exception as e:
                logger.error(f"Anthropic Translation Error: {e}")
                break
        
        return None
