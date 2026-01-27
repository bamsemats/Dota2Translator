import PyInstaller.__main__ as pyi
import os
import shutil

# --- Configuration ---
SCRIPT_NAME = "main.py"
APP_NAME = "Dota2ChatTranslator"
ICON_PATH = None # Optional: path to .ico file, e.g., "icon.ico"
ADD_DATA = [] # List of (source, destination_in_bundle) tuples

# Add custom theme files
# You need to download forest-dark.tcl and forest-light.tcl and place them in your project root
ADD_DATA.append((os.path.join(os.path.dirname(__file__), "forest-dark.tcl"), "."))
ADD_DATA.append((os.path.join(os.path.dirname(__file__), "forest-light.tcl"), "."))

# Add config.ini (if it exists, for initial setup)
if os.path.exists("config.ini"):
    ADD_DATA.append((os.path.join(os.path.dirname(__file__), "config.ini"), "."))
else:
    print("Warning: config.ini not found. It will be created on first run.")

# Add token storage directory (if it exists)
if os.path.exists("tokens"):
    ADD_DATA.append((os.path.join(os.path.dirname(__file__), "tokens"), "tokens"))

# Add client_secret.json (if it exists)
if os.path.exists("client_secret.json"):
    ADD_DATA.append((os.path.join(os.path.dirname(__file__), "client_secret.json"), "."))
else:
    print("Warning: client_secret.json not found. OAuth will not work without it.")


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
        "--onefile", # Creates a single executable file
        "--windowed", # Suppresses the console window
        "--clean", # Clean PyInstaller cache and remove temporary files
        "--noconfirm", # Overwrite output directory without asking
    ]

    # Add icon if provided
    if ICON_PATH:
        pyinstaller_args.extend(["--icon", ICON_PATH])

    # Add --add-data arguments
    pyinstaller_args.extend(add_data_args)

    # Run PyInstaller
    pyi.run(pyinstaller_args)

    print(f"PyInstaller build finished. Check the 'dist' folder for {APP_NAME}.exe")

if __name__ == "__main__":
    build_app()
