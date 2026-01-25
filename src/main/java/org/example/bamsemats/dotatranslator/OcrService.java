package org.example.bamsemats.dotatranslator;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import javafx.application.Platform;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

public class OcrService {

    private final HttpClient httpClient;
    private final URI ocrEndpoint;
    private final boolean saveDebugImages;
    private final ObjectMapper objectMapper;
    private final ChatWindowController chatController; // Added ChatWindowController dependency


    public OcrService(boolean saveDebugImages, ChatWindowController chatController) { // Modified constructor
        this.saveDebugImages = saveDebugImages;
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(10))
                .build();
        this.ocrEndpoint = URI.create("http://127.0.0.1:5001/ocr");
        this.objectMapper = new ObjectMapper();
        this.chatController = chatController; // Store ChatWindowController
    }

    /**
     * Extract text and language from a screenshot image by sending it to a Python service.
     *
     * @param src The BufferedImage to process.
     * @return An OcrResult object containing the extracted text and language, or a default
     *         OcrResult if an error occurs.
     */
    public List<OcrResult.Line> extractText(BufferedImage src) {
        // --- Safeguard: Check OCR API limit ---
        if (UsageTracker.isOcrLimitReached()) {
            Platform.runLater(() -> chatController.addMessage("Warning: OCR free tier limit reached for this month. Further OCR requests are blocked."));
            return Collections.emptyList();
        }

        try {
            // Convert BufferedImage to byte array (PNG format)
            byte[] imageData;
            try (ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
                ImageIO.write(src, "png", baos);
                imageData = baos.toByteArray();
            }

            // Build the multipart/form-data request body
            String boundary = "Boundary-" + UUID.randomUUID().toString();
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(ocrEndpoint)
                    .timeout(Duration.ofSeconds(10))
                    .header("Content-Type", "multipart/form-data;boundary=" + boundary)
                    .POST(ofMimeMultipartData(imageData, boundary))
                    .build();

            // Send the request and get the response
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() == 200) {
                UsageTracker.incrementOcrRequests(); // Increment usage on successful request

                // --- Safeguard: Check for warning threshold ---
                if (UsageTracker.getOcrUsagePercentage() >= 80 && UsageTracker.getOcrUsagePercentage() < 100) {
                    Platform.runLater(() -> chatController.addMessage(
                            String.format("Warning: OCR usage is at %.0f%% of the free tier limit (%d/%d requests). You may be billed soon.",
                                    UsageTracker.getOcrUsagePercentage(), UsageTracker.getOcrRequests(), UsageTracker.getOcrFreeTierLimit())
                    ));
                }

                return parseOcrResultFromJson(response.body());
            } else {
                System.err.println("OCR service failed with status code: " + response.statusCode());
                System.err.println("Response body: " + response.body());
                Platform.runLater(() -> chatController.addMessage("Error: OCR service failed (Status " + response.statusCode() + ")."));
                return Collections.emptyList();
            }

        } catch (IOException | InterruptedException e) {
            System.err.println("Error communicating with OCR service: " + e.getMessage());
            if (e instanceof java.net.ConnectException) {
                System.err.println("Is the Python OCR server running? Start it by running 'python app.py' in the 'python_ocr' directory.");
                Platform.runLater(() -> chatController.addMessage("Error: Python OCR server not reachable. Is it running?"));
            } else {
                Platform.runLater(() -> chatController.addMessage("Error: Failed to communicate with OCR service."));
            }
            Thread.currentThread().interrupt();
            return Collections.emptyList();
        }
    }

    /**
     * Creates a request body for a multipart/form-data request.
     */
    private HttpRequest.BodyPublisher ofMimeMultipartData(byte[] imageData, String boundary) {
        var byteArrays = new java.util.ArrayList<byte[]>();
        byteArrays.add(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        byteArrays.add(("Content-Disposition: form-data; name=\"file\"; filename=\"capture.png\"\r\n").getBytes(StandardCharsets.UTF_8));
        byteArrays.add(("Content-Type: image/png\r\n\r\n").getBytes(StandardCharsets.UTF_8));
        byteArrays.add(imageData);
        byteArrays.add(("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        return HttpRequest.BodyPublishers.ofByteArrays(byteArrays);
    }

    /**
     * Parses the JSON response from the OCR service into a List of OcrResult.Line objects.
     * Expected JSON format: [{"text": "...", "language": "..."}, {...}]
     */
    private List<OcrResult.Line> parseOcrResultFromJson(String json) {
        try {
            return objectMapper.readValue(json, new TypeReference<List<OcrResult.Line>>() {});
        } catch (IOException e) {
            System.err.println("Failed to parse JSON response: " + json + ". Error: " + e.getMessage());
            Platform.runLater(() -> chatController.addMessage("Error: Failed to parse OCR response."));
            return Collections.emptyList();
        }
    }
}
