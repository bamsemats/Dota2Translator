import tkinter as tk
from tkinter import ttk, font
import threading
import os

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
        self.root.geometry("420x520")
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

        self.create_widgets()
        self.apply_font_settings(self.current_font_family, self.current_font_size)
        self.set_theme(self.current_theme)

        self.authorize_google_cloud_startup()

        self.show_startup_status()


# =====================================================
# UI SETUP
# =====================================================

    def create_widgets(self):
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.notification_label = ttk.Label(
            self.main_frame,
            text="",
            wraplength=380,
            anchor="w"
        )
        self.notification_label.pack(fill=tk.X, pady=(0, 10))

        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(pady=(0, 10))

        ttk.Button(
            button_frame,
            text="Take Snapshot",
            command=self.take_snapshot
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Settings",
            command=self.open_settings
        ).pack(side=tk.LEFT, padx=5)

        self.translation_display = tk.Text(
            self.main_frame,
            height=15,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.translation_display.pack(fill=tk.BOTH, expand=True)


# =====================================================
# THEMES
# =====================================================

    def set_theme(self, theme_name):
        self.current_theme = theme_name
        self.config.set_theme(theme_name)

        style = ttk.Style(self.root)

        if theme_name == "Dark":
            style.theme_use("clam")

            self.translation_display.config(
                bg="#2b2b2b",
                fg="white",
                insertbackground="white"
            )
        else:
            style.theme_use("default")

            self.translation_display.config(
                bg="white",
                fg="black",
                insertbackground="black"
            )


# =====================================================
# FONTS
# =====================================================

    def apply_font_settings(self, family, size):
        self.current_font_family = family
        self.current_font_size = size

        new_font = font.Font(family=family, size=size)

        self.translation_display.config(font=new_font)

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

            extracted_lines = self.ocr_service.extract_text_from_image(screenshot)

            all_translated_lines = []

            for line in extracted_lines:
                text = line["text"]
                src_lang = line.get("language", "und")

                original, translated = self.translation_service.translate_text(text, src_lang)
                
                # Append a tuple (original, translated) for later formatting
                all_translated_lines.append((original, translated))

            self.root.after(0, lambda: self.display_translation(all_translated_lines))

        except Exception as e:
            self.safe_notify(f"Error: {e}")


    def display_translation(self, all_translated_lines):
        self.translation_display.config(state=tk.NORMAL)
        self.translation_display.delete("1.0", tk.END)
        
        formatted_output = []
        for original_text, translated_text in all_translated_lines:
            if original_text.strip() != translated_text.strip():
                formatted_output.append(f"{translated_text} ({original_text})")
            else:
                formatted_output.append(original_text) # If no translation, just show original
        
        self.translation_display.insert(tk.END, "\n".join(formatted_output))
        self.translation_display.config(state=tk.DISABLED)

        self.update_notification("Done.")


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
            self.update_.notification("Ready.")


    def on_closing(self):
        self.keybinding_service.stop_listener()
        self.root.destroy()


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
        self.geometry("520x550")
        self.resizable(False, False)
        self.grab_set()

        self.notify = notify_cb
        self.apply_font = apply_font_cb
        self.set_theme = set_theme_cb
        self.config = config
        self.authorize = authorize_cb
        self.set_hotkey = set_hotkey_cb

        self.main = ttk.Frame(self, padding=15) # Changed to self.main
        self.main.pack(fill=tk.BOTH, expand=True)

        # Region
        self.select_region_cb = select_region_cb # Store the callback

        ttk.LabelFrame(self.main, text="Chat Region", padding=10)\
            .pack(fill=tk.X, pady=8)

        ttk.Button(
            self.main,
            text="Select Region",
            command=self._on_select_region_button_click
        ).pack(pady=4)

        # Font
        font_frame = ttk.LabelFrame(self.main, text="Font", padding=10)
        font_frame.pack(fill=tk.X, pady=8)

        self.font_family = tk.StringVar(value=current_font)
        self.font_size = tk.IntVar(value=current_size)

        ttk.Combobox(
            font_frame,
            textvariable=self.font_family,
            values=sorted(font.families()),
            state="readonly"
        ).pack(fill=tk.X)

        ttk.Spinbox(
            font_frame,
            from_=8,
            to=36,
            textvariable=self.font_size,
            command=self.update_.font
        ).pack(fill=tk.X, pady=4)

        # Theme
        theme_frame = ttk.LabelFrame(self.main, text="Theme", padding=10)
        theme_frame.pack(fill=tk.X, pady=8)

        self.theme_var = tk.StringVar(value=current_theme)

        ttk.Combobox(
            theme_frame,
            textvariable=self.theme_var,
            values=["Light", "Dark"],
            state="readonly"
        ).pack(fill=tk.X)

        ttk.Button(
            theme_frame,
            text="Apply Theme",
            command=self.update_theme
        ).pack(pady=4)

        # Google
        gcp_frame = ttk.LabelFrame(self.main, text="Google Cloud", padding=10)
        gcp_frame.pack(fill=tk.X, pady=8)

        self.project_id = tk.StringVar(value=config.get_project_id())

        ttk.Entry(
            gcp_frame,
            textvariable=self.project_id
        ).pack(fill=tk.X)

        ttk.Button(
            gcp_frame,
            text="Save Project ID",
            command=self.save_project
        ).pack(pady=3)

        ttk.Button(
            gcp_frame,
            text="Authorize",
            command=self.authorize
        ).pack(pady=3)

        # Hotkey
        key_frame = ttk.LabelFrame(self.main, text="Hotkey", padding=10)
        key_frame.pack(fill=tk.X, pady=8)

        self.hotkey_var = tk.StringVar(value=current_hotkey)

        entry = ttk.Entry(
            key_frame,
            textvariable=self.hotkey_var
        )
        entry.pack(fill=tk.X)

        entry.bind("<FocusIn>", self.capture_hotkey)

        ttk.Button(
            key_frame,
            text="Save Hotkey",
            command=self.save_hotkey
        ).pack(pady=4)

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
        self.set_theme(self.theme_var.get())
        self.notify("Theme updated.")


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
