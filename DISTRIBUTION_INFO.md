### Security Audit Conclusion for GitHub Upload ###

**1. Sensitive Files:**
- `python_ocr/gcp_credentials.json` is the only file identified as containing sensitive Google Cloud service account credentials. This file *must not* be committed to your GitHub repository.

**2. Hardcoded Secrets:**
- No hardcoded API keys, tokens, or other sensitive credentials were found directly embedded in your Java (`.java`) or Python (`.py`) source code.

**3. User Credentials Handling:**
- The application is designed to prompt users for their own `gcp_credentials.json` file. These credentials are used by both the JavaFX application and passed to the Python OCR server via an environment variable (`GOOGLE_APPLICATION_CREDENTIALS`). This ensures that other users will *not* be connected to your Google account or billed for your usage.

**Recommendation before uploading to GitHub:**
- **Verify your `.gitignore` file.** Ensure it explicitly includes `python_ocr/gcp_credentials.json`. A typical `.gitignore` for this project should look something like this:
```
# Maven
target/
pom.xml.tag
pom.xml.versionsBackup
pom.xml.next
release.properties
release-versions.properties
.repository/
.mvn/timing.properties
# VSCode
.vscode/
# IntelliJ
.idea/
*.iml
*.ipr
*.iws
# OS
.DS_Store
Thumbs.db
# Python
__pycache__/
*.pyc
.venv/
venv/
# PyInstaller
python_ocr/build/
python_ocr/dist/
*.spec
# Google Cloud Credentials
python_ocr/gcp_credentials.json
```
- Run `git status` after checking your `.gitignore` to confirm that `gcp_credentials.json` (and other generated files like `target/`, `.idea/`, etc.) are listed as ignored and *not* staged for commit.

### How to make the program into an executable file for sharing ###

To create a single, user-friendly executable for your friends, the best approach is to package the JavaFX application as a native installer and bundle the Python OCR server as a standalone executable.

**Steps:**

**1. Prepare Python OCR Server as an Executable (using PyInstaller):**
   a.  **Install PyInstaller:** If you haven't already, install PyInstaller in your Python environment:
       `pip install pyinstaller`
   b.  **Create Python Executable:** Navigate to your `python_ocr` directory in the command prompt and run:
       `pyinstaller --onefile app.py`
       This command will create a `dist/` folder inside `python_ocr/`. Inside `python_ocr/dist/`, you'll find `app.exe` (for Windows). This single executable contains your Python Flask app and all its dependencies.

**2. Modify Java `MainApp.java` to launch the Python Executable:**
   You need to change the `ProcessBuilder` in `MainApp.java` to point to this new `app.exe`.
   *Old Line (around line 77 in `MainApp.java`):*
     `ProcessBuilder pb = new ProcessBuilder("python", "app.py");`
   *New Line:*
     `ProcessBuilder pb = new ProcessBuilder("python_ocr/dist/app.exe");`
   *(Note: The exact path might vary depending on where you decide to bundle the `python_ocr/dist` folder relative to your Java app's final structure. For now, this relative path assumes `python_ocr/dist` is next to your Java app's root.)*

**3. Package JavaFX Application as a Native Installer (using `javafx-maven-plugin` and `jpackage`):**
   a.  **Ensure `pom.xml` configuration:** Your `pom.xml` should already have the `org.openjfx:javafx-maven-plugin`. Make sure it's configured to use the `jpackage` goal. You might need to add `jpackage` specific configurations if not already present.
   b.  **Create Installer:** In your project's root directory (where `pom.xml` is), run:
       `mvn clean install javafx:jlink javafx:jpackage`
       This command will:
       - Clean and compile your project.
       - Create a custom Java runtime image (`jlink`).
       - Package your application into a native installer (e.g., an `.exe` file for Windows) using `jpackage`. This installer will include the necessary Java Runtime Environment (JRE) and your JavaFX application.
       - The installer will be located in the `target/jpackage` directory.

**4. Combine and Distribute:**
   a.  **Integrate Python Executable:** After `mvn javafx:jpackage` creates your JavaFX installer, you will need to manually copy the `python_ocr/dist/app.exe` (or the entire `python_ocr/dist` folder) into the appropriate location within the JavaFX installer's structure. This usually means placing it alongside the main JavaFX application's executable. The exact location depends on how `jpackage` structures the installed application.
   b.  **Test:** Install the created package and test it to ensure both the JavaFX app and the bundled Python OCR server launch correctly and communicate.
   c.  **Share:** You can then share this single installer file (e.g., `.exe`) with your friends. They won't need to install Java or Python separately.

**Double check that everything is as it should (meaning they wont get connected to my google account in any way by using this application):**

Yes, we have designed the application specifically to prevent this:
-   **User-Provided Credentials:** Both the JavaFX front-end and the Python back-end are configured to use credentials explicitly provided by the *user* through the credentials selection dialog.
-   **No Hardcoded Credentials:** Your `gcp_credentials.json` (or any other sensitive information) is not hardcoded into the application's source code.
-   **`.gitignore` Enforcement:** By correctly configuring your `.gitignore` and ensuring `python_ocr/gcp_credentials.json` is not committed, your personal credentials will not be shared with the public repository.

Your friends will be responsible for creating their own Google Cloud Project, enabling the necessary APIs (Vision API and Translation API), and generating their own service account JSON key file. The application will then prompt them to select this file, ensuring their usage is tied to *their* Google account and not yours. They will also need to monitor their own usage against Google's free tiers, as instructed by the application's safeguards.
