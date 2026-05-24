import os
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["PADDLE_DISABLE_ONEDNN"] = "1"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import tkinter as tk
from tkinter import ttk, font, messagebox
import threading
import re # Added for chat parsing
import subprocess
import ctypes
import cv2
import requests
from version import __version__

# Enable DPI awareness at the very beginning to fix layout and capture issues
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1) # PROCESS_SYSTEM_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from PIL import ImageTk, Image # Added for image display

from screenshot_utils import RegionSelector, ScreenCapture
from config import AppConfig
from surgical_ocr_pipeline import SurgicalOcrPipeline
from translate.translation_service import TranslationService
from translate.anthropic_service import AnthropicTranslationService
from google_oauth_service import GoogleOAuthService
from keybinding_service import KeybindingService

from pynput import keyboard


# =====================================================
# CONSTANTS
# =====================================================

SUPPORTED_LANGUAGES = [
    {"name": "English", "iso": "en", "paddle": "en"},
    {"name": "Russian", "iso": "ru", "paddle": "ru"},
    {"name": "Japanese", "iso": "ja", "paddle": "japan"},
    {"name": "Chinese (Simp)", "iso": "zh-CN", "paddle": "ch"},
    {"name": "Spanish", "iso": "es", "paddle": "en"},
    {"name": "Portuguese", "iso": "pt", "paddle": "en"},
    {"name": "Turkish", "iso": "tr", "paddle": "en"},
    {"name": "Swedish", "iso": "sv", "paddle": "en"},
    {"name": "German", "iso": "de", "paddle": "en"},
    {"name": "French", "iso": "fr", "paddle": "en"},
]

# Comprehensive PaddleOCR language catalog
PADDLE_LANG_CATALOG = {
    "English": "en", "Russian": "ru", "Japanese": "japan", "Chinese": "ch",
    "Korean": "korean", "French": "french", "German": "german", "Italian": "it",
    "Spanish": "es", "Portuguese": "pt"
}


# =====================================================
# MAIN APPLICATION
# =====================================================

class DotaChatTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Dota 2 Chat Translator v{__version__} (PaddleOCR)")
        self.root.geometry("1600x900")
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.config = AppConfig()
        
        self.resize_timer = None

        # Load config
        self.chat_region = self.config.get_chat_region()
        self.current_font_family = self.config.get_font_family()
        self.current_font_size = self.config.get_font_size()
        self.current_theme = self.config.get_theme()
        self.google_cloud_project_id = self.config.get_project_id()
        self.hotkey_str = self.config.get_hotkey()
        self.target_lang = self.config.get_target_lang()
        self.ocr_langs_str = self.config.get_ocr_langs()
        self.ocr_dashboard_str = self.config.get_ocr_dashboard()
        self.anthropic_api_key = self.config.get_anthropic_api_key()

        # Google services
        self.google_oauth_service = GoogleOAuthService(self.update_notification)
        self.credentials = None

        self.translation_service = TranslationService(self.google_cloud_project_id, target_lang=self.target_lang)
        self.anthropic_service = AnthropicTranslationService(self.anthropic_api_key, target_lang=self.target_lang) if self.anthropic_api_key else None
        
        self.ocr_pipeline = SurgicalOcrPipeline(self.config)
        self.ocr_pipeline.set_translation_service(self.translation_service)
        
        # FIX: Pass app reference for lazy injection since anthropic_service is late-bound
        self.ocr_pipeline._app_ref = self
        print(f"App reference passed to ocr_pipeline for lazy injection.")
        
        # Memory of seen senders to help parse colon-less lines
        self.sender_registry = set() 
        self.recent_messages = [] 
        self.max_recent = 100

        # Hotkey listener
        self.keybinding_service = KeybindingService(self.take_snapshot, self.hotkey_str)
        self.keybinding_service.start_listener()
        
        # Add F7 for calibration
        self.calibration_listener = keyboard.GlobalHotKeys({
            '<f7>': self.trigger_calibration
        })
        self.calibration_listener.start()

        self.last_screenshot_pil = None 
        self.last_screenshot_tk = None 

        self.create_widgets()
        self.apply_font_settings(self.current_font_family, self.current_font_size)
        self.set_theme(self.current_theme)

        self.authorize_google_cloud_startup()

        self.show_startup_status()

        # Check for first run to open README
        if self.config.get_first_run():
            self._open_readme_file()
            self.config.set_first_run(False)

        # Check for updates in the background
        threading.Thread(target=self.check_for_updates, daemon=True).start()

        # Prompt for missing API keys
        if not self.anthropic_api_key:
            self.root.after(2000, lambda: messagebox.showinfo("Anthropic API Key", 
                "Anthropic API key is missing. Claude Vision OCR will be disabled.\n"
                "Please go to Settings to add your key."))

    def check_for_updates(self):
        """Checks for new version on GitHub."""
        try:
            repo_url = "https://api.github.com/repos/bamsemats/Dota2Translator/releases/latest"
            response = requests.get(repo_url, timeout=5)
            if response.status_code == 200:
                latest_release = response.json()
                latest_version = latest_release.get("tag_name", "0.0.0").lstrip('v')
                
                if self.is_newer_version(__version__, latest_version):
                    self.root.after(0, lambda: self.prompt_update(latest_version, latest_release.get("html_url")))
        except Exception as e:
            print(f"Update check failed: {e}")

    def is_newer_version(self, current, latest):
        """Simple semantic version comparison."""
        try:
            curr_parts = [int(p) for p in current.split('.')]
            late_parts = [int(p) for p in latest.split('.')]
            return late_parts > curr_parts
        except:
            return latest != current

    def prompt_update(self, version, url):
        """Prompts the user to update."""
        if messagebox.askyesno("Update Available", 
            f"A new version (v{version}) is available. Would you like to go to the download page?"):
            import webbrowser
            webbrowser.open(url)

    def trigger_calibration(self):
        """
        Callback for F7 calibration hotkey.
        """
        if self.chat_region:
            self.safe_notify("Calibration capture triggered (F7)...")
            # Run in thread to not block UI
            threading.Thread(target=lambda: self.ocr_pipeline.calibrate(self.chat_region), daemon=True).start()
        else:
            self.safe_notify("Cannot calibrate: No region selected.")

    def register_sender(self, sender):
        """
        Adds a sender to the registry.
        """
        self.ocr_pipeline.parser.register_sender(sender)

    def create_widgets(self):
        # Main container
        self.root.configure(bg="#313338" if self.current_theme == "Dark" else "#F2F3F5")
        
        self.main_frame = ttk.Frame(self.root, padding=15)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Header Area
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        # Define larger font for UI elements (NOT the chat font)
        self.ui_font = (self.current_font_family, 11) # Base size is 9, so 11 is +2pt

        self.notification_label = ttk.Label(
            header_frame,
            text="Ready",
            font=self.ui_font,
            anchor="w"
        )
        self.notification_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT)

        # Style for standard buttons
        style = ttk.Style()
        style.configure("TButton", font=self.ui_font)
        style.configure("Accent.TButton", font=self.ui_font)

        ttk.Button(
            button_frame,
            text="Snapshot",
            style="Accent.TButton",
            command=self.take_snapshot
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Settings",
            command=self.open_settings
        ).pack(side=tk.LEFT)

        # Chat Log Area
        self.chat_container = ttk.Frame(self.main_frame)
        self.chat_container.pack(fill=tk.BOTH, expand=True)

        chat_scroll = ttk.Scrollbar(self.chat_container)
        chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.translation_display = tk.Text(
            self.chat_container,
            height=15,
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief=tk.FLAT,
            padx=10,
            pady=10,
            yscrollcommand=chat_scroll.set,
            highlightthickness=0
        )
        self.translation_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chat_scroll.config(command=self.translation_display.yview)

        # Tags
        self.translation_display.tag_configure("bold", font=(self.current_font_family, self.current_font_size, "bold"))
        self.translation_display.tag_configure("message_tag", foreground="white") 
        self.translation_display.tag_configure("original_tag", foreground="#aaaaaa")

        # Screenshot Preview
        self.preview_container = ttk.Frame(self.main_frame, height=400)
        self.preview_container.pack(fill=tk.BOTH, expand=False, pady=(15, 0))
        self.preview_container.pack_propagate(False)

        self.screenshot_frame = ttk.LabelFrame(self.preview_container, text="Preview", padding=5)
        self.screenshot_frame.pack(fill=tk.BOTH, expand=True)

        self.screenshot_label = ttk.Label(self.screenshot_frame, text="No capture", anchor="center")
        self.screenshot_label.pack(fill=tk.BOTH, expand=True)

        # Footer Area (Usage Stats)
        self.footer_frame = ttk.Frame(self.main_frame)
        self.footer_frame.pack(fill=tk.X, pady=(10, 0))

        self.usage_label = ttk.Label(
            self.footer_frame,
            text="OCR: 0/1000 | Trans: 0/500000 | Daily: 0",
            font=(self.current_font_family, 8),
            anchor="e"
        )
        self.usage_label.pack(side=tk.RIGHT)

        self.preview_container.bind("<Configure>", self.on_resize)
        
        self.update_usage_display()

    def update_usage_display(self):
        tracker = self.ocr_pipeline.usage_tracker
        ocr_count = tracker.get_ocr_requests()
        trans_count = tracker.get_translation_characters()
        daily_count = tracker.get_daily_translation_characters()
        
        usage_text = f"OCR: {ocr_count}/{tracker.get_ocr_free_tier_limit()} | " \
                     f"Trans: {trans_count}/{tracker.get_translation_free_tier_limit()} chars | " \
                     f"Daily: {daily_count}"
        
        self.usage_label.config(text=usage_text)

    def set_theme(self, theme_name):
        self.current_theme = theme_name
        self.config.set_theme(theme_name)
        style = ttk.Style(self.root)
        
        theme_file = f"forest-{theme_name.lower()}.tcl"
        theme_path = os.path.join(os.path.dirname(__file__), "theme", theme_file)
        
        if os.path.exists(theme_path):
            try:
                self.root.tk.call("source", theme_path)
                style.theme_use(f"forest-{theme_name.lower()}")
            except:
                style.theme_use("clam")
        else:
            style.theme_use("clam")

    def apply_font_settings(self, family, size):
        self.current_font_family = family
        self.current_font_size = size
        
        # Create a new font object for the chat widget
        chat_font = font.Font(family=family, size=size)
        
        # Update the main Text widget configuration
        self.translation_display.configure(font=chat_font)
        
        # Re-configure all tags with the new font family and size
        # This is critical because tags can override the base widget font
        self.translation_display.tag_configure("bold", font=(family, size, "bold"))
        self.translation_display.tag_configure("sender_tag", font=(family, size, "bold"))
        self.translation_display.tag_configure("message_tag", font=(family, size))
        self.translation_display.tag_configure("allies_tag", font=(family, size))
        self.translation_display.tag_configure("original_tag", font=(family, size))
        
        # Save to config
        self.config.set_font_family(family)
        self.config.set_font_size(size)

    def authorize_google_cloud_startup(self):
        self.credentials = self.google_oauth_service.authorize()
        if self.credentials:
            self.translation_service.initialize_client(self.credentials)

    def show_startup_status(self):
        if not self.chat_region:
            self.update_notification("No chat region set.")
        elif not self.google_cloud_project_id:
            self.update_notification("Set Google Cloud Project ID.")
        elif not self.credentials:
            self.update_notification("Authorize Google Cloud.")
        else:
            self.update_notification("Ready.")

    def on_closing(self):
        self.keybinding_service.stop_listener()
        self.root.destroy()

    def _open_readme_file(self):
        readme_path = os.path.join(os.path.dirname(__file__), "README.md")
        if os.path.exists(readme_path):
            try:
                os.startfile(readme_path)
            except:
                pass

    def take_snapshot(self):
        if not self.chat_region:
            self.update_notification("No chat region selected.")
            return

        if not self.google_cloud_project_id:
            self.update_notification("Google Cloud Project ID missing.")
            return

        if not self.translation_service.client:
            self.update_notification("Google Cloud not authorized.")
            return

        self.update_notification("Starting capture...")

        thread = threading.Thread(
            target=self.run_ocr_pipeline,
            daemon=True
        )
        thread.start()

    def reprocess_last_snapshot(self):
        self.take_snapshot()

    def run_ocr_pipeline(self, deep_scan=False):
        try:
            self.safe_notify("Processing (PaddleOCR)...")
            
            # Get active ISO codes for better language detection
            active_iso = []
            dashboard_langs = self.ocr_dashboard_str.split(",")
            for dl in dashboard_langs:
                match = next((l for l in SUPPORTED_LANGUAGES if l["paddle"] == dl or l["iso"] == dl), None)
                if match:
                    active_iso.append(match["iso"])
            
            # Ensure target language and English are always considered
            if "en" not in active_iso: active_iso.append("en")
            if self.target_lang not in active_iso: active_iso.append(self.target_lang)
            
            def handle_first_frame(frame_bgr):
                # Convert BGR (from CaptureService) to PIL for display
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                self.last_screenshot_pil = pil_img
                self.root.after(0, self.display_last_screenshot)

            # The new pipeline handles capture internally.
            results = self.ocr_pipeline.run(
                self.chat_region, 
                enabled_iso=active_iso, 
                on_first_frame=handle_first_frame
            )

            if not results:
                self.safe_notify("No new text detected.")
                return

            self.root.after(0, lambda: self.display_translation(results))
            self.root.after(0, self.update_usage_display)
            self.safe_notify("Ready.")

        except Exception as e:
            self.safe_notify(f"Error: {e}")
            import traceback
            traceback.print_exc()

    def display_translation(self, results):
        self.translation_display.config(state=tk.NORMAL)
        
        if self.translation_display.index(tk.END) != "1.0":
            self.translation_display.insert(tk.END, "\n")
        
        # High-Contrast Discord-inspired Colors
        if self.current_theme == "Dark":
            bg_color = "#2B2D31"
            tag_color = "#23A559" # Green
            sender_color = "#949CF7" # Light Blurple
            msg_color = "#DBDEE1" # Off-white
            orig_color = "#949BA4" # Grey
        else:
            bg_color = "#FFFFFF"
            tag_color = "#1A8344" # Dark Green
            sender_color = "#4752C4" # Dark Blurple
            msg_color = "#313338" # Dark Grey
            orig_color = "#5C5E66" # Medium Grey

        self.translation_display.config(bg=bg_color)
        self.translation_display.tag_configure("allies_tag", foreground=tag_color)
        self.translation_display.tag_configure("sender_tag", foreground=sender_color, font=(self.current_font_family, self.current_font_size, "bold"))
        self.translation_display.tag_configure("message_tag", foreground=msg_color)
        self.translation_display.tag_configure("original_tag", foreground=orig_color)

        for res in results:
            tag = res.get("tag")
            sender = res.get("sender")
            original_msg = res.get("message", "")
            translated_msg = res.get("translated_message", "")
            lang = res.get("lang", "unknown").upper()

            # 1. Tag [Allies]
            if tag:
                self.translation_display.insert(tk.END, f"[{tag}] ", "allies_tag")
            
            # 2. Sender
            if sender:
                self.translation_display.insert(tk.END, f"{sender}: ", "sender_tag")
            
            # 3. Message / Translation
            # If translated and significantly different
            if translated_msg and translated_msg.lower().strip() != original_msg.lower().strip():
                # Format: [RU] "Осторожно!" -> "Careful!"
                lang_prefix = f"[{lang}] " if lang != "UNKNOWN" else ""
                
                self.translation_display.insert(tk.END, translated_msg + "\n", "message_tag")
                self.translation_display.insert(tk.END, f"\t\t{lang_prefix}\"{original_msg}\"\n", "original_tag")
            else:
                self.translation_display.insert(tk.END, original_msg + "\n", "message_tag")
        
        self.translation_display.see(tk.END)
        self.translation_display.config(state=tk.DISABLED)
        self.update_notification("Done.")


    def on_resize(self, event):
        """
        Handles dynamic resizing of the preview image when the window changes.
        Uses debouncing to avoid excessive processing during rapid drags.
        """
        # Only handle Configure events for the preview_container itself, not its children
        if event.widget != self.preview_container:
            return

        if self.resize_timer:
            self.root.after_cancel(self.resize_timer)
        
        self.resize_timer = self.root.after(100, self.display_last_screenshot)

    def display_last_screenshot(self):
        if self.last_screenshot_pil:
            # Use the actual widget size if it's already rendered
            max_width = self.preview_container.winfo_width()
            max_height = self.preview_container.winfo_height()

            # Fallbacks for initialization or tiny window
            if max_width < 50 or max_height < 50:
                max_width = 1000
                max_height = 380
            
            img_width, img_height = self.last_screenshot_pil.size
            
            # Pad the area to fit nicely inside the frame
            target_w = max_width - 30
            target_h = max_height - 50
            
            ratio = min(target_w / img_width, target_h / img_height)
            new_width = max(1, int(img_width * ratio))
            new_height = max(1, int(img_height * ratio))
            
            # Use NEAREST for upscaling text to keep it crisp
            resampling = Image.Resampling.NEAREST if ratio > 1 else Image.Resampling.LANCZOS
            resized_image = self.last_screenshot_pil.resize((new_width, new_height), resampling)
            self.last_screenshot_tk = ImageTk.PhotoImage(resized_image)
            
            self.screenshot_label.config(image=self.last_screenshot_tk, text="")
        else:
            self.screenshot_label.config(image="", text="No capture")


