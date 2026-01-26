package org.example.bamsemats.dotatranslator;

import com.google.api.client.auth.oauth2.Credential;
import com.google.api.gax.core.FixedCredentialsProvider;
import com.google.auth.oauth2.UserCredentials; // Change import from GoogleCredentials to UserCredentials
import com.google.auth.oauth2.AccessToken; // Correctly placed import

import java.io.IOException;

import com.google.cloud.translate.v3.*;
import javafx.application.Platform;
import java.util.HashMap;
import java.util.Map;
import java.util.Date; // Needed for expiration time

public class TranslationService {

    private final String projectId;
    private final TranslationServiceClient client;
    private final MainViewController mainViewController;
    private final Map<String, String> translationCache = new HashMap<>();

    private static final String TARGET_LANGUAGE = "en";

    // Constructor now accepts a Credential, Client ID, and Client Secret
    public TranslationService(String projectId, Credential credential, String clientId, String clientSecret, MainViewController mainViewController) throws IOException {
        this.projectId = projectId;
        this.mainViewController = mainViewController;
        TranslationServiceClient tempClient = null;
        if (credential != null && credential.getAccessToken() != null) { // Check if credential and its token are valid
            try {
                // Create com.google.auth.oauth2.AccessToken from com.google.api.client.auth.oauth2.Credential
                com.google.auth.oauth2.AccessToken googleAuthAccessToken = new com.google.auth.oauth2.AccessToken(
                    credential.getAccessToken(),
                    new Date(credential.getExpirationTimeMilliseconds())
                );

                // Create UserCredentials from the com.google.api.client.auth.oauth2.Credential
                UserCredentials.Builder userCredentialsBuilder = UserCredentials.newBuilder()
                    .setAccessToken(googleAuthAccessToken)
                    .setClientId(clientId) // Set client ID
                    .setClientSecret(clientSecret); // Set client secret

                if (credential.getRefreshToken() != null) {
                    userCredentialsBuilder.setRefreshToken(credential.getRefreshToken());
                }
                
                UserCredentials credentials = userCredentialsBuilder.build();
                
                TranslationServiceSettings settings = TranslationServiceSettings.newBuilder()
                    .setCredentialsProvider(FixedCredentialsProvider.create(credentials))
                    .build();
                tempClient = TranslationServiceClient.create(settings);
            } catch (Exception e) {
                Platform.runLater(() -> mainViewController.addMessage("Error initializing Google Cloud Translation Service with Credential: " + e.getClass().getSimpleName() + ". Translation will be disabled."));
                System.err.println("Error initializing Google Cloud Translation Service with Credential:");
                e.printStackTrace();
            }
        } else {
            Platform.runLater(() -> mainViewController.addMessage("No Google Cloud Credential (or valid Access Token) provided. Translation will be disabled."));
        }
        this.client = tempClient;
    }

    public String translateText(String sourceText, String sourceLanguage) {
        if (this.client == null || sourceText == null || sourceText.trim().isEmpty() || TARGET_LANGUAGE.equalsIgnoreCase(sourceLanguage)) {
            return sourceText;
        }

        String cacheKey = sourceText + "::" + sourceLanguage;
        if (translationCache.containsKey(cacheKey)) {
            return translationCache.get(cacheKey);
        }

        if (UsageTracker.isTranslationLimitReached()) {
            Platform.runLater(() -> mainViewController.addMessage("Warning: Translation free tier limit reached for this month. Further translation requests are blocked."));
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

            UsageTracker.incrementTranslationCharacters(sourceText.length());

            if (UsageTracker.getTranslationUsagePercentage() >= 80 && UsageTracker.getTranslationUsagePercentage() < 100) {
                Platform.runLater(() -> mainViewController.addMessage(
                        String.format("Warning: Translation usage is at %.0f%% of the free tier limit (%d/%d characters). You may be billed soon.",
                                UsageTracker.getTranslationUsagePercentage(), UsageTracker.getTranslationCharacters(), UsageTracker.getTranslationFreeTierLimit())
                ));
            }

            if (!response.getTranslationsList().isEmpty()) {
                String translatedText = response.getTranslationsList().get(0).getTranslatedText();
                translationCache.put(cacheKey, translatedText);
                return translatedText;
            }
        } catch (Exception e) {
            System.err.println("Error during translation: " + e.getMessage());
            Platform.runLater(() -> mainViewController.addMessage("Error translating: " + e.getMessage()));
        }
        return sourceText;
    }

    public void shutdown() {
        if (client != null) {
            client.close();
        }
    }
}

