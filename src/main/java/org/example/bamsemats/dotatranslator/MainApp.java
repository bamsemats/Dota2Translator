package org.example.bamsemats.dotatranslator;

import javafx.application.Application;
import javafx.application.Platform;
import javafx.fxml.FXMLLoader;
import javafx.geometry.Insets;
import javafx.scene.Scene;
import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.layout.BorderPane;
import javafx.scene.layout.VBox;
import javafx.scene.shape.Rectangle;
import javafx.stage.FileChooser;
import javafx.stage.Modality;
import javafx.stage.Stage;
import javafx.stage.StageStyle;

import java.io.File;
import java.io.IOException;
import java.util.concurrent.TimeUnit;
import java.util.prefs.Preferences;
import java.security.GeneralSecurityException;
import java.nio.file.Path;
import java.nio.file.Paths;

import com.github.kwhat.jnativehook.keyboard.NativeKeyEvent;
import com.google.api.client.auth.oauth2.Credential;
import com.google.auth.oauth2.AccessToken;
import java.util.function.Consumer;
import java.util.Date;
import javafx.scene.control.TextInputDialog;
import javafx.scene.layout.VBox;

public class MainApp extends Application {

    private ScreenCaptureService captureService;
    private MainViewController mainViewController;
    private TranslationService translationService;
    private Process pythonProcess;
    private Stage primaryStage;
    private java.awt.Rectangle chatRegion;
    private KeybindService keybindService;

    // OAuth related fields
    private GoogleOAuthService oAuthService;
    private Credential userCredential;
    private String googleCloudProjectId;

    private static final String PREF_REGION_X = "chatRegionX";
    private static final String PREF_REGION_Y = "chatRegionY";
    private static final String PREF_REGION_WIDTH = "chatRegionWidth";
    private static final String PREF_REGION_HEIGHT = "chatRegionHeight";
    private static final String PREF_SNAPSHOT_KEY = "snapshotKey";
    private static final String PREF_FONT_FAMILY = "fontFamily";
    private static final String PREF_FONT_SIZE = "fontSize";
    private static final String PREF_THEME = "theme";
    private static final String PREF_GOOGLE_CLOUD_PROJECT_ID = "googleCloudProjectId";


    public static void main(String[] args) {
        launch(args);
    }

