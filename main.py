import tkinter as tk
from tkinter import ttk, font
import threading
import os
import re # Added for chat parsing
import subprocess

from PIL import ImageTk, Image # Added for image display

from screenshot_utils import RegionSelector, ScreenCapture
from config import AppConfig
from ocr_service import OcrService
from translation_service import TranslationService
from google_oauth_service import GoogleOAuthService
from keybinding_service import KeybindingService

from pynput import keyboard


# =====================================================
# MAIN APPLICATION
# =====================================================

class DotaChatTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dota 2 Chat Translator")
        self.root.geometry("1280x960") # Increased by 25% (1024x768 -> 1280x960)
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.config = AppConfig()
        
        self.resize_timer = None # Timer for debouncing resizes

        # Load config
        self.chat_region = self.config.get_chat_region()
        self.current_font_family = self.config.get_font_family()
        self.current_font_size = self.config.get_font_size()
        self.current_theme = self.config.get_theme()
        self.google_cloud_project_id = self.config.get_project_id()
        self.hotkey_str = self.config.get_hotkey()

        # Google services
        self.google_oauth_service = GoogleOAuthService(self.update_notification)
        self.credentials = None

        self.ocr_service = OcrService() # No longer needs project_id
        self.translation_service = TranslationService(self.google_cloud_project_id)
        
        # Memory of seen senders to help parse colon-less lines
        self.sender_registry = set() 

        # Hotkey listener
        self.keybinding_service = KeybindingService(self.take_snapshot, self.hotkey_str)
        self.keybinding_service.start_listener()

        self.last_screenshot_pil = None # Stores the PIL Image object
        self.last_screenshot_tk = None # Stores the PhotoImage object for Tkinter to display

        self.create_widgets()
        self.apply_font_settings(self.current_font_family, self.current_font_size)
        self.set_theme(self.current_theme)

        self.authorize_google_cloud_startup()

        self.show_startup_status()

        # Check for first run to open README
        if self.config.get_first_run():
            self._open_readme_file()
            self.config.set_first_run(False)

    def register_sender(self, sender):
        """
        Adds a sender to the registry, with a cap on the total number of senders
        to prevent memory issues over long sessions.
        """
        if not sender:
            return
            
        sender_lower = sender.lower()
        if len(self.sender_registry) > 100:
            # Clear if it gets too large, it will rebuild from new chat lines
            self.sender_registry.clear()
            
        self.sender_registry.add(sender_lower)


# =====================================================
# UI SETUP
# =====================================================

    def create_widgets(self):
        # Main container with a Discord-ish background
        self.root.configure(bg="#313338" if self.current_theme == "Dark" else "#F2F3F5")
        
        self.main_frame = ttk.Frame(self.root, padding=15)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Header Area
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        self.notification_label = ttk.Label(
            header_frame,
            text="Ready",
            font=(self.current_font_family, 9),
            anchor="w"
        )
        self.notification_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT)

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

        # Add a scrollbar to the text widget
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
            highlightthickness=0,
            tabs=(80, 200) # Defined tab stops for columns
        )
        self.translation_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chat_scroll.config(command=self.translation_display.yview)

        # Tags
        self.translation_display.tag_configure("bold", font=(self.current_font_family, self.current_font_size, "bold"))
        self.translation_display.tag_configure("allies_tag", foreground="#23A559") # Discord Green
        self.translation_display.tag_configure("sender_tag", foreground="#5865F2") # Discord Blurple
        self.translation_display.tag_configure("message_tag", foreground="white") 
        self.translation_display.tag_configure("original_tag", foreground="#aaaaaa")

        # Screenshot Preview - Increased height for better visibility
        self.preview_container = ttk.Frame(self.main_frame, height=400)
        self.preview_container.pack(fill=tk.BOTH, expand=False, pady=(15, 0))
        self.preview_container.pack_propagate(False)

        self.screenshot_frame = ttk.LabelFrame(self.preview_container, text="Preview", padding=5)
        self.screenshot_frame.pack(fill=tk.BOTH, expand=True)

        self.screenshot_label = ttk.Label(self.screenshot_frame, text="No capture", anchor="center")
        self.screenshot_label.pack(fill=tk.BOTH, expand=True)

        # Bind resize event to update preview scaling
        self.preview_container.bind("<Configure>", self.on_resize)


