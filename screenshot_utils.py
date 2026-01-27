import tkinter as tk
from tkinter import Toplevel, Canvas
from PIL import ImageGrab, Image
import time
import os

class RegionSelector:
    def __init__(self, master, window_to_hide=None):
        self.master = master
        self.window_to_hide = window_to_hide if window_to_hide else master
        self.selection_window = Toplevel(master)
        self.selection_window.overrideredirect(True) # No window decorations
        self.selection_window.attributes('-alpha', 0.3) # Transparent overlay
        self.selection_window.attributes('-topmost', True) # Always on top
        self.selection_window.geometry(f"{self.master.winfo_screenwidth()}x{self.master.winfo_screenheight()}+0+0")

        self.canvas = Canvas(self.selection_window, cursor="cross", bg="grey")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.selected_region = None # (x, y, width, height)

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.current_rect:
            self.canvas.delete(self.current_rect)
        self.current_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)

    def on_mouse_drag(self, event):
        if self.start_x is not None:
            self.canvas.coords(self.current_rect, self.start_x, self.start_y, event.x, event.y)

    def on_button_release(self, event):
        end_x, end_y = event.x, event.y
        x1, y1, x2, y2 = min(self.start_x, end_x), min(self.start_y, end_y), \
                         max(self.start_x, end_x), max(self.start_y, end_y)
        
        self.selected_region = (x1, y1, x2 - x1, y2 - y1)
        self.selection_window.destroy()

    def get_region(self):
        self.window_to_hide.withdraw() # Hide the specified window
        self.selection_window.wait_window() # Wait for selection to complete
        self.window_to_hide.deiconify() # Show the specified window again
        return self.selected_region

class ScreenCapture:
    def capture_region(self, region):
        """
        Captures a specific region of the screen.
        :param region: A tuple (x, y, width, height) defining the region.
        :return: A PIL Image object of the captured region.
        """
        if not region:
            return None
        x, y, width, height = region
        # ImageGrab.grab() captures the screen
        # On Windows, it handles multiple monitors correctly relative to primary screen
        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        return screenshot

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Main App (Hidden during selection)")
    root.geometry("300x200")
    
    label = ttk.Label(root, text="Click to select region")
    label.pack(pady=20)

    selected_label = ttk.Label(root, text="Selected: None")
    selected_label.pack()

    def select_and_show():
        selector = RegionSelector(root)
        region = selector.get_region()
        if region:
            print(f"Selected region: {region}")
            selected_label.config(text=f"Selected: {region}")
            
            # Example: Save the captured image
            capturer = ScreenCapture()
            screenshot = capturer.capture_region(region)
            if screenshot:
                screenshot.save("debug_capture.png")
                print("Screenshot saved to debug_capture.png")
        else:
            print("No region selected.")
            selected_label.config(text="Selected: None (cancelled)")

    ttk.Button(root, text="Select Region", command=select_and_show).pack(pady=10)
    
    root.mainloop()