# =====================================================
# CHAT PARSING
# =====================================================

    def parse_chat_line(self, chat_line):
        parsed = {
            "tag": None,
            "sender": None,
            "message": chat_line.strip()
        }

        temp_line = chat_line.strip()

        # 1. Tag Detection
        # Matches [Allies], (Allies), [All], [Team], [Squelched], etc.
        # Allowing for slight OCR errors like (Allies] or [Alies]
        tag_pattern = r"^[\[\(]?(Allies|Team|All|Squelch\w*|Party)[\]\)]?\s*(.*)"
        tag_match = re.search(tag_pattern, temp_line, re.IGNORECASE)
        
        if tag_match:
            parsed["tag"] = tag_match.group(1).capitalize()
            # If tag was missing brackets, we still count it but clean the text
            temp_line = tag_match.group(2).strip()
        else:
            # Fallback for even noisier tags: look for the words anywhere near start
            loose_tag_match = re.search(r"(Allies|All|Team|Party)", temp_line[:15], re.IGNORECASE)
            if loose_tag_match:
                parsed["tag"] = loose_tag_match.group(1).capitalize()
                # Remove the tag word and any surrounding non-alnum noise
                temp_line = re.sub(r"^[^\w\d]*" + re.escape(loose_tag_match.group(0)) + r"[^\w\d]*", "", temp_line, flags=re.IGNORECASE).strip()

        # 2. Sender Detection
        # Case A: Colon, Semicolon, or common OCR misreads (like . or i at the end of a word)
        # We look for a delimiter within the first 30 characters
        # Delimiters: : ; ! | and sometimes dots if they follow a bracket/name
        sender_match = re.search(r"^([^:;!\|]{1,30})[:;!\|](.*)", temp_line)
        if not sender_match:
            # Fallback for dots or common colon misreads as 'i' or 'l'
            # Only if it follows a likely name structure (like ending in a bracket)
            sender_match = re.search(r"^([^:;]{1,30}[\]\)])[\.\sil](.*)", temp_line)
            
        if not sender_match:
            # Look for a space and a dot (common misread of ' :')
            sender_match = re.search(r"^([^:;]{1,30})\s\.(.*)", temp_line)

        if sender_match:
            potential_sender = sender_match.group(1).strip()
            message_part = sender_match.group(2).strip()

            # Validate sender: at least 1 alphanumeric character
            if any(c.isalnum() for c in potential_sender):
                parsed["sender"] = potential_sender
                parsed["message"] = message_part
                if len(potential_sender) > 2:
                    self.register_sender(potential_sender)
            else:
                parsed["message"] = temp_line
        
        # Case B: No colon, check against registry or look for first word
        else:
            words = temp_line.split(" ")
            if words:
                first_word = words[0].rstrip(":;,. ").strip()
                if first_word.lower() in self.sender_registry:
                    parsed["sender"] = first_word
                    parsed["message"] = " ".join(words[1:]).strip()
                
                # Case C: No colon, but we have a tag - first word is VERY likely the sender
                elif parsed["tag"] and len(words) > 1:
                    potential_sender = words[0].strip()
                    # If it's a plausible name length and not just punctuation
                    if 1 <= len(potential_sender) <= 20 and any(c.isalnum() for c in potential_sender):
                        parsed["sender"] = potential_sender
                        parsed["message"] = " ".join(words[1:]).strip()
                        self.register_sender(potential_sender)
                    else:
                        parsed["message"] = temp_line
                else:
                    parsed["message"] = temp_line

        # Final surgical cleanup
        # We only want to remove leading colons/semicolons and surrounding whitespace
        # that Tesseract sometimes orphans at the start of the message part.
        parsed["message"] = re.sub(r"^[ :;.,\.]+", "", parsed["message"]).strip()
        
        # If the resulting message is just one char or nonsense, discard it
        if len(parsed["message"]) < 2 and not any(c.isalnum() for c in parsed["message"]):
             parsed["message"] = ""

        return parsed