    @Override
    public void start(Stage primaryStage) throws IOException {
        this.primaryStage = primaryStage;
        primaryStage.setTitle("Dota 2 Chat Translator");
        // Set a dummy scene initially to prevent NullPointerException when dialogs try to initOwner
        // This scene will be replaced later with the actual MainView scene.
        primaryStage.setScene(new Scene(new VBox(), 1, 1));
        // Removed primaryStage.setOpacity(0.0); // Make it invisible

        Preferences prefs = Preferences.userNodeForPackage(MainApp.class);

        try {
            oAuthService = new GoogleOAuthService();
            // Attempt to get stored credentials first, or authorize if none exist/expired
            userCredential = oAuthService.authorize();

            if (userCredential == null) {
                showAlert("Authentication Error", "Failed to authorize with Google Cloud. Exiting application.");
                Platform.exit();
                return;
            }

            // Get Project ID from preferences or prompt user
            googleCloudProjectId = prefs.get(PREF_GOOGLE_CLOUD_PROJECT_ID, null);
            if (googleCloudProjectId == null || googleCloudProjectId.isEmpty()) {
                googleCloudProjectId = showProjectIdInputDialog(primaryStage);
                if (googleCloudProjectId == null || googleCloudProjectId.isEmpty()) {
                    showAlert("Configuration Error", "Google Cloud Project ID not provided. Exiting application.");
                    Platform.exit();
                    return;
                }
                prefs.put(PREF_GOOGLE_CLOUD_PROJECT_ID, googleCloudProjectId);
            }

        } catch (GeneralSecurityException | IOException e) {
            System.err.println("Error during Google Cloud OAuth: " + e.getMessage());
            showAlert("Authentication Error", "Failed to authorize with Google Cloud. Check console for details.");
            Platform.exit();
            return;
        }

        startPythonOcrServer();
        loadChatRegion(prefs);

        FXMLLoader loader = new FXMLLoader(getClass().getResource("/MainView.fxml"));
        BorderPane root = loader.load();
        mainViewController = loader.getController();

        mainViewController.setSettingsCallback(this::openSettingsWindow);
        mainViewController.setSnapshotCallback(this::performOcrAction);

        // Debugging userCredential contents
        System.out.println("DEBUG MainApp: userCredential.getAccessToken(): " + userCredential.getAccessToken());
        System.out.println("DEBUG MainApp: userCredential.getExpirationTimeMilliseconds(): " + userCredential.getExpirationTimeMilliseconds());
        System.out.println("DEBUG MainApp: OAuth Client ID: " + oAuthService.getClientId());
        System.out.println("DEBUG MainApp: OAuth Client Secret: [REDACTED]"); // Don't print sensitive info

        // Pass Credential, ProjectId, Client ID, and Client Secret to services
        String oauthClientId = oAuthService.getClientId();
        String oauthClientSecret = oAuthService.getClientSecret();

        OcrService ocrService = new OcrService(false, mainViewController, userCredential, googleCloudProjectId, oauthClientId, oauthClientSecret);
        translationService = new TranslationService(googleCloudProjectId, userCredential, oauthClientId, oauthClientSecret, mainViewController);
        captureService = new ScreenCaptureService(chatRegion, ocrService, mainViewController, translationService);

        int snapshotKey = prefs.getInt(PREF_SNAPSHOT_KEY, NativeKeyEvent.VC_F8);
        keybindService = new KeybindService(this::performOcrAction, snapshotKey);
        keybindService.register();

        // Load font settings
        String fontFamily = prefs.get(PREF_FONT_FAMILY, "Segoe UI");
        double fontSize = prefs.getDouble(PREF_FONT_SIZE, 14.0);
        mainViewController.applyFontSettings(fontFamily, fontSize);

        // Load theme settings
        String theme = prefs.get(PREF_THEME, "Dark");
        setTheme(theme); // Apply theme to the main scene

        if (chatRegion == null) {
            mainViewController.setNotification("No chat region selected. Please select one in the settings.");
        }

        primaryStage.setScene(new Scene(root));
        primaryStage.show();
    }

    private String showProjectIdInputDialog(Stage ownerStage) {
        TextInputDialog dialog = new TextInputDialog(Preferences.userNodeForPackage(MainApp.class).get(PREF_GOOGLE_CLOUD_PROJECT_ID, ""));
        dialog.initOwner(ownerStage);
        dialog.setTitle("Google Cloud Project ID");
        dialog.setHeaderText("Please enter your Google Cloud Project ID.");
        dialog.setContentText("You can find this in your Google Cloud Console overview page (e.g., my-gcp-project-12345).");

        java.util.Optional<String> result = dialog.showAndWait();

        return result.orElse(null);
    }

    private void openSettingsWindow() {
        try {
            FXMLLoader loader = new FXMLLoader(getClass().getResource("/SettingsView.fxml"));
            VBox settingsRoot = loader.load();
            SettingsViewController controller = loader.getController();
            controller.setSelectRegionCallback(this::selectChatRegion);

            int currentKey = Preferences.userNodeForPackage(MainApp.class).getInt(PREF_SNAPSHOT_KEY, NativeKeyEvent.VC_F8);
            controller.setSnapshotKey(currentKey);
            controller.setSetSnapshotKeyCallback(this::setSnapshotKey);

            // Pass current font settings to the controller
            Preferences prefs = Preferences.userNodeForPackage(MainApp.class);
            String currentFontFamily = prefs.get(PREF_FONT_FAMILY, "Segoe UI");
            double currentFontSize = prefs.getDouble(PREF_FONT_SIZE, 14.0);
            controller.setCurrentFont(currentFontFamily, currentFontSize);
            controller.setFontChangeCallback(this::setFontSettings);

            // Pass current theme settings to the controller
            String currentTheme = prefs.get(PREF_THEME, "Dark");
            controller.setCurrentTheme(currentTheme);
            controller.setThemeChangeCallback(this::setTheme);


            Stage settingsStage = new Stage();
            settingsStage.setTitle("Settings");
            settingsStage.initModality(Modality.APPLICATION_MODAL);
            settingsStage.initOwner(primaryStage);
            settingsStage.setScene(new Scene(settingsRoot));
            settingsStage.showAndWait();
        } catch (IOException e) {
            e.printStackTrace();
            showAlert("Error", "Could not open settings window.");
        }
    }

