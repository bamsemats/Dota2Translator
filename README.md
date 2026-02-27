# Dota 2 Chat Translator

This application captures a specified region of your screen, performs Optical Character Recognition (OCR) on it, and translates any recognized text into English. It is designed to translate in-game chat from Dota 2 in real-time.

This version uses a hybrid approach:
- **Local OCR:** Text recognition is handled locally using the Tesseract OCR engine. This is fast, free, and has no usage limits.
- **Cloud Translation:** The recognized text is translated using the Google Cloud Translation API to ensure high-quality translations.

## Installation

There are three main steps to get the application running: installing Tesseract, setting up the Python environment, and configuring Google Cloud.

### 1. Install Tesseract OCR

This application depends on Tesseract OCR engine. You must install it on your system.

- **Platform:** Windows
- **Installer:** You can find the official Tesseract installers from the University of Mannheim.
  - **Link:** [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
- **Instructions:**
  1. Download and run the installer for your system (e.g., `tesseract-ocr-w64-setup-v5.x.x.exe`).
  2. **Important:** During installation, make sure to select the language packs for the languages you expect to encounter. At a minimum, for Dota 2 it is recommended to install:
     - English (`eng`)
     - Russian (`rus`)
     - Spanish (`spa`)
     - Portuguese (`por`)
     - Simplified Chinese (`chi_sim`)
  3. Note the installation path. The default is usually `C:\Program Files\Tesseract-OCR`. If you install it here, the application should find it automatically. If you choose a different path, you may need to edit `ocr_service.py` and set the path manually at the top of the file.

### 2. Set Up Python Environment

Clone this repository and install the required Python packages.

```bash
# Clone the repository
git clone <repository-url>
cd Dota2ChatTranslater

# It is recommended to use a virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Google Cloud for Translation

Since translation is handled by Google Cloud, you still need a Google Cloud Project to use the Translation API.

1. **Create a Google Cloud Project:** Follow the instructions on the [Google Cloud Console](https://console.cloud.google.com/).
2. **Enable the "Cloud Translation API":** In your project, go to the API Library and enable it.
3. **Create Credentials:**
   - Go to "Credentials" in the "APIs & Services" section.
   - Create a new credential of type "OAuth 2.0 Client ID".
   - Select "Desktop app" as the application type.
   - Download the JSON file containing your credentials.
4. **Place Credentials File:** Rename the downloaded file to `client_secret.json` and place it in the root directory of this project.
5. **Set Project ID:**
   - Run the application.
   - Go to `Settings -> Google Cloud`.
   - Paste your Google Cloud **Project ID** into the entry box and click "Save Project ID".

**SECURITY WARNING:** The `client_secret.json` file contains credentials for your Google Cloud Project. **NEVER commit this file to a public version control repository (like GitHub).** Always ensure it's listed in your `.gitignore` to prevent accidental exposure.

## How to Run

Execute the `run.bat` script or run the main python file:

```bash
python main.py
```

## Usage

1. **Authorize Google Cloud:** On first run (or after saving a new Project ID), click the "Authorize" button in the Settings menu. This will open a browser window asking you to log in with your Google account and grant permission.
2. **Select Chat Region:**
   - In the app's settings, click "Select Region".
   - Your screen will dim. Click and drag to draw a box around the area where chat messages appear in Dota 2.
3. **Translate:**
   - Once the region is set and Google Cloud is authorized, you can press your configured hotkey (default is `<f8>`) to capture the chat region.
   - The application will process the image, and any translated text will appear in the main window.
4. **Settings:** You can change the hotkey, theme, and text font size from the Settings menu.
