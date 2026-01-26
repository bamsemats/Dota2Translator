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
import com.google.api.client.auth.oauth2.Credential; // Use this Credential type

public class OcrService {

    private final HttpClient httpClient;
    private final URI ocrEndpoint;
    private final boolean saveDebugImages;
    private final ObjectMapper objectMapper;
    private final MainViewController mainViewController;
    private final Credential credential; // Store the Credential object
    private final String projectId;
    private final String clientId; // New field
    private final String clientSecret; // New field


    public OcrService(boolean saveDebugImages, MainViewController mainViewController, Credential credential, String projectId, String clientId, String clientSecret) {
        this.saveDebugImages = saveDebugImages;
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(10))
                .build();
        this.ocrEndpoint = URI.create("http://127.0.0.1:5001/ocr");
        this.objectMapper = new ObjectMapper();
        this.mainViewController = mainViewController;
        this.credential = credential; // Store the credential
        this.projectId = projectId;
        this.clientId = clientId; // Store client ID
        this.clientSecret = clientSecret; // Store client Secret
    }

    /**
     * Extract text and language from a screenshot image by sending it to a Python service.
     *
     * @param src The BufferedImage to process.
     * @return An OcrResult object containing the extracted text and language, or a default
     *         OcrResult if an error occurs.
     */
    public List<OcrResult.Line> extractText(BufferedImage src) {
        if (UsageTracker.isOcrLimitReached()) {
            Platform.runLater(() -> mainViewController.addMessage("Warning: OCR free tier limit reached for this month. Further OCR requests are blocked."));
            return Collections.emptyList();
        }

        try {
            byte[] imageData;
            try (ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
                ImageIO.write(src, "png", baos);
                imageData = baos.toByteArray();
            }

            String boundary = "Boundary-" + UUID.randomUUID().toString();
            HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
                    .uri(ocrEndpoint)
                    .timeout(Duration.ofSeconds(10))
                    .header("Content-Type", "multipart/form-data;boundary=" + boundary)
                    .POST(ofMimeMultipartData(imageData, boundary));
            
            // Add OAuth 2.0 Access Token and Project ID to headers
            if (credential != null && credential.getAccessToken() != null) {
                requestBuilder.header("Authorization", "Bearer " + credential.getAccessToken()); // Use getAccessToken() from Credential
            }
            if (projectId != null && !projectId.isEmpty()) {
                requestBuilder.header("X-Google-Cloud-Project-Id", projectId);
            }

            HttpRequest request = requestBuilder.build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() == 200) {
                UsageTracker.incrementOcrRequests();

                if (UsageTracker.getOcrUsagePercentage() >= 80 && UsageTracker.getOcrUsagePercentage() < 100) {
                    Platform.runLater(() -> mainViewController.addMessage(
                            String.format("Warning: OCR usage is at %.0f%% of the free tier limit (%d/%d requests). You may be billed soon.",
                                    UsageTracker.getOcrUsagePercentage(), UsageTracker.getOcrRequests(), UsageTracker.getOcrFreeTierLimit())
                    ));
                }

                return parseOcrResultFromJson(response.body());
            } else {
                System.err.println("OCR service failed with status code: " + response.statusCode());
                System.err.println("Response body: " + response.body());
                Platform.runLater(() -> mainViewController.addMessage("Error: OCR service failed (Status " + response.statusCode() + ")."));
                return Collections.emptyList();
            }

        } catch (IOException | InterruptedException e) {
            System.err.println("Error communicating with OCR service: " + e.getMessage());
            if (e instanceof java.net.ConnectException) {
                System.err.println("Is the Python OCR server running? Start it by running 'python app.py' in the 'python_ocr' directory.");
                Platform.runLater(() -> mainViewController.addMessage("Error: Python OCR server not reachable. Is it running?"));
            } else {
                Platform.runLater(() -> mainViewController.addMessage("Error: Failed to communicate with OCR service."));
            }
            Thread.currentThread().interrupt();
            return Collections.emptyList();
        }
    }

    private HttpRequest.BodyPublisher ofMimeMultipartData(byte[] imageData, String boundary) {
        var byteArrays = new java.util.ArrayList<byte[]>();
        byteArrays.add(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        byteArrays.add(("Content-Disposition: form-data; name=\"file\"; filename=\"capture.png\"\r\n").getBytes(StandardCharsets.UTF_8));
        byteArrays.add(("Content-Type: image/png\r\n\r\n").getBytes(StandardCharsets.UTF_8));
        byteArrays.add(imageData);
        byteArrays.add(("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        return HttpRequest.BodyPublishers.ofByteArrays(byteArrays);
    }

    private List<OcrResult.Line> parseOcrResultFromJson(String json) {
        try {
            return objectMapper.readValue(json, new TypeReference<List<OcrResult.Line>>() {});
        } catch (IOException e) {
            System.err.println("Failed to parse JSON response: " + json + ". Error: " + e.getMessage());
            Platform.runLater(() -> mainViewController.addMessage("Error: Failed to parse OCR response."));
            return Collections.emptyList();
        }
    }
}