    public void setSnapshotKey(int keyCode) {
        if (keybindService != null) {
            keybindService.setSnapshotKey(keyCode);
        }
        Preferences prefs = Preferences.userNodeForPackage(MainApp.class);
        prefs.putInt(PREF_SNAPSHOT_KEY, keyCode);
    }

    public void setFontSettings(String fontFamily, double fontSize) {
        if (mainViewController != null) {
            mainViewController.applyFontSettings(fontFamily, fontSize);
        }
        Preferences prefs = Preferences.userNodeForPackage(MainApp.class);
        prefs.put(PREF_FONT_FAMILY, fontFamily);
        prefs.putDouble(PREF_FONT_SIZE, fontSize);
    }

    public void setTheme(String themeName) {
        Preferences prefs = Preferences.userNodeForPackage(MainApp.class);
        prefs.put(PREF_THEME, themeName);

        if (primaryStage.getScene() != null) {
            primaryStage.getScene().getStylesheets().clear();
            String cssPath = switch (themeName) {
                case "Light" -> "/light_theme.css";
                case "Dark" -> "/dark_theme.css";
                default -> "/dark_theme.css"; // Default to dark
            };
            primaryStage.getScene().getStylesheets().add(getClass().getResource(cssPath).toExternalForm());
        }
    }

    private void selectChatRegion() {
        Platform.runLater(() -> {
            primaryStage.hide();
            try {
                // Use a temporary, transparent stage for region selection
                Stage selectionStage = new Stage(StageStyle.TRANSPARENT);
                selectionStage.setOpacity(0.01);
                selectionStage.show();

                Alert alert = new Alert(AlertType.INFORMATION);
                alert.setTitle("Dota 2 Chat Translator");
                alert.setHeaderText("Select Chat Region");
                alert.setContentText("Please select the in-game chat window region on your screen. Drag to draw a rectangle over the chat.");
                alert.showAndWait();

                Rectangle fxRect = new RegionSelector().selectRegion(selectionStage);
                this.chatRegion = RegionSelector.toAwt(fxRect);
                System.out.println("Selected chat region: " + this.chatRegion);
                captureService.setChatRegion(this.chatRegion);
                saveChatRegion(Preferences.userNodeForPackage(MainApp.class));
                mainViewController.setNotification("Chat region selected.");
                selectionStage.close();
            } finally {
                primaryStage.show();
            }
        });
    }

    private void performOcrAction() {
        if (chatRegion == null) {
            mainViewController.setNotification("Cannot take snapshot: No chat region selected.");
            return;
        }
        System.out.println("DEBUG MainApp: performOcrAction entered.");
        if (captureService != null) {
            System.out.println("DEBUG MainApp: captureService is not null, calling captureAndProcess().");
            try {
                captureService.captureAndProcess();
            } catch (IOException e) {
                System.err.println("Error during on-demand OCR: " + e.getMessage());
                Platform.runLater(() -> mainViewController.addMessage("Error performing OCR: " + e.getMessage()));
            }
        } else {
            System.out.println("DEBUG MainApp: captureService is NULL, cannot perform OCR.");
            Platform.runLater(() -> mainViewController.addMessage("Error: Capture service not initialized."));
        }
    }

