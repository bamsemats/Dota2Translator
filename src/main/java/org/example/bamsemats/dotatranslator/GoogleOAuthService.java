package org.example.bamsemats.dotatranslator;

import com.google.api.client.auth.oauth2.Credential;
import com.google.api.client.extensions.java6.auth.oauth2.AuthorizationCodeInstalledApp;
import com.google.api.client.extensions.jetty.auth.oauth2.LocalServerReceiver;
import com.google.api.client.googleapis.auth.oauth2.GoogleAuthorizationCodeFlow;
import com.google.api.client.googleapis.auth.oauth2.GoogleClientSecrets;
import com.google.api.client.googleapis.javanet.GoogleNetHttpTransport;
import com.google.api.client.http.HttpTransport;
import com.google.api.client.json.JsonFactory;
import com.google.api.client.json.gson.GsonFactory;
import com.google.api.client.util.store.FileDataStoreFactory;
import com.google.auth.oauth2.AccessToken;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.security.GeneralSecurityException;
import java.util.Collections;
import java.util.List;

public class GoogleOAuthService {

    private static final String APPLICATION_NAME = "Dota2ChatTranslator";
    private static final JsonFactory JSON_FACTORY = GsonFactory.getDefaultInstance();
    private static final List<String> SCOPES = Collections.singletonList("https://www.googleapis.com/auth/cloud-platform"); // Broad scope for Vision and Translate
    private static final String TOKENS_DIRECTORY_PATH = "tokens"; // Directory to store user's refresh token
    private static final String CLIENT_SECRET_FILE = "/client_secret.json"; // Path to client_secret.json in resources

    private HttpTransport HTTP_TRANSPORT;
    private FileDataStoreFactory DATA_STORE_FACTORY;
    private GoogleClientSecrets clientSecrets; // Store client secrets
    private String clientId;
    private String clientSecret;


    public GoogleOAuthService() throws GeneralSecurityException, IOException {
        HTTP_TRANSPORT = GoogleNetHttpTransport.newTrustedTransport();
        DATA_STORE_FACTORY = new FileDataStoreFactory(new File(TOKENS_DIRECTORY_PATH));

        // Load client secrets in constructor
        InputStream in = GoogleOAuthService.class.getResourceAsStream(CLIENT_SECRET_FILE);
        if (in == null) {
            throw new IOException("Client secret file " + CLIENT_SECRET_FILE + " not found in resources.");
        }
        clientSecrets = GoogleClientSecrets.load(JSON_FACTORY, new InputStreamReader(in));
        
        // Store client ID and secret
        if (clientSecrets.getDetails() != null) {
            this.clientId = clientSecrets.getDetails().getClientId();
            this.clientSecret = clientSecrets.getDetails().getClientSecret();
        } else {
            throw new IOException("Client secret file " + CLIENT_SECRET_FILE + " is missing client ID or client secret details.");
        }
    }

    /**
     * Authorizes the user and returns a Credential object.
     * If a refresh token is available, it will be used to refresh the access token.
     * Otherwise, it will initiate a new authorization flow, opening a browser window.
     * @return Credential object containing access token, refresh token, etc.
     * @throws IOException
     * @throws GeneralSecurityException
     */
    public Credential authorize() throws IOException, GeneralSecurityException {
        // Build flow and trigger user authorization request.
        GoogleAuthorizationCodeFlow flow = new GoogleAuthorizationCodeFlow.Builder(
                HTTP_TRANSPORT, JSON_FACTORY, clientSecrets, SCOPES) // Use stored clientSecrets
                .setDataStoreFactory(DATA_STORE_FACTORY)
                .setAccessType("offline") // Required to get a refresh token
                .build();

        // Authorize the user. This will open a browser window if needed.
        // It will also handle token storage and refreshing.
        Credential credential = new AuthorizationCodeInstalledApp(flow, new LocalServerReceiver()).authorize("user");
        
        System.out.println("Credentials saved to " + TOKENS_DIRECTORY_PATH);
        return credential;
    }

    /**
     * Retrieves the last known authorized credential without re-authorizing the user.
     * Useful for checking if a user is already authenticated.
     * @return Credential object if found, null otherwise.
     * @throws IOException
     * @throws GeneralSecurityException
     */
    public Credential getStoredCredential() throws IOException, GeneralSecurityException {
        GoogleAuthorizationCodeFlow flow = new GoogleAuthorizationCodeFlow.Builder(
                HTTP_TRANSPORT, JSON_FACTORY, clientSecrets, SCOPES) // Use stored clientSecrets
                .setDataStoreFactory(DATA_STORE_FACTORY)
                .setAccessType("offline")
                .build();
        
        return flow.loadCredential("user");
    }

    public String getClientId() {
        return clientId;
    }

    public String getClientSecret() {
        return clientSecret;
    }
}
