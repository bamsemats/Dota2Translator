package org.example.bamsemats.dotatranslator;

import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.scene.control.Label;
import javafx.scene.control.ListView;
import javafx.scene.text.Font;
import java.util.function.Consumer;

public class MainViewController {

    @FXML
    private ListView<String> chatListView;

    @FXML
    private Label notificationLabel;

    private ObservableList<String> chatMessages;
    private Runnable settingsCallback;
    private Runnable snapshotCallback;

    @FXML
    public void initialize() {
        chatMessages = FXCollections.observableArrayList();
        chatListView.setItems(chatMessages);
    }

    public void setSettingsCallback(Runnable callback) {
        this.settingsCallback = callback;
    }

    public void setSnapshotCallback(Runnable callback) {
        this.snapshotCallback = callback;
    }

    @FXML
    private void handleSettings() {
        if (settingsCallback != null) {
            settingsCallback.run();
        }
    }

    @FXML
    private void handleSnapshot() {
        if (snapshotCallback != null) {
            snapshotCallback.run();
        }
    }

    public void setNotification(String message) {
        notificationLabel.setText(message);
    }

    public void addMessage(String message) {
        if (chatMessages != null) {
            chatMessages.add(message);
            chatListView.scrollTo(chatMessages.size() - 1);
        }
    }

    public void applyFontSettings(String fontFamily, double fontSize) {
        // Apply to ListView directly for generic text
        chatListView.setStyle(String.format("-fx-font-family: '%s'; -fx-font-size: %.0fpt;", fontFamily, fontSize));
        // Apply to list cells for actual message display
        chatListView.setCellFactory(lv -> new javafx.scene.control.ListCell<String>() {
            @Override
            protected void updateItem(String item, boolean empty) {
                super.updateItem(item, empty);
                if (empty || item == null) {
                    setText(null);
                } else {
                    setText(item);
                    setStyle(String.format("-fx-font-family: '%s'; -fx-font-size: %.0fpt;", fontFamily, fontSize));
                }
            }
        });
    }
}