    private void startPythonOcrServer() {
        try {
            // Aggressively kill any existing app.exe processes before starting a new one
            // This prevents multiple instances and resolves file-lock issues during PyInstaller rebuilds.
            try {
                System.out.println("Attempting to kill existing app.exe processes.");
                Process killProcess = Runtime.getRuntime().exec("taskkill /F /IM app.exe");
                killProcess.waitFor(5, TimeUnit.SECONDS); // Give it some time to terminate
                killProcess.destroy(); // Ensure the kill process itself is terminated
            } catch (IOException | InterruptedException e) {
                System.err.println("Error attempting to kill existing app.exe: " + e.getMessage());
                // Continue despite the error, as the process might not have been running.
            }

            // Get the directory where the Java application is running from.
            // In a packaged app, jpackage sets "app.dir" system property to the installation directory.
            String appRootPath = System.getProperty("app.dir", System.getProperty("user.dir"));
            Path appRoot = Paths.get(appRootPath);

            Path pythonOcrDistDir = appRoot.resolve("python_ocr").resolve("dist");
            Path pythonOcrExePath = pythonOcrDistDir.resolve("app.exe");
            Path pythonOcrDir = appRoot.resolve("python_ocr");

            // Check if app.exe exists before trying to run it
            if (!pythonOcrExePath.toFile().exists()) {
                showAlert("Python Server Error", "Python OCR executable not found at: " + pythonOcrExePath.toString() + "\n(Expected to be bundled in " + appRootPath + "/python_ocr/dist)");
                Platform.exit();
                return;
            }

            File pythonStdoutFile = File.createTempFile("python_stdout_", ".log");
            File pythonStderrFile = File.createTempFile("python_stderr_", ".log");
            pythonStdoutFile.deleteOnExit();
            pythonStderrFile.deleteOnExit();

            ProcessBuilder pb = new ProcessBuilder(pythonOcrExePath.toString());
            pb.directory(pythonOcrDir.toFile());
            // No longer setting GOOGLE_APPLICATION_CREDENTIALS environment variable
            pb.environment().put("PYTHONIOENCODING", "utf-8");
            pb.redirectOutput(pythonStdoutFile);
            pb.redirectError(pythonStderrFile);
            pythonProcess = pb.start();
            System.out.println("DEBUG MainApp: Python OCR server process started. Logs: " + pythonStdoutFile.getAbsolutePath());
            Thread.sleep(5000); // Give server time to start
        } catch (IOException | InterruptedException e) {
            System.err.println("Error starting Python OCR server: " + e.getMessage());
            showAlert("Python Server Error", "Failed to start Python OCR server. Check console for details.");
            Platform.exit(); // Exit if Python server fails to start
        }
    }

    private void loadChatRegion(Preferences prefs) {
        int x = prefs.getInt(PREF_REGION_X, -1);
        if (x != -1) {
            int y = prefs.getInt(PREF_REGION_Y, 0);
            int width = prefs.getInt(PREF_REGION_WIDTH, 0);
            int height = prefs.getInt(PREF_REGION_HEIGHT, 0);
            this.chatRegion = new java.awt.Rectangle(x, y, width, height);
        }
    }

    private void saveChatRegion(Preferences prefs) {
        if (chatRegion != null) {
            prefs.putInt(PREF_REGION_X, chatRegion.x);
            prefs.putInt(PREF_REGION_Y, chatRegion.y);
            prefs.putInt(PREF_REGION_WIDTH, chatRegion.width);
            prefs.putInt(PREF_REGION_HEIGHT, chatRegion.height);
        }
    }

    private void showAlert(String title, String content) {
        Alert alert = new Alert(AlertType.ERROR);
        alert.setTitle(title);
        alert.setHeaderText(null);
        alert.setContentText(content);
        alert.showAndWait();
    }

    @Override
    public void stop() {
        if (keybindService != null) {
            keybindService.unregister();
        }
        if (translationService != null) {
            translationService.shutdown();
        }
        if (pythonProcess != null) {
            System.out.println("DEBUG MainApp: Attempting to terminate Python OCR server.");
            pythonProcess.destroy();
            try {
                if (!pythonProcess.waitFor(5, TimeUnit.SECONDS)) {
                    pythonProcess.destroyForcibly();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        System.out.println("Application stopped.");
    }
}
