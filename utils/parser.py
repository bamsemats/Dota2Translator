import re

class ChatParser:
    def __init__(self, sender_registry=None):
        self.sender_registry = sender_registry if sender_registry is not None else set()

    def register_sender(self, sender):
        if sender and len(sender) > 2:
            self.sender_registry.add(sender.lower())

    def parse_line(self, chat_line):
        """
        Dota 2 Structural Parser:
        Expected format: [Channel] #w Sender [Tag] : Message
        Example: [Allies] #w bamsemats [DT] : help me
        """
        parsed = {
            "channel": None,
            "sender": None,
            "tag": None,
            "message": chat_line.strip(),
            "is_structured": False
        }
        
        # 1. Pre-processing: Correct common OCR bracket/keyword misreads
        line = chat_line.strip()
        
        # Issue 3: missing leading bracket on [Allies] etc.
        # if a line starts with Allies] or llies], prepend [
        if re.match(r"^(?:Allies|llies|Party|arty|Team|eam|All)\]", line, re.IGNORECASE):
            line = "[" + line

        # Fix [Allies] / [All]
        line = re.sub(r"[f\[\(]{1,2}(All[ie\s\|1]{1,4}s|All)[\]\)J]{1,2}", "[Allies]", line, flags=re.IGNORECASE)
        # Fix [Party]
        line = re.sub(r"[f\[\(]{1,2}Party[\]\)J]{1,2}", "[Party]", line, flags=re.IGNORECASE)
        # Fix [DT] tag
        line = re.sub(r"[f\[\(]{1,2}DT[\]\)J]{1,2}", "[DT]", line)
        
        # 2. Structural Regex
        # Pattern: [Channel] (optional #w) Sender (optional [Tag]) : Message
        # Refined: Handle '#w' or similar markers more flexibly.
        # Issue 2: Capture #w and [DT] as part of the sender if they aren't separated by colons.
        # New pattern tries to include #w and trailing tags like [DT] into the sender capture if possible.
        struct_pattern = r"^\[(Allies|Party|Team|All)\]\s*((?:#\w\s+)?.*?(?:\s+\[[^\]]+\])?)\s*[:;!\|]\s*(.*)"
        match = re.match(struct_pattern, line, re.IGNORECASE)
        
        if match:
            parsed["channel"] = match.group(1).capitalize()
            parsed["sender"] = match.group(2).strip()
            # Try to extract sub-tag if present (e.g. [DT])
            tag_match = re.search(r"\[([^\]]+)\]$", parsed["sender"])
            if tag_match:
                parsed["tag"] = tag_match.group(1)
                # We keep it in the sender as requested by "Issue 2" implied behavior 
                # (if #w bamsemats [DT] is the sender, we capture it all)
            
            parsed["message"] = match.group(3).strip()
            parsed["is_structured"] = True
            self.register_sender(parsed["sender"])
        else:
            # Fallback to existing loose parsing if strict structure fails
            temp_line = line
            # Check for channel tag anywhere if strict match failed
            tag_match = re.search(r"(\[(Allies|Party|Team|All)\])", temp_line, re.IGNORECASE)
            if tag_match:
                parsed["channel"] = tag_match.group(2).capitalize()
                temp_line = temp_line.replace(tag_match.group(1), "").strip()
            
            # Clean optional prefix like #w before loose sender extraction
            temp_line = re.sub(r"^#\w\s+", "", temp_line)
            
            sender_match = re.search(r"^([^:;!\|]{1,45})[:;!\|](.*)", temp_line)
            if sender_match:
                parsed["sender"] = sender_match.group(1).strip()
                parsed["message"] = sender_match.group(2).strip()
                # Try to extract [Tag] from sender if it's there
                tag_in_sender = re.search(r"\[([^\]]+)\]$", parsed["sender"])
                if tag_in_sender:
                    parsed["tag"] = tag_in_sender.group(1)
                    parsed["sender"] = parsed["sender"].replace(tag_in_sender.group(0), "").strip()
                self.register_sender(parsed["sender"])

        # Final message cleanup
        parsed["message"] = re.sub(r"^[ :;.,\.\!\|\]\)\}-]+", "", parsed["message"]).strip()
        return parsed
