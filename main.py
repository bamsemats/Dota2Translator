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
        self.root.geometry("420x720") # Adjusted geometry to accommodate the image panel
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.config = AppConfig()

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
            highlightthickness=0
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
        self.preview_container = ttk.Frame(self.main_frame, height=280)
        self.preview_container.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        self.preview_container.pack_propagate(False)

        self.screenshot_frame = ttk.LabelFrame(self.preview_container, text="Preview", padding=5)
        self.screenshot_frame.pack(fill=tk.BOTH, expand=True)

        self.screenshot_label = ttk.Label(self.screenshot_frame, text="No capture", anchor="center")
        self.screenshot_label.pack(fill=tk.BOTH, expand=True)


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

            extracted_lines = self.ocr_service.extract_text_from_image(screenshot)

            processed_messages = []

            for line in extracted_lines:
                text = line["text"]
                parsed = self.parse_chat_line(text)
                
                # --- Multi-line Joining Logic ---
                # If this line has no tag and no sender, it might be a continuation of the previous message
                if not parsed["tag"] and not parsed["sender"] and processed_messages:
                    prev_msg = processed_messages[-1]
                    # Only join if the previous message actually had a sender (i.e. it wasn't just noise or a system msg)
                    if prev_msg["sender"] or prev_msg["tag"]:
                        prev_msg["message"] += " " + parsed["message"]
                        # We'll re-translate the combined message later or just append translation
                        # For simplicity, let's just append for now, or re-translate below
                        continue 

                processed_messages.append(parsed)

            # Translation pass on the final structured messages
            for msg_obj in processed_messages:
                if msg_obj["message"]:
                    original_msg = msg_obj["message"]
                    # We don't know the exact lang for joined lines, use "und"
                    _, translated_msg = self.translation_service.translate_text(original_msg, "und")
                    msg_obj["translated_message"] = translated_msg
                else:
                    msg_obj["translated_message"] = ""

            self.root.after(0, lambda: self.display_translation(processed_messages))
            self.root.after(0, self.display_last_screenshot) # Call the method to display the screenshot

        except Exception as e:
            self.safe_notify(f"Error: {e}")


    def display_translation(self, processed_messages):
        self.translation_display.config(state=tk.NORMAL)
        
        # Add a newline only if there's already content, to separate new entries
        if self.translation_display.index(tk.END) != "1.0":
            self.translation_display.insert(tk.END, "\n\n") # Double newline for better separation
        
        for msg_obj in processed_messages:
            tag = msg_obj["tag"]
            sender = msg_obj["sender"]
            original_msg = msg_obj["message"]
            translated_msg = msg_obj["translated_message"]

            # 1. Display Translated/Main Line
            if tag:
                self.translation_display.insert(tk.END, f"[{tag}] ", "allies_tag")
            if sender:
                self.translation_display.insert(tk.END, f"{sender}: ", "sender_tag")
            
            # If translation happened and is different from original
            if translated_msg and translated_msg.strip().lower() != original_msg.strip().lower():
                self.translation_display.insert(tk.END, translated_msg + " (Translation)\n", "bold")
                
                # 2. Display Original Line (indented and dimmed)
                indent = "  "
                if tag: indent += " " * (len(tag) + 3)
                if sender: indent += " " * (len(sender) + 2)
                
                self.translation_display.insert(tk.END, f"{indent}({original_msg})\n", "original_tag")
            else:
                self.translation_display.insert(tk.END, original_msg + "\n", "message_tag")
        
        # Auto-scroll to the end of the text widget
        self.translation_display.see(tk.END)
        self.translation_display.config(state=tk.DISABLED)

        self.update_notification("Done.")


    def display_last_screenshot(self):
        if self.last_screenshot_pil:
            self.root.update_idletasks()
            
            # Use the preview container's size
            max_width = self.preview_container.winfo_width()
            max_height = self.preview_container.winfo_height()

            if max_width <= 1 or max_height <= 1:
                max_width = 400
                max_height = 150 # Fixed height fallback
            
            img_width, img_height = self.last_screenshot_pil.size
            
            # Subtract padding for the LabelFrame
            max_width -= 20
            max_height -= 30
            
            ratio = min(max_width / img_width, max_height / img_height)
            new_width = max(1, int(img_width * ratio))
            new_height = max(1, int(img_height * ratio))
            
            resized_image = self.last_screenshot_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
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

        # Improved Tag Detection: Allow noise before tag, and match more tag types
        # Matches [Allies], (Allies), [All], [Team], etc.
        tag_pattern = r"(?:.*?)([\[\(](Allies|Team|All)[\]\)])\s*(.*)"
        tag_match = re.search(tag_pattern, temp_line, re.IGNORECASE)
        
        if tag_match:
            parsed["tag"] = tag_match.group(2)
            temp_line = tag_match.group(3).strip()

        # Improved Sender Detection:
        # Look for a colon or semicolon as a separator
        if ":" in temp_line or ";" in temp_line:
            split_char = ":" if ":" in temp_line else ";"
            parts = temp_line.split(split_char, 1)
            potential_sender = parts[0].strip()
            message_part = parts[1].strip()

            # Sender validation: allow 1-30 chars, must have at least one alphanumeric
            if 1 <= len(potential_sender) <= 30 and re.search(r'\w', potential_sender):
                parsed["sender"] = potential_sender
                # Clean up the message part (remove leading/trailing artifacts)
                parsed["message"] = message_part.lstrip(":;,. ").strip()
            else:
                parsed["message"] = temp_line.lstrip(":;,. ").strip()
        else:
            parsed["message"] = temp_line.lstrip(":;,. ").strip()
        
        # Final cleanup for common OCR garbage at start of message
        # e.g. "© Hello" or "» Hi"
        parsed["message"] = re.sub(r"^[^\w\s\[\(]+", "", parsed["message"]).strip()
        
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
