import re

class ChatParser:
    def __init__(self, sender_registry=None):
        self.sender_registry = sender_registry if sender_registry is not None else set()

    def register_sender(self, sender):
        if sender and len(sender) > 2:
            self.sender_registry.add(sender.lower())

    def parse_line(self, chat_line):
        """
        Parses a raw OCR line into tag, sender, and message.
        """
        parsed = {
            "tag": None,
            "sender": None,
            "message": chat_line.strip()
        }

        temp_line = chat_line.strip()

        # 1. Tag Detection
        # Matches [Allies], (Allies), [All], [Team], [Squelched], etc.
        tag_pattern = r"^[\[\(]?(Allies|Team|All|Squelch\w*|Party)[\]\)]?\s*(.*)"
        tag_match = re.search(tag_pattern, temp_line, re.IGNORECASE)
        
        if tag_match:
            parsed["tag"] = tag_match.group(1).capitalize()
            temp_line = tag_match.group(2).strip()
        else:
            loose_tag_match = re.search(r"(Allies|All|Team|Party)", temp_line[:15], re.IGNORECASE)
            if loose_tag_match:
                parsed["tag"] = loose_tag_match.group(1).capitalize()
                temp_line = re.sub(r"^[^\w\d]*" + re.escape(loose_tag_match.group(0)) + r"[^\w\d]*", "", temp_line, flags=re.IGNORECASE).strip()

        # 2. Sender Detection
        # Look for delimiters like : ; ! |
        # We also check if the text before the delimiter is a likely name (1-20 chars, mostly alnum)
        sender_match = re.search(r"^([^:;!\|]{1,25})[:;!\|](.*)", temp_line)
        if not sender_match:
            # Fallback for dots or common colon misreads as 'i' or 'l' after a name-like structure
            sender_match = re.search(r"^([^:;]{1,25}[\]\)])[\.\sil](.*)", temp_line)
            
        if not sender_match:
            # Look for a space and a dot (common misread of ' :')
            sender_match = re.search(r"^([^:;]{1,25})\s\.(.*)", temp_line)

        if sender_match:
            potential_sender = sender_match.group(1).strip()
            message_part = sender_match.group(2).strip()

            # Robust validation: Sender should have at least one letter/digit 
            # and shouldn't be too long or just symbols
            if 1 <= len(potential_sender) <= 25 and any(c.isalnum() for c in potential_sender):
                parsed["sender"] = potential_sender
                parsed["message"] = message_part
                self.register_sender(potential_sender)
            else:
                parsed["message"] = temp_line
        else:
            # Check against registry
            words = temp_line.split(" ")
            if words:
                first_word = words[0].rstrip(":;,. ").strip()
                if first_word.lower() in self.sender_registry:
                    parsed["sender"] = first_word
                    parsed["message"] = " ".join(words[1:]).strip()
                elif parsed["tag"] and len(words) > 1:
                    # If we have a tag, the first word is almost certainly a sender
                    potential_sender = words[0].strip()
                    if 1 <= len(potential_sender) <= 20 and any(c.isalnum() for c in potential_sender):
                        parsed["sender"] = potential_sender
                        parsed["message"] = " ".join(words[1:]).strip()
                        self.register_sender(potential_sender)

        # Final cleanup
        parsed["message"] = re.sub(r"^[ :;.,\.]+", "", parsed["message"]).strip()
        
        if len(parsed["message"]) < 2 and not any(c.isalnum() for c in parsed["message"]):
             parsed["message"] = ""

        return parsed
