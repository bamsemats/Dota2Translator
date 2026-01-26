package org.example.bamsemats.dotatranslator;

import javafx.application.Platform;

import java.awt.Rectangle;
import java.awt.Robot;
import java.awt.image.BufferedImage;
import java.awt.AWTException;
import java.io.IOException;
import java.util.List;
import java.util.Objects;

public class ScreenCaptureService {

    private final Robot robot;
    private Rectangle chatRegion;
    private final OcrService ocrService;
    private final MainViewController mainViewController;
    private final TranslationService translationService;
    private int lastImageHashCode = 0;

    public ScreenCaptureService(Rectangle chatRegion, OcrService ocrService,
                                MainViewController mainViewController, TranslationService translationService) {
        try {
            this.robot = new Robot();
        } catch (AWTException e) {
            throw new RuntimeException(e);
        }

        this.chatRegion = chatRegion;
        this.ocrService = ocrService;
        this.mainViewController = mainViewController;
        this.translationService = translationService;
    }

    public void setChatRegion(Rectangle newChatRegion) {
        this.chatRegion = newChatRegion;
        this.lastImageHashCode = 0;
    }

    public void captureAndProcess() throws IOException {
        if (chatRegion == null) {
            Platform.runLater(() -> mainViewController.setNotification("Cannot take snapshot: No chat region selected."));
            return;
        }
        BufferedImage image = robot.createScreenCapture(chatRegion);
        int currentImageHashCode = getImageHashCode(image);
        System.out.println("DEBUG: captureAndProcess called. currentImageHashCode: " + currentImageHashCode + ", lastImageHashCode: " + lastImageHashCode);

        if (currentImageHashCode == lastImageHashCode) {
            System.out.println("DEBUG: Image is identical, skipping OCR.");
            return;
        }
        lastImageHashCode = currentImageHashCode;
        System.out.println("DEBUG: Image changed, proceeding with OCR.");

        List<OcrResult.Line> ocrLines = ocrService.extractText(image);

        for (OcrResult.Line lineObject : ocrLines) {
            final String finalOriginalText = lineObject.getText().trim();
            final String finalDetectedLanguage = lineObject.getLanguage();

            if (!finalOriginalText.isBlank()) {
                Platform.runLater(() -> {
                    if (translationService != null && !"en".equalsIgnoreCase(finalDetectedLanguage) && !"und".equalsIgnoreCase(finalDetectedLanguage)) {
                        String translatedText = translationService.translateText(finalOriginalText, finalDetectedLanguage);
                        System.out.println("DEBUG ScreenCaptureService: Adding translated message: " + translatedText);
                        mainViewController.addMessage(translatedText);
                        System.out.println("DEBUG ScreenCaptureService: Adding original message: (" + finalOriginalText + ")");
                        mainViewController.addMessage("(" + finalOriginalText + ")");
                    } else {
                        System.out.println("DEBUG ScreenCaptureService: Adding original message (no translation): " + finalOriginalText);
                        mainViewController.addMessage(finalOriginalText);
                    }
                });
            }
        }
    }

    private int getImageHashCode(BufferedImage image) {
        int result = 0;
        int sampleStepX = Math.max(1, image.getWidth() / 100);
        int sampleStepY = Math.max(1, image.getHeight() / 100);

        for (int x = 0; x < image.getWidth(); x += sampleStepX) {
            for (int y = 0; y < image.getHeight(); y += sampleStepY) {
                result = 31 * result + image.getRGB(x, y);
            }
        }
        return result;
    }
}