# =====================================================
# THEMES
# =====================================================

    def set_theme(self, theme_name):
        self.current_theme = theme_name
        self.config.set_theme(theme_name)

        style = ttk.Style(self.root)
        
        # Load Forest Theme
        theme_file = f"forest-{theme_name.lower()}.tcl"
        theme_path = os.path.join(os.path.dirname(__file__), "theme", theme_file)
        
        theme_loaded = False
        if os.path.exists(theme_path):
            try:
                self.root.tk.call("source", theme_path)
                style.theme_use(f"forest-{theme_name.lower()}")
                theme_loaded = True
            except Exception as e:
                print(f"Error loading forest theme: {e}")
        
        if not theme_loaded:
            style.theme_use("clam")

        # Explicitly configure colors to ensure Discord look
        if theme_name == "Dark":
            bg_color = "#313338"
            panel_color = "#2B2D31"
            text_color = "#DBDEE1"
            accent_color = "#5865F2"
            btn_color = "#4E5058"
            
            self.root.configure(bg=bg_color)
            style.configure("TFrame", background=bg_color)
            style.configure("TLabel", background=bg_color, foreground=text_color)
            style.configure("TLabelframe", background=bg_color, foreground=text_color)
            style.configure("TLabelframe.Label", background=bg_color, foreground=text_color)
            
            # Button Styling
            style.configure("TButton", background=btn_color, foreground="white")
            style.map("TButton", background=[("active", "#6D6F78")])
            style.configure("Accent.TButton", background=accent_color, foreground="white")
            style.map("Accent.TButton", background=[("active", "#4752C4")])
            
            self.translation_display.config(
                bg=panel_color,
                fg=text_color,
                insertbackground="white"
            )
            self.translation_display.tag_configure("allies_tag", foreground="#23A559") 
            self.translation_display.tag_configure("sender_tag", foreground="#949CF7")
            self.translation_display.tag_configure("message_tag", foreground=text_color)
            self.translation_display.tag_configure("original_tag", foreground="#949BA4")
        else:
            bg_color = "#F2F3F5"
            panel_color = "#FFFFFF"
            text_color = "#313338"
            accent_color = "#5865F2"
            btn_color = "#E3E5E8"
            
            self.root.configure(bg=bg_color)
            style.configure("TFrame", background=bg_color)
            style.configure("TLabel", background=bg_color, foreground=text_color)
            style.configure("TLabelframe", background=bg_color, foreground=text_color)
            style.configure("TLabelframe.Label", background=bg_color, foreground=text_color)
            
            # Button Styling
            style.configure("TButton", background=btn_color, foreground=text_color)
            style.map("TButton", background=[("active", "#D1D3D7")])
            style.configure("Accent.TButton", background=accent_color, foreground="white")
            style.map("Accent.TButton", background=[("active", "#4752C4")])
            
            self.translation_display.config(
                bg=panel_color,
                fg=text_color,
                insertbackground="black"
            )
            self.translation_display.tag_configure("allies_tag", foreground="#1A8344")
            self.translation_display.tag_configure("sender_tag", foreground="#5865F2")
            self.translation_display.tag_configure("message_tag", foreground=text_color)
            self.translation_display.tag_configure("original_tag", foreground="#5C5E66")
        
        # Style the Accent Button if the theme supports it (Forest does)
        if theme_loaded:
            style.configure("Accent.TButton", padding=6)
        else:
            # Fallback for clam/default
            style.configure("Accent.TButton", foreground="white", background="#5865F2")


