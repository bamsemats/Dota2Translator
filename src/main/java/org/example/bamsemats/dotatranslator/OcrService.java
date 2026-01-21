package org.example.bamsemats.dotatranslator;

import net.sourceforge.tess4j.ITesseract;
import net.sourceforge.tess4j.Tesseract;

import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.awt.image.RescaleOp;
import java.io.File;
import javax.imageio.ImageIO;

public class OcrService {

    private final ITesseract tesseract;
    private final boolean saveDebugImages;

    /**
     * @param saveDebugImages If true, will save processed images to disk for inspection
     */
    public OcrService(boolean saveDebugImages) {
        this.saveDebugImages = saveDebugImages;

        tesseract = new Tesseract();

        // Path to tessdata folder
        tesseract.setDatapath("src/main/resources/tessdata");

        // Language support: English + Russian
        tesseract.setLanguage("eng+rus+swe");

        // Modern LSTM OCR only
        tesseract.setOcrEngineMode(1);

        // Treat image as a single block of text (chat-style)
        tesseract.setPageSegMode(6);

        // Optional: restrict characters if you want more control
        tesseract.setTessVariable(
                "tessedit_char_whitelist",
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,!?':;()[] "
        );
    }

    /**
     * Extract text from a screenshot image
     */
    public String extractText(BufferedImage src) {
        try {
            BufferedImage processed = preprocess(src);

            if (saveDebugImages) {
                ImageIO.write(processed, "png", new File("ocr_debug.png"));
            }

            return tesseract.doOCR(processed).trim();
        } catch (Exception e) {
            System.err.println("OCR failed: " + e.getMessage());
            return "";
        }
    }

    /**
     * Preprocess image for better OCR accuracy
     * Minimal preprocessing: grayscale + slight contrast
     */
    private BufferedImage preprocess(BufferedImage src) {
        // 1. Convert to grayscale
        BufferedImage gray = new BufferedImage(
                src.getWidth(),
                src.getHeight(),
                BufferedImage.TYPE_BYTE_GRAY
        );

        Graphics2D g = gray.createGraphics();
        g.drawImage(src, 0, 0, null);
        g.dispose();

        // 2. Slight contrast adjustment (alpha >1 increases contrast)
        RescaleOp rescale = new RescaleOp(1.2f, 0f, null); // 1.2x contrast, no brightness change
        BufferedImage contrasted = rescale.filter(gray, null);

        return contrasted;
    }
}
