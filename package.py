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
ADD_DATA.append((os.path.join(os.path.dirname(__file__), "client_secret_template.json"), "."))

# Only add client_secret.json if it exists locally
if os.path.exists("client_secret.json"):
    ADD_DATA.append((os.path.join(os.path.dirname(__file__), "client_secret.json"), "."))

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
        "--onedir", 
        "--windowed", 
        "--clean",
        "--noconfirm",
        # Minimal hidden imports
        "--hidden-import=pynput.keyboard._win32",
        "--hidden-import=pynput.mouse._win32",
        "--collect-all", "chardet", # Still useful for requests
    ]

    if ICON_PATH:
        pyinstaller_args.extend(["--icon", ICON_PATH])

    pyinstaller_args.extend(add_data_args)

    # Run PyInstaller
    pyi.run(pyinstaller_args)

    print(f"PyInstaller build finished. Check 'dist/{APP_NAME}' folder.")

if __name__ == "__main__":
    build_app()