# =====================================================
# FONTS
# =====================================================

    def apply_font_settings(self, family, size):
        self.current_font_family = family
        self.current_font_size = size

        new_font = font.Font(family=family, size=size)

        self.translation_display.config(font=new_font)
        
        # Dynamically update tab stops based on font size
        # We use a character-width measurement for consistency
        avg_char_width = new_font.measure("0")
        tab1 = avg_char_width * 11 # Approx 11 chars for [Allies] tag
        tab2 = avg_char_width * 30 # Approx 30 chars for sender (total)
        self.translation_display.config(tabs=(tab1, tab2))

        self.translation_display.tag_configure("bold", font=(family, size, "bold")) # Update bold tag


        self.config.set_font_family(family)
        self.config.set_font_size(size)


# =====================================================
# GOOGLE AUTH
# =====================================================

    def authorize_google_cloud_startup(self):
        self.credentials = self.google_oauth_service.authorize()

        if self.credentials:
            # self.ocr_service.initialize_client(self.credentials) # No longer needed
            self.translation_service.initialize_client(self.credentials)


# =====================================================
# SNAPSHOT + OCR THREADING
# =====================================================

    def take_snapshot(self):
        if not self.chat_region:
            self.update_notification("No chat region selected.")
            return

        if not self.google_cloud_project_id:
            self.update_notification("Google Cloud Project ID missing.")
            return

        # OCR client is local, so we only need to check the translation client
        if not self.translation_service.client:
            self.update_notification("Google Cloud not authorized.")
            return

        self.update_notification("Processing OCR + Translation...")

        thread = threading.Thread(
            target=self.run_ocr_pipeline,
            daemon=True
        )
        thread.start()


    def run_ocr_pipeline(self):
        try:
            capturer = ScreenCapture()
            screenshot = capturer.capture_region(self.chat_region)

            if not screenshot:
                self.safe_notify("Screenshot failed.")
                return

            self.last_screenshot_pil = screenshot # Store the PIL Image
            
            # Update the UI with the screenshot preview
            self.root.after(0, self.display_last_screenshot)

            # --- PASS 1: Get Message Lines (White text only) ---
            extracted_data = self.ocr_service.extract_text_from_image(screenshot)

            processed_messages = []

            for data in extracted_data:
                text = data["text"]
                y_bounds = data["y_bounds"]
                hsv = data["full_hsv"]

                # Detect Tag and Message from the white text
                parsed = self.parse_chat_line(text)
                
                # If no tag found, default to 'All'
                if not parsed["tag"]:
                    parsed["tag"] = "All"

                # --- PASS 2: Get Sender Name (Colored text only) ---
                # Targeted search within the same vertical bounds
                sender_name = self.ocr_service.extract_sender_from_line(hsv, y_bounds)
                if sender_name:
                    parsed["sender"] = sender_name
                    
                    # Deduplication Logic: If the message still starts with the sender's name, strip it.
                    # We check the first few words of the message against the detected sender.
                    msg_text = parsed["message"]
                    sender_clean = re.sub(r'\W+', ' ', sender_name.lower()).strip()
                    sender_parts = set(sender_clean.split())
                    
                    msg_words = msg_text.split()
                    strip_idx = 0
                    for i in range(min(len(msg_words), 4)): # Check first 4 words
                        word_clean = re.sub(r'\W+', '', msg_words[i].lower())
                        if word_clean in sender_parts or any(p in word_clean for p in sender_parts if len(p) > 2):
                            strip_idx = i + 1
                        else:
                            break
                    
                    if strip_idx > 0:
                        parsed["message"] = " ".join(msg_words[strip_idx:]).strip()
                        # Final cleanup for any leftover colon/dots
                        parsed["message"] = re.sub(r"^[ :;.,\.]+", "", parsed["message"]).strip()
                
                # Translation pass
                original_msg = parsed["message"]
                if original_msg:
                    _, translated_msg = self.translation_service.translate_text(original_msg, "und")
                    parsed["translated_message"] = translated_msg
                else:
                    parsed["translated_message"] = ""

                processed_messages.append(parsed)

            self.root.after(0, lambda: self.display_translation(processed_messages))

        except Exception as e:
            self.safe_notify(f"Error: {e}")
            import traceback
            traceback.print_exc()


    def display_translation(self, processed_messages):
        self.translation_display.config(state=tk.NORMAL)
        
        # Add a newline only if there's already content
        if self.translation_display.index(tk.END) != "1.0":
            self.translation_display.insert(tk.END, "\n")
        
        for msg_obj in processed_messages:
            tag = msg_obj["tag"]
            sender = msg_obj["sender"]
            original_msg = msg_obj["message"]
            translated_msg = msg_obj["translated_message"]

            # 1. Column 1: Tag
            if tag:
                tag_str = f"[{tag}]"
                self.translation_display.insert(tk.END, tag_str, "allies_tag")
            
            self.translation_display.insert(tk.END, "\t")

            # 2. Column 2: Sender
            # If the sender pass detected a name, use it. Otherwise, use what the main pass found.
            display_sender = sender if sender else ""
            if display_sender:
                self.translation_display.insert(tk.END, f"{display_sender}:", "sender_tag")
            
            self.translation_display.insert(tk.END, "\t")

            # 3. Column 3: Message / Translation
            # If translation happened and is significantly different from original
            clean_original = original_msg.strip().lower()
            clean_translated = translated_msg.strip().lower()
            
            # Simple heuristic: If length differs significantly or chars changed
            if translated_msg and clean_translated != clean_original and len(clean_translated) > 1:
                self.translation_display.insert(tk.END, translated_msg + " (Translation)\n", "bold")
                
                # Display Original Line (indented to the 3rd column)
                self.translation_display.insert(tk.END, f"\t\t({original_msg})\n", "original_tag")
            else:
                self.translation_display.insert(tk.END, original_msg + "\n", "message_tag")
        
        # Auto-scroll to the end
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
        # We look for a colon or semicolon within the first 25 characters
        # Added support for misread colons as dots if they follow a likely name
        sender_match = re.search(r"^([^:;]{1,25})[:;](.*)", temp_line)
        if not sender_match:
            # Fallback: look for a space and a dot (common misread of ' :')
            sender_match = re.search(r"^([^:;]{1,25})\s\.(.*)", temp_line)

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
            self.set_hotkey_from_settings
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
        else:
            self.update_notification("Selection cancelled.")


