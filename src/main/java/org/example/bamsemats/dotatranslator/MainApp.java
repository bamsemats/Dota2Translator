package org.example.bamsemats.dotatranslator;

import javafx.application.Application;
import javafx.scene.shape.Rectangle;
import javafx.stage.Stage;

public class MainApp extends Application {

    private ScreenCaptureService captureService;

    public static void main(String[] args) {
        launch(args);
    }

    @Override
    public void start(Stage stage) {
        stage.setTitle("Dota 2 Chat Translator");
        stage.setWidth(300);
        stage.setHeight(100);
        stage.show();

        // 1️⃣ Let user select chat region
        RegionSelector selector = new RegionSelector();
        Rectangle fxRect = selector.selectRegion(stage);

        java.awt.Rectangle chatRegion = RegionSelector.toAwt(fxRect);
        System.out.println("Selected chat region: " + chatRegion);

        // 2️⃣ Initialize capture service with OCR
        captureService = new ScreenCaptureService(chatRegion);

        // 3️⃣ Start capturing OCR in background
        captureService.start();
    }

    /**
     * Called automatically when the app window closes
     * Stops background capture threads to prevent lingering process
     */
    @Override
    public void stop() {
        if (captureService != null) {
            captureService.stop();
        }
        System.out.println("Application stopped. All threads terminated.");
    }
}
