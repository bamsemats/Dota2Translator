package org.example.bamsemats.dotatranslator;

import javafx.application.Platform;

import java.awt.Rectangle; // Specific import
import java.awt.Robot;     // Specific import
import java.awt.image.BufferedImage; // Specific import
import java.awt.AWTException; // Added import for AWTException
import java.io.IOException;
import java.util.List;     // Added import for List
// import java.util.Timer; // No longer needed for continuous capture
// import java.util.TimerTask; // No longer needed for continuous capture
import java.util.Objects; // Import Objects for hashCode

public class ScreenCaptureService {

    private final Robot robot;
    private Rectangle chatRegion; // Changed to non-final to allow dynamic updates
    private final OcrService ocrService;
    private final ChatWindowController chatController;
    private final TranslationService translationService; // New member variable for TranslationService
    private int lastImageHashCode = 0; // Stores the hash code of the last processed image

    public ScreenCaptureService(Rectangle chatRegion, OcrService ocrService,
                                ChatWindowController chatController, TranslationService translationService) { // Updated constructor
        try {
            this.robot = new Robot();
        } catch (AWTException e) {
            throw new RuntimeException(e);
        }

        this.chatRegion = chatRegion;
        this.ocrService = ocrService;
        this.chatController = chatController;
        this.translationService = translationService; // Store TranslationService
    }

    // New method to update the chat region if needed after re-selection
    public void setChatRegion(Rectangle newChatRegion) {
        this.chatRegion = newChatRegion;
        // Reset hash code to force OCR on the new region
        this.lastImageHashCode = 0;
    }

    // No start() or stop() methods for continuous capture anymore

    public void captureAndProcess() throws IOException { // Made public
        BufferedImage image = robot.createScreenCapture(chatRegion);
        int currentImageHashCode = getImageHashCode(image);
        System.out.println("DEBUG: captureAndProcess called. currentImageHashCode: " + currentImageHashCode + ", lastImageHashCode: " + lastImageHashCode);

        // Only proceed if the image has changed
        if (currentImageHashCode == lastImageHashCode) {
            System.out.println("DEBUG: Image is identical, skipping OCR.");
            return; // Image is identical to the last one, skip OCR
        }
        lastImageHashCode = currentImageHashCode; // Update the hash for the next comparison
        System.out.println("DEBUG: Image changed, proceeding with OCR.");

        List<OcrResult.Line> ocrLines = ocrService.extractText(image); // Changed type to List<OcrResult.Line>

        for (OcrResult.Line lineObject : ocrLines) { // Iterate over the list of line objects
            final String finalOriginalText = lineObject.getText().trim(); // Get text from Line object
            final String finalDetectedLanguage = lineObject.getLanguage(); // Get language from Line object

            if (!finalOriginalText.isBlank()) {
                Platform.runLater(() -> {
                    // Only attempt translation if translationService is not null
                    if (translationService != null && !"en".equalsIgnoreCase(finalDetectedLanguage) && !"und".equalsIgnoreCase(finalDetectedLanguage)) {
                        String translatedText = translationService.translateText(finalOriginalText, finalDetectedLanguage);
                        System.out.println("DEBUG ScreenCaptureService: Adding translated message: " + translatedText);
                        chatController.addMessage(translatedText); // Add translated text
                        System.out.println("DEBUG ScreenCaptureService: Adding original message: (" + finalOriginalText + ")");
                        chatController.addMessage("(" + finalOriginalText + ")"); // Add original text in parentheses
                    } else {
                        System.out.println("DEBUG ScreenCaptureService: Adding original message (no translation): " + finalOriginalText);
                        chatController.addMessage(finalOriginalText); // Add original text
                    }
                });
            }
        }
    }

    // Helper method to compute a hash code for a BufferedImage
    private int getImageHashCode(BufferedImage image) {
        // A simple way to get a hash code from an image's pixel data.
        // This might not be robust enough for all cases (e.g., slight pixel variations)
        // but serves as a good starting point for deduplication.
        int result = 0;
        // Sample pixels to optimize - adjust sampling rate as needed
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