# =====================================================
# SETTINGS WINDOW
# =====================================================

    def open_settings(self):
        SettingsWindow(
            self.root,
            self.select_chat_region,
            self.update_notification,
            self.current_font_family,
            self.current_font_size,
            self.apply_font_settings,
            self.current_theme,
            self.set_theme,
            self.config,
            self.authorize_google_cloud,
            self.hotkey_str,
            self.set_hotkey_from_settings,
            self.target_lang,
            self.set_target_lang,
            self.ocr_langs_str,
            self.set_ocr_langs,
            self.ocr_dashboard_str,
            self.set_ocr_dashboard,
            self.recalibrate_geometry
        )


# =====================================================
# REGION SELECTION
# =====================================================

    def select_chat_region(self, window_to_hide_for_selector=None):
        self.update_notification("Select chat region...")
        selector = RegionSelector(self.root, window_to_hide=window_to_hide_for_selector)

        region = selector.get_region()

        if region:
            self.chat_region = region
            self.config.set_chat_region(region)
            self.update_notification(f"Region set: {region}")
            # Automatic Calibration
            self.recalibrate_geometry()
        else:
            self.update_notification("Selection cancelled.")

    def recalibrate_geometry(self):
        if self.chat_region:
            self.update_notification("Auto-calibrating geometry...")
            res = self.ocr_pipeline.calibrate(self.chat_region)
            if "WARNING" in res:
                tk.messagebox.showwarning("Calibration", res)
            self.update_notification(res)
        else:
            self.update_notification("No region set to calibrate.")

