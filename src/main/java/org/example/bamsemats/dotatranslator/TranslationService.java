package org.example.bamsemats.dotatranslator;

import com.google.cloud.translate.v3.LocationName;
import com.google.cloud.translate.v3.TranslateTextRequest;
import com.google.cloud.translate.v3.TranslateTextResponse;
import com.google.cloud.translate.v3.TranslationServiceClient;
import com.google.cloud.translate.v3.TranslationServiceSettings;
import com.google.auth.oauth2.GoogleCredentials;
import com.google.api.gax.core.FixedCredentialsProvider;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.File;
import javafx.application.Platform;
import org.example.bamsemats.dotatranslator.ChatWindowController;
import org.example.bamsemats.dotatranslator.UsageTracker;

import java.util.HashMap; // Added import for HashMap
import java.util.Map;     // Added import for Map

public class TranslationService {

    private final String projectId;
    private final TranslationServiceClient client;
    private final ChatWindowController chatController;
    private final Map<String, String> translationCache = new HashMap<>(); // Added translation cache

    // The target language for all translations
    private static final String TARGET_LANGUAGE = "en";

    public TranslationService(String projectId, String credentialsFilePath, ChatWindowController chatController) throws IOException {
        this.projectId = projectId;
        this.chatController = chatController;
        TranslationServiceClient tempClient = null;
        try {
            if (credentialsFilePath != null && !credentialsFilePath.isEmpty()) {
                File credentialsFile = new File(credentialsFilePath);
                if (credentialsFile.exists() && credentialsFile.isFile()) {
                    GoogleCredentials credentials = GoogleCredentials.fromStream(new FileInputStream(credentialsFilePath));
                    TranslationServiceSettings settings = TranslationServiceSettings.newBuilder()
                        .setCredentialsProvider(FixedCredentialsProvider.create(credentials))
                        .build();
                    tempClient = TranslationServiceClient.create(settings);
                } else {
                    Platform.runLater(() -> chatController.addMessage("Warning: Google Cloud credentials file not found at " + credentialsFilePath + ". Translation will be disabled."));
                }
            } else {
                Platform.runLater(() -> chatController.addMessage("No Google Cloud credentials path provided. Translation will be disabled."));
            }
        } catch (Exception e) {
            Platform.runLater(() -> chatController.addMessage("Error initializing Google Cloud Translation Service: " + e.getMessage() + ". Translation will be disabled."));
            System.err.println("Error initializing Google Cloud Translation Service: " + e.getMessage());
        }
        this.client = tempClient;
    }

    /**
     * Translates text from a detected source language to English.
     *
     * @param sourceText The text to translate.
     * @param sourceLanguage The detected source language code (e.g., "ru", "fr").
     * @return The translated text, or the original text if translation fails or is not needed.
     */
    public String translateText(String sourceText, String sourceLanguage) {
        if (this.client == null || sourceText == null || sourceText.trim().isEmpty() || TARGET_LANGUAGE.equalsIgnoreCase(sourceLanguage)) {
            return sourceText;
        }

        String cacheKey = sourceText + "::" + sourceLanguage;
        if (translationCache.containsKey(cacheKey)) {
            // System.out.println("DEBUG: Returning cached translation for: " + sourceText); // Optional debug
            return translationCache.get(cacheKey);
        }

        // --- Safeguard: Check Translation API limit ---
        if (UsageTracker.isTranslationLimitReached()) {
            Platform.runLater(() -> chatController.addMessage("Warning: Translation free tier limit reached for this month. Further translation requests are blocked."));
            return sourceText;
        }

        try {
            LocationName parent = LocationName.of(projectId, "global");

            TranslateTextRequest request =
                    TranslateTextRequest.newBuilder()
                            .setParent(parent.toString())
                            .setMimeType("text/plain")
                            .setTargetLanguageCode(TARGET_LANGUAGE)
                            .addContents(sourceText)
                            .setSourceLanguageCode(sourceLanguage)
                            .build();

            TranslateTextResponse response = client.translateText(request);

            // Increment usage on successful request
            UsageTracker.incrementTranslationCharacters(sourceText.length());

            // --- Safeguard: Check for warning threshold ---
            if (UsageTracker.getTranslationUsagePercentage() >= 80 && UsageTracker.getTranslationUsagePercentage() < 100) {
                Platform.runLater(() -> chatController.addMessage(
                        String.format("Warning: Translation usage is at %.0f%% of the free tier limit (%d/%d characters). You may be billed soon.",
                                UsageTracker.getTranslationUsagePercentage(), UsageTracker.getTranslationCharacters(), UsageTracker.getTranslationFreeTierLimit())
                ));
            }

            if (!response.getTranslationsList().isEmpty()) {
                String translatedText = response.getTranslationsList().get(0).getTranslatedText();
                translationCache.put(cacheKey, translatedText); // Add to cache
                return translatedText;
            }
        } catch (Exception e) {
            System.err.println("Error during translation: " + e.getMessage());
            Platform.runLater(() -> chatController.addMessage("Error translating: " + e.getMessage()));
            // Fallback: return original text if translation fails
        }
        return sourceText;
    }

    public void shutdown() {
        if (client != null) {
            client.close();
        }
    }
}
