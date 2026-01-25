package org.example.bamsemats.dotatranslator;

import javafx.application.Application;
import javafx.fxml.FXMLLoader;
import javafx.scene.Scene;
import javafx.scene.layout.VBox;
import javafx.scene.shape.Rectangle;
import javafx.stage.Stage;
import javafx.stage.StageStyle;
import javafx.scene.control.Alert; // Import for Alert
import javafx.scene.control.Alert.AlertType; // Import for AlertType

import java.io.*;

import javafx.application.Platform; // Added import
import java.util.prefs.Preferences; // Import for Preferences
import javafx.scene.control.Button;
import javafx.scene.control.TextField;
import javafx.scene.control.Label;
import javafx.stage.FileChooser;
import javafx.geometry.Insets;

import java.util.concurrent.TimeUnit; // Added import
import java.nio.charset.StandardCharsets; // Added import

public class MainApp extends Application {

    private ScreenCaptureService captureService;
    private ChatWindowController chatWindowController;
    private Stage chatStage;
    private TranslationService translationService;
    private Process pythonProcess; // Added field to manage Python server process

    private static final String GOOGLE_CLOUD_PROJECT_ID = "dota-translator-485221";
    private static final String PREF_CREDENTIALS_PATH = "googleCredentialsPath";

    private String userCredentialsPath; // To store the path selected by the user

    public static void main(String[] args) {
        launch(args);
    }