# =====================================================
# HOTKEY
# =====================================================

    def set_hotkey_from_settings(self, new_hotkey):
        self.hotkey_str = new_hotkey
        self.config.set_hotkey(new_hotkey)

        self.keybinding_service.set_hotkey(new_hotkey)

        self.update_notification(f"Hotkey set: {new_hotkey}")


    def set_target_lang(self, lang_code):
        self.target_lang = lang_code
        self.config.set_target_lang(lang_code)
        self.translation_service.set_target_lang(lang_code)
        self.update_notification(f"Target language: {lang_code}")

    def set_ocr_langs(self, langs_str):
        self.ocr_langs_str = langs_str
        self.config.set_ocr_langs(langs_str)
        
        # Mapper for legacy Tesseract codes to PaddleOCR codes
        legacy_map = {
            "eng": "en",
            "rus": "ru",
            "chi_sim": "ch",
            "jpn": "japan",
            "spa": "en",
            "por": "en",
            "fra": "en",
            "deu": "en",
            "swe": "en",
            "tur": "en"
        }

        # Language Selection Strategy:
        # PaddleOCR uses specialized models for different scripts.
        # Prioritize 'japan', 'ru', or 'ch' as they are inclusive models.
        
        lang_list = [l.strip() for l in langs_str.split(",")] if langs_str else ["en"]
        mapped_langs = [legacy_map.get(l, l) for l in lang_list]
        
        # Prioritize inclusive models for maximum coverage
        if "japan" in mapped_langs:
            primary_lang = "japan"
        elif "ru" in mapped_langs:
            primary_lang = "ru"
        elif "ch" in mapped_langs:
            primary_lang = "ch"
        else:
            primary_lang = mapped_langs[0]
            
        self.ocr_pipeline.set_language(primary_lang)
        self.update_notification(f"Multilingual OCR ready (Model: {primary_lang})")

    def set_ocr_dashboard(self, dashboard_str):
        self.ocr_dashboard_str = dashboard_str
        self.config.set_ocr_dashboard(dashboard_str)


# =====================================================
# UTILITIES
# =====================================================

    def update_notification(self, msg):
        self.notification_label.config(text=msg)
        print(msg)


    def safe_notify(self, msg):
        self.root.after(0, lambda: self.update_notification(msg))


    def authorize_google_cloud(self):
        self.credentials = self.google_oauth_service.authorize()

        if self.credentials:
            # self.ocr_service.initialize_client(self.credentials) # No longer needed
            self.translation_service.initialize_client(self.credentials)
            self.update_notification("Google Cloud authorized.")


    def show_startup_status(self):
        if not self.chat_region:
            self.update_notification("No chat region set.")
        elif not self.google_cloud_project_id:
            self.update_notification("Set Google Cloud Project ID.")
        elif not self.credentials:
            self.update_notification("Authorize Google Cloud.")
        else:
            self.update_notification("Ready.")


    def on_closing(self):
        self.keybinding_service.stop_listener()
        self.root.destroy()

# =====================================================
# AUTO-OPEN README ON FIRST RUN
# =====================================================

    def _open_readme_file(self):
        readme_path = os.path.join(os.path.dirname(__file__), "README.md")
        if os.path.exists(readme_path):
            try:
                # Use os.startfile for Windows to open with default application
                os.startfile(readme_path)
                self.update_notification("Opened README.md for first-time setup.")
            except Exception as e:
                self.update_notification(f"Could not open README.md: {e}")
        else:
            self.update_notification("README.md not found. Please ensure it's in the app's directory.")

# =====================================================
# SETTINGS WINDOW CLASS
# =====================================================

