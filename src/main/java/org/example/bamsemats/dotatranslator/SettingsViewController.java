package org.example.bamsemats.dotatranslator;

import com.github.kwhat.jnativehook.keyboard.NativeKeyEvent;
import javafx.application.Platform;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.ComboBox;
import javafx.scene.control.ChoiceBox;
import javafx.scene.control.Label;
import javafx.scene.control.Slider;
import javafx.scene.control.TextField;
import javafx.scene.input.KeyCode;
import javafx.scene.text.Font;

import java.util.function.BiConsumer;
import java.util.function.Consumer;

public class SettingsViewController {

    @FXML
    private TextField keybindTextField;
    @FXML
    private Button changeKeybindButton;
    @FXML
    private ComboBox<String> fontFamilyComboBox;
    @FXML
    private Slider fontSizeSlider;
    @FXML
    private Label fontSizeLabel;
    @FXML
    private ChoiceBox<String> themeChoiceBox;


    private Runnable selectRegionCallback;
    private Consumer<Integer> setSnapshotKeyCallback;
    private BiConsumer<String, Double> fontChangeCallback;
    private Consumer<String> themeChangeCallback;

    public void initialize() {
        fontFamilyComboBox.getItems().addAll(Font.getFamilies());
        fontSizeSlider.valueProperty().addListener((obs, oldVal, newVal) -> {
            double size = newVal.doubleValue();
            fontSizeLabel.setText(String.format("%.0fpt", size));
            if (fontChangeCallback != null) {
                fontChangeCallback.accept(fontFamilyComboBox.getValue(), size);
            }
        });
        fontFamilyComboBox.getSelectionModel().selectedItemProperty().addListener((obs, oldVal, newVal) -> {
            if (fontChangeCallback != null) {
                fontChangeCallback.accept(newVal, fontSizeSlider.getValue());
            }
        });

        themeChoiceBox.getItems().addAll("Dark", "Light");
        themeChoiceBox.getSelectionModel().selectedItemProperty().addListener((obs, oldVal, newVal) -> {
            if (themeChangeCallback != null) {
                themeChangeCallback.accept(newVal);
            }
        });
    }

    public void setSelectRegionCallback(Runnable callback) {
        this.selectRegionCallback = callback;
    }

    public void setSetSnapshotKeyCallback(Consumer<Integer> callback) {
        this.setSnapshotKeyCallback = callback;
    }

    public void setFontChangeCallback(BiConsumer<String, Double> callback) {
        this.fontChangeCallback = callback;
    }

    public void setThemeChangeCallback(Consumer<String> callback) {
        this.themeChangeCallback = callback;
    }

    public void setCurrentFont(String family, double size) {
        fontFamilyComboBox.setValue(family);
        fontSizeSlider.setValue(size);
    }

    public void setCurrentTheme(String theme) {
        themeChoiceBox.setValue(theme);
    }

    public void setSnapshotKey(int keyCode) {
        keybindTextField.setText(NativeKeyEvent.getKeyText(keyCode));
    }

    @FXML
    private void handleSelectRegion() {
        if (selectRegionCallback != null) {
            selectRegionCallback.run();
        }
    }

    @FXML
    private void handleChangeKeybind() {
        keybindTextField.setText("Press a key...");
        changeKeybindButton.getScene().setOnKeyPressed(event -> {
            if (setSnapshotKeyCallback != null) {
                int nativeKeyCode = convertKeyCode(event.getCode());
                if (nativeKeyCode != -1) {
                    setSnapshotKeyCallback.accept(nativeKeyCode);
                    Platform.runLater(() -> {
                        keybindTextField.setText(NativeKeyEvent.getKeyText(nativeKeyCode));
                        changeKeybindButton.getScene().setOnKeyPressed(null);
                    });
                }
            }
        });
    }

    private int convertKeyCode(KeyCode fxKey) {
        switch (fxKey) {
            case F1: return NativeKeyEvent.VC_F1;
            case F2: return NativeKeyEvent.VC_F2;
            case F3: return NativeKeyEvent.VC_F3;
            case F4: return NativeKeyEvent.VC_F4;
            case F5: return NativeKeyEvent.VC_F5;
            case F6: return NativeKeyEvent.VC_F6;
            case F7: return NativeKeyEvent.VC_F7;
            case F8: return NativeKeyEvent.VC_F8;
            case F9: return NativeKeyEvent.VC_F9;
            case F10: return NativeKeyEvent.VC_F10;
            case F11: return NativeKeyEvent.VC_F11;
            case F12: return NativeKeyEvent.VC_F12;
            default:
                return -1;
        }
    }
}
