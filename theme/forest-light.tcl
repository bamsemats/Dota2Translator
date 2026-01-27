# This file defines the 'light' theme for Tkinter's ttk widgets.
# You can customize colors and styles here.
# For a full theme, this would contain many more style definitions.

# Example: setting a light background for the root window and general ttk elements
# theme create light
# theme use light

# You might set specific widget styles here, e.g.:
# ttk::style configure TButton -background #eee -foreground black
# ttk::style configure TFrame -background #fff
# ttk::style configure TNotebook -background #ddd
# ttk::style map TButton -background [list disabled #eee !disabled #ccc]

# Using an external theme like 'forest' is generally more robust
# This file should contain the actual forest-light theme definitions if not already loaded

# For demonstration, a minimal example of changing colors:
# ttk::style theme create "light" parent "alt"
# ttk::style configure . -background "#f0f0f0"
# ttk::style configure TFrame -background "#f0f0f0"
# ttk::style configure TButton -background "#dddddd" -foreground "black"
# ttk::style configure TLabel -background "#f0f0f0" -foreground "black"
# ttk::style configure TText -background "#ffffff" -foreground "black"
# ttk::style configure TCombobox -fieldbackground "#ffffff" -background "#dddddd" -foreground "black"
# ttk::style configure TSpinbox -fieldbackground "#ffffff" -background "#dddddd" -foreground "black"