class SettingsWindow(tk.Toplevel):
    def __init__(
        self,
        master,
        select_region_cb,
        notify_cb,
        current_font,
        current_size,
        apply_font_cb,
        current_theme,
        set_theme_cb,
        config,
        authorize_cb,
        current_hotkey,
        set_hotkey_cb,
        current_target_lang,
        set_target_lang_cb,
        current_ocr_langs,
        set_ocr_langs_cb,
        current_ocr_dashboard,
        set_ocr_dashboard_cb,
        recalibrate_cb
    ):
        super().__init__(master)
        self.title("Settings")
        self.geometry("540x950") # Increased height for Anthropic API
        self.resizable(False, False)
        self.grab_set()

        self.notify = notify_cb
        self.apply_font = apply_font_cb
        self.set_theme = set_theme_cb
        self.config = config
        self.authorize = authorize_cb
        self.set_hotkey = set_hotkey_cb
        self.set_target_lang = set_target_lang_cb
        self.set_ocr_langs = set_ocr_langs_cb
        self.set_ocr_dashboard = set_ocr_dashboard_cb
        self.recalibrate = recalibrate_cb

        # Match theme background
        bg_color = "#313338" if current_theme == "Dark" else "#F2F3F5"
        self.configure(bg=bg_color)

        # Main container with a scrollbar because it's getting long
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, bg=bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.main = self.scrollable_frame # Redirect old code to use the scrollable part

        # Region
        self.select_region_cb = select_region_cb

        region_frame = ttk.LabelFrame(self.main, text="Chat Region & Geometry", padding=10)
        region_frame.pack(fill=tk.X, padx=20, pady=(10, 5))

        ttk.Button(
            region_frame,
            text="Select New Region",
            style="Accent.TButton",
            command=self._on_select_region_button_click
        ).pack(fill=tk.X, pady=5)

        ttk.Button(
            region_frame,
            text="Recalibrate Chat Geometry",
            command=self.recalibrate
        ).pack(fill=tk.X, pady=5)

        ttk.Label(region_frame, text="Make sure 2-3 lines are visible in chat before recalibrating.", font=("", 8), foreground="grey").pack(pady=2)

        # Languages
        lang_frame = ttk.LabelFrame(self.main, text="Languages", padding=10)
        lang_frame.pack(fill=tk.X, padx=20, pady=10)

        # Target Language Dropdown
        ttk.Label(lang_frame, text="Translate To:").pack(anchor="w")
        self.target_lang_var = tk.StringVar(value=next((l["name"] for l in SUPPORTED_LANGUAGES if l["iso"] == current_target_lang), "English"))
        target_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.target_lang_var,
            values=[l["name"] for l in SUPPORTED_LANGUAGES],
            state="readonly"
        )
        target_combo.pack(fill=tk.X, pady=(2, 10))
        target_combo.bind("<<ComboboxSelected>>", self.save_target_lang)

        # OCR Languages Section
        ttk.Label(lang_frame, text="Detect Chat Languages (OCR):").pack(anchor="w")
        
        # Add Language Dropdown
        add_lang_frame = ttk.Frame(lang_frame)
        add_lang_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.add_lang_var = tk.StringVar()
        lang_names = sorted(PADDLE_LANG_CATALOG.keys())
        self.add_lang_combo = ttk.Combobox(
            add_lang_frame, 
            textvariable=self.add_lang_var, 
            values=lang_names,
            state="readonly"
        )
        self.add_lang_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.add_lang_combo.set("Add Language...")
        
        ttk.Button(
            add_lang_frame, 
            text="Add", 
            width=5,
            command=self.add_ocr_language
        ).pack(side=tk.RIGHT)

        # Dynamic Grid for Checkboxes + Delete buttons
        self.ocr_grid_container = ttk.Frame(lang_frame)
        self.ocr_grid_container.pack(fill=tk.X, pady=5)
        
        self.ocr_vars = {} # {tess_code: BooleanVar}
        self.dashboard_list = current_ocr_dashboard.split(",")
        self.active_list = current_ocr_langs.split(",")
        
        self.refresh_ocr_list()

        # Hotkey
        key_frame = ttk.LabelFrame(self.main, text="Snapshot Hotkey", padding=10)
        key_frame.pack(fill=tk.X, padx=20, pady=10)

        self.hotkey_var = tk.StringVar(value=current_hotkey)

        hotkey_entry = ttk.Entry(
            key_frame,
            textvariable=self.hotkey_var,
            justify="center"
        )
        hotkey_entry.pack(fill=tk.X, pady=5)
        hotkey_entry.bind("<FocusIn>", self.capture_hotkey)

        ttk.Button(
            key_frame,
            text="Save Hotkey",
            command=self.save_hotkey
        ).pack(fill=tk.X, pady=5)

        # Appearance (Font & Theme)
        appearance_frame = ttk.LabelFrame(self.main, text="Appearance", padding=10)
        appearance_frame.pack(fill=tk.X, padx=20, pady=10)

        # Font Family
        ttk.Label(appearance_frame, text="Font Family").pack(anchor="w")
        self.font_family = tk.StringVar(value=current_font)
        font_combo = ttk.Combobox(
            appearance_frame,
            textvariable=self.font_family,
            values=sorted(font.families()),
            state="readonly"
        )
        font_combo.pack(fill=tk.X, pady=(2, 8))
        font_combo.bind("<<ComboboxSelected>>", lambda e: self.update_font())

        # Font Size & Theme Row
        row_frame = ttk.Frame(appearance_frame)
        row_frame.pack(fill=tk.X)

        size_frame = ttk.Frame(row_frame)
        size_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Label(size_frame, text="Size").pack(anchor="w")
        self.font_size = tk.IntVar(value=current_size)
        ttk.Spinbox(
            size_frame,
            from_=8,
            to=36,
            textvariable=self.font_size,
            command=self.update_font
        ).pack(fill=tk.X)

        theme_inner_frame = ttk.Frame(row_frame)
        theme_inner_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        ttk.Label(theme_inner_frame, text="Theme").pack(anchor="w")
        self.theme_var = tk.StringVar(value=current_theme)
        theme_combo = ttk.Combobox(
            theme_inner_frame,
            textvariable=self.theme_var,
            values=["Light", "Dark"],
            state="readonly"
        )
        theme_combo.pack(fill=tk.X)
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self.update_theme())

        # Anthropic API
        anthropic_frame = ttk.LabelFrame(self.main, text="Anthropic API (Claude Vision)", padding=10)
        anthropic_frame.pack(fill=tk.X, padx=20, pady=10)

        ant_label_row = ttk.Frame(anthropic_frame)
        ant_label_row.pack(fill=tk.X)
        ttk.Label(ant_label_row, text="API Key").pack(side=tk.LEFT)
        ttk.Button(ant_label_row, text="?", width=2, command=self.show_anthropic_help).pack(side=tk.RIGHT)

        self.anthropic_key_var = tk.StringVar(value=config.get_anthropic_api_key())
        ttk.Entry(
            anthropic_frame,
            textvariable=self.anthropic_key_var,
            show="*" # Mask the key
        ).pack(fill=tk.X, pady=(2, 8))

        ttk.Button(
            anthropic_frame,
            text="Save Anthropic Key",
            command=self.save_anthropic_key
        ).pack(fill=tk.X)

        # Google Cloud
        gcp_frame = ttk.LabelFrame(self.main, text="Google Cloud API (Legacy)", padding=10)
        gcp_frame.pack(fill=tk.X, padx=20, pady=10)

        gcp_label_row = ttk.Frame(gcp_frame)
        gcp_label_row.pack(fill=tk.X)
        ttk.Label(gcp_label_row, text="Project ID").pack(side=tk.LEFT)
        ttk.Button(gcp_label_row, text="?", width=2, command=self.show_google_help).pack(side=tk.RIGHT)

        self.project_id = tk.StringVar(value=config.get_project_id())
        ttk.Entry(
            gcp_frame,
            textvariable=self.project_id
        ).pack(fill=tk.X, pady=(2, 8))

        btn_row = ttk.Frame(gcp_frame)
        btn_row.pack(fill=tk.X)
        
        ttk.Button(
            btn_row,
            text="Save ID",
            command=self.save_project
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(
            btn_row,
            text="Authorize",
            command=self.authorize
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

    def show_anthropic_help(self):
        help_win = tk.Toplevel(self)
        help_win.title("How to get an Anthropic API Key")
        help_win.geometry("450x300")
        help_win.resizable(False, False)
        
        txt = tk.Text(help_win, wrap=tk.WORD, padx=10, pady=10)
        txt.pack(fill=tk.BOTH, expand=True)
        
        guide = (
            "1. Go to https://console.anthropic.com/\n"
            "2. Create an account and sign in.\n"
            "3. Navigate to 'API Keys' in the dashboard.\n"
            "4. Click 'Create Key' and give it a name.\n"
            "5. Copy the key (starts with 'sk-ant-') and paste it here.\n\n"
            "Note: You may need to add credits to your account to use the API."
        )
        txt.insert(tk.END, guide)
        txt.config(state=tk.DISABLED)

    def show_google_help(self):
        help_win = tk.Toplevel(self)
        help_win.title("How to set up Google Cloud")
        help_win.geometry("450x350")
        help_win.resizable(False, False)
        
        txt = tk.Text(help_win, wrap=tk.WORD, padx=10, pady=10)
        txt.pack(fill=tk.BOTH, expand=True)
        
        guide = (
            "1. Go to https://console.cloud.google.com/\n"
            "2. Create a new project.\n"
            "3. Copy the 'Project ID' and paste it here.\n"
            "4. Enable 'Cloud Translation API' in the API Library.\n"
            "5. Create OAuth 2.0 Client ID (Desktop App) in Credentials.\n"
            "6. Download the JSON file, rename it to 'client_secret.json', "
            "and place it in the application folder.\n"
            "7. Click 'Authorize' in this settings menu."
        )
        txt.insert(tk.END, guide)
        txt.config(state=tk.DISABLED)


    def _on_select_region_button_click(self):
        # Release the grab on this SettingsWindow before starting region selection
        self.grab_release()
        
        # Call the main app's select_chat_region, passing *this* SettingsWindow instance
        # so it can be temporarily withdrawn by the RegionSelector.
        self.select_region_cb(window_to_hide_for_selector=self)
        
        # Re-establish the grab on this SettingsWindow after selection is complete
        self.grab_set()


# =====================================================
# SETTINGS HELPERS
# =====================================================

    def refresh_ocr_list(self):
        """Rebuilds the OCR language list UI from dashboard_list."""
        for widget in self.ocr_grid_container.winfo_children():
            widget.destroy()
            
        self.ocr_vars = {}
        # Reverse lookup for display names
        rev_catalog = {v: k for k, v in PADDLE_LANG_CATALOG.items()}
        
        for i, tess_code in enumerate(self.dashboard_list):
            if not tess_code: continue
            
            row = ttk.Frame(self.ocr_grid_container)
            row.pack(fill=tk.X, pady=1)
            
            is_checked = tess_code in self.active_list
            var = tk.BooleanVar(value=is_checked)
            self.ocr_vars[tess_code] = var
            
            display_name = rev_catalog.get(tess_code, tess_code)
            
            cb = ttk.Checkbutton(
                row, 
                text=display_name, 
                variable=var,
                command=self.save_ocr_langs
            )
            cb.pack(side=tk.LEFT)
            
            # Delete button (X)
            # Use a lambda with captured tess_code
            ttk.Button(
                row, 
                text="X", 
                width=2,
                command=lambda tc=tess_code: self.remove_ocr_language(tc)
            ).pack(side=tk.RIGHT)

    def add_ocr_language(self):
        lang_name = self.add_lang_var.get()
        if lang_name in PADDLE_LANG_CATALOG:
            tess_code = PADDLE_LANG_CATALOG[lang_name]
            if tess_code not in self.dashboard_list:
                self.dashboard_list.append(tess_code)
                # Automatically enable it when added
                if tess_code not in self.active_list:
                    self.active_list.append(tess_code)
                
                self.save_ocr_dashboard_state()
                self.refresh_ocr_list()
                self.save_ocr_langs()
                self.notify(f"Added {lang_name}")
            else:
                self.notify(f"{lang_name} already in list")
        
    def remove_ocr_language(self, tess_code):
        if tess_code in self.dashboard_list:
            self.dashboard_list.remove(tess_code)
            if tess_code in self.active_list:
                self.active_list.remove(tess_code)
            
            self.save_ocr_dashboard_state()
            self.refresh_ocr_list()
            self.save_ocr_langs()
            self.notify(f"Removed {tess_code}")

    def save_ocr_dashboard_state(self):
        dashboard_str = ",".join(self.dashboard_list)
        self.set_ocr_dashboard(dashboard_str)

    def save_target_lang(self, event=None):
        name = self.target_lang_var.get()
        lang_obj = next((l for l in SUPPORTED_LANGUAGES if l["iso"] == current_target_lang), None)
        if lang_obj:
            self.set_target_lang(lang_obj["iso"])
            self.notify(f"Target language set to {name}")

    def save_ocr_langs(self):
        selected = [tess for tess, var in self.ocr_vars.items() if var.get()]
        if not selected:
            # Don't allow empty selection, default back to English if available
            if "eng" in self.ocr_vars:
                selected = ["eng"]
                self.ocr_vars["eng"].set(True)
            elif self.dashboard_list:
                selected = [self.dashboard_list[0]]
                self.ocr_vars[selected[0]].set(True)
        
        self.active_list = selected
        langs_str = ",".join(selected)
        self.set_ocr_langs(langs_str)
        self.notify(f"OCR languages updated")

    def update_font(self):
        self.apply_font(
            self.font_family.get(),
            self.font_size.get()
        )
        self.notify("Font updated.")


    def update_theme(self):
        new_theme = self.theme_var.get()
        self.set_theme(new_theme)
        
        # Update Settings window background live
        bg_color = "#313338" if new_theme == "Dark" else "#F2F3F5"
        self.configure(bg=bg_color)
        
        # Force redraw of the settings window widgets to pick up style changes
        # By re-applying the style to the main frame explicitly if needed
        # but ttk.Style changes should be global.
        
        self.notify(f"Theme set to {new_theme}")


    def save_project(self):
        pid = self.project_id.get()
        self.config.set_project_id(pid)
        self.notify("Project ID saved.")

    def save_anthropic_key(self):
        key = self.anthropic_key_var.get().strip()
        self.config.set_anthropic_api_key(key)
        # Inform user to restart for change to take effect
        self.notify("Anthropic Key saved. Please restart the app.")
        messagebox.showinfo("Anthropic API", "API key saved successfully.\nPlease restart the application to enable Claude Vision OCR.")


# =====================================================
# HOTKEY CAPTURE (CLEAN)
# =====================================================

    def capture_hotkey(self, event):
        self.notify("Press hotkey combo (Esc to cancel)")
        self.hotkey_var.set("Listening...")

        pressed = set()

        def on_press(key):
            if key == keyboard.Key.esc:
                listener.stop()
                self.hotkey_var.set(self.config.get_hotkey())
                self.notify("Cancelled.")
                return

            pressed.add(key)

            if any(isinstance(k, keyboard.KeyCode) for k in pressed):
                combo = []

                for k in pressed:
                    if k in [keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
                        combo.append("<ctrl>")
                    elif k in [keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r]:
                        combo.append("<alt>")
                    elif k in [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r]:
                        combo.append("<shift>")
                    elif isinstance(k, keyboard.KeyCode):
                        combo.append(k.char.lower())

                hotkey = "+".join(combo)

                self.hotkey_var.set(hotkey)
                listener.stop()

        listener = keyboard.Listener(on_press=on_press)
        listener.start()


    def save_hotkey(self):
        val = self.hotkey_var.get()

        if "+" not in val:
            self.notify("Invalid hotkey.")
            return

        self.set_hotkey(val)
        self.notify(f"Saved hotkey: {val}")


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = DotaChatTranslatorApp(root)
    root.mainloop()
