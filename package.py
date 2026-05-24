import PyInstaller.__main__ as pyi
import os
import shutil

# --- Configuration ---
SCRIPT_NAME = "main.py"
APP_NAME = "Dota2ChatTranslator"
ICON_PATH = None # Optional: path to .ico file
ADD_DATA = []

# Add custom theme files
ADD_DATA.append((os.path.join(os.path.dirname(__file__), "theme"), "theme"))

# Add config files and assets
ADD_DATA.append((os.path.join(os.path.dirname(__file__), "chat_format.json"), "."))
ADD_DATA.append((os.path.join(os.path.dirname(__file__), "version.py"), "."))
ADD_DATA.append((os.path.join(os.path.dirname(__file__), "README.md"), "."))

# Add client_secret.json (use template if actual one is missing)
if os.path.exists("client_secret.json"):
    ADD_DATA.append((os.path.join(os.path.dirname(__file__), "client_secret.json"), "."))
else:
    ADD_DATA.append((os.path.join(os.path.dirname(__file__), "client_secret_template.json"), "."))
    # Note: Inno Setup or the app should handle renaming template to actual if needed

def build_app():
    # Clean up previous build artifacts
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists(f'{APP_NAME}.spec'):
        os.remove(f'{APP_NAME}.spec')

    print(f"Starting PyInstaller build for {APP_NAME}...")

    # Build the --add-data arguments
    add_data_args = []
    for src, dst in ADD_DATA:
        add_data_args.append(f"--add-data={src}{os.pathsep}{dst}")
    
    # PyInstaller options
    pyinstaller_args = [
        SCRIPT_NAME,
        "--name", APP_NAME,
        "--onedir", # Directory mode for faster startup
        "--windowed", # Suppresses the console window
        "--clean",
        "--noconfirm",
        # Important for PaddleOCR: hidden imports
        "--hidden-import=pynput.keyboard._win32",
        "--hidden-import=pynput.mouse._win32",
    ]

    if ICON_PATH:
        pyinstaller_args.extend(["--icon", ICON_PATH])

    pyinstaller_args.extend(add_data_args)

    # Run PyInstaller
    pyi.run(pyinstaller_args)

    print(f"PyInstaller build finished. Check 'dist/{APP_NAME}' folder.")

if __name__ == "__main__":
    build_app()