# =====================================================
# HOTKEY
# =====================================================

    def set_hotkey_from_settings(self, new_hotkey):
        self.hotkey_str = new_hotkey
        self.config.set_hotkey(new_hotkey)

        self.keybinding_service.set_hotkey(new_hotkey)

        self.update_notification(f"Hotkey set: {new_hotkey}")


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
        set_hotkey_cb
    ):
        super().__init__(master)
        self.title("Settings")
        self.geometry("450x620")
        self.resizable(False, False)
        self.grab_set()

        self.notify = notify_cb
        self.apply_font = apply_font_cb
        self.set_theme = set_theme_cb
        self.config = config
        self.authorize = authorize_cb
        self.set_hotkey = set_hotkey_cb

        # Match theme background
        bg_color = "#313338" if current_theme == "Dark" else "#F2F3F5"
        self.configure(bg=bg_color)

        self.main = ttk.Frame(self, padding=20)
        self.main.pack(fill=tk.BOTH, expand=True)

        # Region
        self.select_region_cb = select_region_cb

        region_frame = ttk.LabelFrame(self.main, text="Chat Region", padding=10)
        region_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            region_frame,
            text="Select New Region",
            style="Accent.TButton",
            command=self._on_select_region_button_click
        ).pack(fill=tk.X, pady=5)

        # Hotkey
        key_frame = ttk.LabelFrame(self.main, text="Snapshot Hotkey", padding=10)
        key_frame.pack(fill=tk.X, pady=10)

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
        appearance_frame.pack(fill=tk.X, pady=10)

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

        # Google Cloud
        gcp_frame = ttk.LabelFrame(self.main, text="Google Cloud API", padding=10)
        gcp_frame.pack(fill=tk.X, pady=10)

        ttk.Label(gcp_frame, text="Project ID").pack(anchor="w")
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
