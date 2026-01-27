from pynput import keyboard
import threading
import time

class KeybindingService:
    def __init__(self, callback_function, initial_hotkey_str="<f8>"):
        self.callback_function = callback_function
        self.hotkey_str = initial_hotkey_str
        self.listener = None
        self.stop_event = threading.Event()
        self.hotkey_registered = False
        self.current_keys = set() # To keep track of currently pressed keys

    def set_hotkey(self, hotkey_str):
        self.stop_listener() # Stop existing listener if any
        self.hotkey_str = hotkey_str
        self.start_listener() # Start new listener with new hotkey

    def _on_press(self, key):
        try:
            self.current_keys.add(key.char) # For regular keys
        except AttributeError:
            self.current_keys.add(key) # For special keys (e.g., Key.f8, Key.ctrl_l)

        # Check if the current combination of pressed keys matches the hotkey
        # Example hotkey_str: "<ctrl>+s" -> hotkey_parts = ["ctrl", "s"]
        # pressed_key_names: {<Key.ctrl_l>, 's'} -> {Key.ctrl_l, 's'}
        
        # Convert hotkey string to a comparable format (e.g., {'ctrl', 's'})
        hotkey_parts_set = set(self.hotkey_str.replace('<', '').replace('>', '').split('+'))
        
        # Convert pressed keys to a comparable format (e.g., {'ctrl_l', 's'})
        # Need to handle Key.ctrl_l, Key.ctrl_r etc. as 'ctrl'
        pressed_key_names_normalized = set()
        for k in self.current_keys:
            if isinstance(k, keyboard.Key):
                if k == keyboard.Key.ctrl_l or k == keyboard.Key.ctrl_r:
                    pressed_key_names_normalized.add('ctrl')
                elif k == keyboard.Key.alt_l or k == keyboard.Key.alt_r:
                    pressed_key_names_normalized.add('alt')
                elif k == keyboard.Key.shift_l or k == keyboard.Key.shift_r:
                    pressed_key_names_normalized.add('shift')
                elif k == keyboard.Key.cmd_l or k == keyboard.Key.cmd_r:
                    pressed_key_names_normalized.add('cmd') # Or 'super'
                else:
                    pressed_key_names_normalized.add(str(k).replace("Key.", ""))
            else:
                pressed_key_names_normalized.add(str(k))
        
        # If all parts of the hotkey are currently pressed
        if hotkey_parts_set.issubset(pressed_key_names_normalized):
            if not self.stop_event.is_set():
                print(f"Hotkey '{self.hotkey_str}' pressed. Executing callback.")
                self.callback_function()
                # Add a small delay or flag to prevent rapid re-triggering if key is held
                # A better approach might be to activate only on *release* of the last hotkey part
                # For simplicity, we'll allow single activation per press cycle here.

    def _on_release(self, key):
        try:
            if key.char in self.current_keys:
                self.current_keys.remove(key.char)
        except AttributeError:
            if key in self.current_keys:
                self.current_keys.remove(key)
        
        # No need to stop listener here unless it's a dedicated exit key

    def start_listener(self):
        if self.listener is not None and self.listener.running:
            return # Listener already running

        try:
            self.stop_event.clear()
            self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self.listener.start()
            self.hotkey_registered = True
            print(f"Keybinding service started for hotkey: {self.hotkey_str}")
        except Exception as e:
            print(f"Error starting keybinding listener: {e}")
            self.hotkey_registered = False

    def stop_listener(self):
        if self.listener is not None and self.listener.running:
            self.stop_event.set() # Signal that processing should halt
            self.listener.stop()
            self.listener.join() # Wait for the thread to finish
            self.listener = None
            self.current_keys.clear() # Clear any remaining pressed keys
            self.hotkey_registered = False
            print("Keybinding service stopped.")

# Example usage (for testing this module independently)
if __name__ == "__main__":
    def test_callback():
        print("Test callback executed!")

    kb_service = KeybindingService(test_callback, "<ctrl>+s") # Example hotkey
    kb_service.start_listener()

    print("Press Ctrl+S to trigger the callback. Press Ctrl+C to exit.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting example.")
        kb_service.stop_listener()

    # Test changing hotkey
    print("\nChanging hotkey to <alt>+t")
    kb_service.set_hotkey("<alt>+t")
    print("Press Alt+T to trigger the callback. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting example.")
        kb_service.stop_listener()