    @Override
    public void start(Stage primaryStage) throws IOException {
        this.primaryStage = primaryStage;

        // Load saved credentials path if available
        Preferences prefs = Preferences.userNodeForPackage(MainApp.class);
        userCredentialsPath = prefs.get(PREF_CREDENTIALS_PATH, "");

        // 1. Prompt for Google Cloud Credentials if not set or invalid
        if (userCredentialsPath.isEmpty()) {
            userCredentialsPath = showCredentialsSelectionDialog(primaryStage);
            if (userCredentialsPath == null || userCredentialsPath.isEmpty()) {
                // User cancelled or didn't provide credentials, exit gracefully
                System.out.println("Google Cloud credentials not provided. Exiting application.");
                Platform.exit();
                return;
            }
            prefs.put(PREF_CREDENTIALS_PATH, userCredentialsPath);
        } else {
            // Validate if the stored path is still valid, if not, prompt again
            File credFile = new File(userCredentialsPath);
            if (!credFile.exists() || !credFile.isFile()) {
                System.out.println("Stored credentials file not found: " + userCredentialsPath + ". Prompting user to re-select.");
                userCredentialsPath = showCredentialsSelectionDialog(primaryStage);
                if (userCredentialsPath == null || userCredentialsPath.isEmpty()) {
                    System.out.println("Google Cloud credentials not provided. Exiting application.");
                    Platform.exit();
                    return;
                }
                prefs.put(PREF_CREDENTIALS_PATH, userCredentialsPath);
            }
        }

        // --- Start Python OCR Server ---
        // Create temporary log files for Python output
        File pythonStdoutFile = File.createTempFile("python_stdout_", ".log");
        File pythonStderrFile = File.createTempFile("python_stderr_", ".log");
        pythonStdoutFile.deleteOnExit(); // Clean up on exit
        pythonStderrFile.deleteOnExit(); // Clean up on exit

        try {
            ProcessBuilder pb = new ProcessBuilder("python", "app.py");
            pb.directory(new File("python_ocr")); // Set working directory for Python app
            // Set GOOGLE_APPLICATION_CREDENTIALS for the Python process
            pb.environment().put("GOOGLE_APPLICATION_CREDENTIALS", userCredentialsPath);
            // Set Python output encoding to UTF-8 to prevent UnicodeEncodeError
            pb.environment().put("PYTHONIOENCODING", "utf-8");
            pb.redirectOutput(pythonStdoutFile); // Redirect stdout to file
            pb.redirectError(pythonStderrFile); // Redirect stderr to file
            pythonProcess = pb.start();
            System.out.println("DEBUG MainApp: Python OCR server process started. Output redirected to " + pythonStdoutFile.getAbsolutePath() + " and " + pythonStderrFile.getAbsolutePath());

            // Give the Python server a moment to start up
            Thread.sleep(5000); // 5 seconds

        } catch (IOException | InterruptedException e) {
            System.err.println("Error starting Python OCR server: " + e.getMessage());
            // Read and display Python stderr for debugging
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(new FileInputStream(pythonStderrFile), StandardCharsets.UTF_8))) {
                StringBuilder errorOutput = new StringBuilder("Python OCR server failed to start. Error output:\n");
                String line;
                while ((line = reader.readLine()) != null) {
                    errorOutput.append(line).append("\n");
                }
                System.err.println(errorOutput.toString());
                Platform.runLater(() -> chatWindowController.addMessage("Error: Could not start Python OCR server. Details in console."));
            } catch (IOException logReadError) {
                System.err.println("Error reading Python stderr log: " + logReadError.getMessage());
                Platform.runLater(() -> chatWindowController.addMessage("Error: Could not start Python OCR server. Check console for details."));
            }
            Platform.exit();
            return;
        }

        primaryStage.setTitle("Dota 2 Chat Translator Setup");
        primaryStage.setWidth(1);
        primaryStage.setHeight(1);
        primaryStage.setOpacity(0.01);
        primaryStage.initStyle(StageStyle.UNDECORATED);
        primaryStage.show();

        // Prompt user to select region
        Alert alert = new Alert(AlertType.INFORMATION);
        alert.setTitle("Dota 2 Chat Translator");
        alert.setHeaderText("Select Chat Region");
        alert.setContentText("Please select the in-game chat window region on your screen. Drag to draw a rectangle over the chat.");
        alert.showAndWait(); // Show alert and wait for user to click OK

        // Initial region selection
        Rectangle fxRect = new RegionSelector().selectRegion(primaryStage);
        this.chatRegion = RegionSelector.toAwt(fxRect); // Store chatRegion as a member variable
        System.out.println("Selected chat region: " + this.chatRegion);

        // Hide the primary stage once region selection is done
        primaryStage.hide();

        // Load the chat display window
        FXMLLoader loader = new FXMLLoader(getClass().getResource("/ChatWindow.fxml"));
        VBox root = loader.load();
        chatWindowController = loader.getController();
        System.out.println("DEBUG MainApp: chatWindowController after loader.getController(): " + chatWindowController);
        chatWindowController.setReselectRegionCallback(this::reselectChatRegion); // Set the callback
        chatWindowController.setPerformOcrCallback(this::performOcrAction); // Set the OCR action callback
        System.out.println("DEBUG MainApp: performOcrCallback set on controller.");

        chatStage = new Stage();
        chatStage.setTitle("Dota 2 Chat");
        chatStage.setScene(new Scene(root, 400, 600));
        chatStage.show();
        chatWindowController.setStage(chatStage); // Pass the chatStage to the controller

        // Initialize OCR and Translation services
        OcrService ocrService = new OcrService(false, chatWindowController); // Pass chatWindowController
        translationService = new TranslationService(GOOGLE_CLOUD_PROJECT_ID, userCredentialsPath, chatWindowController); // Pass chatWindowController

        // Pass all necessary services and controller to capture service
        captureService = new ScreenCaptureService(this.chatRegion, ocrService, chatWindowController, translationService); // Pass the translationService

        // No continuous capture (ScreenCaptureService.start() removed)
    }

    private Stage primaryStage; // Add as member variable
    private java.awt.Rectangle chatRegion; // Add as member variable

    // Method to reselect chat region
    private void reselectChatRegion(Void unused) {
        if (captureService != null) {
            // No need to stop captureService as it's not continuous anymore,
            // but we need to update its region and reset its hash.
            // captureService.stop(); // Removed as there's no timer to stop
        }

        Platform.runLater(() -> {
            try {
                this.chatRegion = performRegionSelection(primaryStage);
                System.out.println("Re-selected chat region: " + this.chatRegion);

                // Update the existing captureService with the new region
                if (captureService != null) {
                    captureService.setChatRegion(this.chatRegion);
                } else {
                    // This case should ideally not happen if captureService is always initialized
                    OcrService ocrService = new OcrService(false, chatWindowController); // Pass chatWindowController
                    translationService = new TranslationService(GOOGLE_CLOUD_PROJECT_ID, userCredentialsPath, chatWindowController); // Reinitialize with userCredentialsPath
                    captureService = new ScreenCaptureService(this.chatRegion, ocrService, chatWindowController, translationService);
                }
                // No need to start captureService as it's on-demand now.
                // captureService.start(); // Removed as there's no timer to start

            } catch (IOException e) {
                System.err.println("Error during region re-selection: " + e.getMessage());
                // Propagate as a RuntimeException as Platform.runLater does not allow checked exceptions
                throw new RuntimeException("Failed to re-select region", e);
            }
        });
    }

    // Method to trigger OCR action from button click
    private void performOcrAction(Void unused) {
        System.out.println("DEBUG MainApp: performOcrAction entered.");
        if (captureService != null) {
            System.out.println("DEBUG MainApp: captureService is not null, calling captureAndProcess().");
            try {
                captureService.captureAndProcess();
            } catch (IOException e) {
                System.err.println("Error during on-demand OCR: " + e.getMessage());
                Platform.runLater(() -> chatWindowController.addMessage("Error performing OCR: " + e.getMessage()));
            }
        } else {
            System.out.println("DEBUG MainApp: captureService is NULL, cannot perform OCR.");
            Platform.runLater(() -> chatWindowController.addMessage("Error: Capture service not initialized."));
        }
    }

    // Extracted method to perform region selection, declares IOException
    private java.awt.Rectangle performRegionSelection(Stage stage) throws IOException {
        stage.show(); // Show the primary stage for re-selection
        Alert alert = new Alert(AlertType.INFORMATION);
        alert.setTitle("Dota 2 Chat Translator");
        alert.setHeaderText("Re-select Chat Region");
        alert.setContentText("Please re-select the in-game chat window region on your screen. Drag to draw a rectangle over the chat.");
        alert.showAndWait();

        Rectangle fxRect = new RegionSelector().selectRegion(stage);
        stage.hide(); // Hide after re-selection
        return RegionSelector.toAwt(fxRect);
    }

    /**
     * Called automatically when the app window closes
     * Stops background capture threads to prevent lingering process
     */
    @Override
    public void stop() {
        // No continuous capture to stop, but ensures cleanup of services if they were running
        // if (captureService != null) {
        // captureService.stop(); // Removed as timer is gone
        // }
        if (chatStage != null) {
            chatStage.hide();
        }
        if (translationService != null) {
            translationService.shutdown();
        }
        // Terminate Python process
        if (pythonProcess != null) {
            System.out.println("DEBUG MainApp: Attempting to terminate Python OCR server.");
            pythonProcess.destroy(); // Send termination signal
            try {
                if (!pythonProcess.waitFor(5, TimeUnit.SECONDS)) { // Wait for a few seconds
                    pythonProcess.destroyForcibly(); // Force kill if not terminated
                }
            } catch (InterruptedException e) {
                System.err.println("Error waiting for Python process to terminate: " + e.getMessage());
                Thread.currentThread().interrupt();
            }
        }
        System.out.println("Application stopped. All threads terminated.");
    }

    // Dialog to let user select Google Cloud credentials file
    private String showCredentialsSelectionDialog(Stage ownerStage) {
        Stage dialogStage = new Stage();
        dialogStage.initOwner(ownerStage);
        dialogStage.initStyle(StageStyle.UTILITY);
        dialogStage.setTitle("Google Cloud Credentials");

        VBox root = new VBox(10);
        root.setPadding(new Insets(10));

        Label label = new Label("Please select your Google Cloud Service Account JSON file:");
        TextField pathField = new TextField(userCredentialsPath);
        pathField.setEditable(false);

        Button browseButton = new Button("Browse...");
        browseButton.setOnAction(e -> {
            FileChooser fileChooser = new FileChooser();
            fileChooser.setTitle("Select Google Cloud Credentials File");
            fileChooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("JSON Files", "*.json"));
            File file = fileChooser.showOpenDialog(dialogStage);
            if (file != null) {
                pathField.setText(file.getAbsolutePath());
            }
        });

        Button okButton = new Button("OK");
        okButton.setOnAction(e -> dialogStage.close());

        root.getChildren().addAll(label, pathField, browseButton, okButton);
        dialogStage.setScene(new Scene(root));
        dialogStage.showAndWait();

        return pathField.getText();
    }
}
