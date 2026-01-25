package org.example.bamsemats.dotatranslator;

import javafx.fxml.FXML;
import javafx.scene.control.ListView;
import javafx.collections.ObservableList;
import javafx.collections.FXCollections;
import javafx.stage.FileChooser;
import javafx.stage.Stage;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.function.Consumer; // Import Consumer

public class ChatWindowController {

    @FXML
    private ListView<String> chatListView;

    private ObservableList<String> chatMessages;

    private Stage stage;
    private Consumer<Void> reselectRegionCallback; // Callback for re-selecting region
    private Consumer<Void> performOcrCallback; // New callback for performing OCR

    public void setStage(Stage stage) {
        this.stage = stage;
    }

    // Setter for the reselectRegionCallback
    public void setReselectRegionCallback(Consumer<Void> callback) {
        this.reselectRegionCallback = callback;
    }

    // Setter for the performOcrCallback
    public void setPerformOcrCallback(Consumer<Void> callback) {
        this.performOcrCallback = callback;
        System.out.println("DEBUG ChatWindowController: setPerformOcrCallback invoked.");
    }

    @FXML
    public void initialize() {
        chatMessages = FXCollections.observableArrayList();
        chatListView.setItems(chatMessages);
    }

    public void addMessage(String message) {
        if (chatMessages != null) {
            chatMessages.add(message);
            // Optionally, scroll to the bottom
            chatListView.scrollTo(chatMessages.size() - 1);
        }
    }

    @FXML
    private void handleReselectRegion() {
        System.out.println("Re-select Chat Region button clicked.");
        if (reselectRegionCallback != null) {
            reselectRegionCallback.accept(null); // Trigger the callback
        }
    }

    @FXML
    private void handleScanChat() {
        System.out.println("Scan Chat button clicked.");
        if (performOcrCallback != null) {
            System.out.println("DEBUG ChatWindowController: performOcrCallback is not null, triggering OCR action.");
            performOcrCallback.accept(null); // Trigger the OCR action
        } else {
            System.out.println("DEBUG ChatWindowController: performOcrCallback is NULL. OCR action cannot be triggered.");
        }
    }

    @FXML
    private void handleSaveChatLog() {
        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Save Chat Log");
        fileChooser.getExtensionFilters().addAll(
                new FileChooser.ExtensionFilter("Text Files", "*.txt"),
                new FileChooser.ExtensionFilter("All Files", "*.*")
        );

        // Get the current stage to show the file chooser modally
        File file = fileChooser.showSaveDialog(stage);

        if (file != null) {
            try (FileWriter fileWriter = new FileWriter(file)) {
                for (String message : chatMessages) {
                    fileWriter.write(message + System.lineSeparator());
                }
                System.out.println("Chat log saved to: " + file.getAbsolutePath());
            } catch (IOException e) {
                System.err.println("Error saving chat log: " + e.getMessage());
                // Optionally show an alert to the user
            }
        }
    }
}
