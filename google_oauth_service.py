import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Scopes required for Google Cloud Vision and Translation APIs
SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

# Path to the client secrets file
CLIENT_SECRETS_FILE = 'client_secret.json'

# Directory to store user's tokens
TOKEN_STORAGE_DIR = 'tokens'
TOKEN_FILE = os.path.join(TOKEN_STORAGE_DIR, 'token.json')

class GoogleOAuthService:
    def __init__(self, update_notification_callback=None):
        self.credentials = None
        self.update_notification_callback = update_notification_callback
        os.makedirs(TOKEN_STORAGE_DIR, exist_ok=True) # Ensure token directory exists

    def _update_notification(self, message):
        if self.update_notification_callback:
            self.update_notification_callback(message)
        else:
            print(message)

    def authorize(self):
        """
        Authorizes the user and returns Credentials.
        If a refresh token is available, it will be used to refresh the access token.
        Otherwise, it will initiate a new authorization flow, opening a browser window.
        """
        self.credentials = None

        # Load existing credentials if available
        if os.path.exists(TOKEN_FILE):
            try:
                self.credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
                self._update_notification("Loaded existing credentials.")
            except Exception as e:
                self._update_notification(f"Error loading existing credentials: {e}. Re-authorizing.")
                self.credentials = None # Invalidate credentials if loading fails

        # If credentials are not valid or don't exist, initiate the flow
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self._update_notification("Refreshing access token...")
                try:
                    self.credentials.refresh(Request())
                    self._update_notification("Access token refreshed.")
                except Exception as e:
                    self._update_notification(f"Error refreshing token: {e}. Re-authorizing.")
                    self.credentials = None # Invalidate if refresh fails
            
            if not self.credentials or not self.credentials.valid:
                # Flow for desktop application
                self._update_notification("Initiating new OAuth authorization flow...")
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                self.credentials = flow.run_local_server(port=0) # port=0 lets OS pick a free port
                self._update_notification("Authorization successful.")

        # Save credentials for the next run and print authorized email
        if self.credentials and self.credentials.valid:
            if self.credentials.id_token:
                try:
                    import jwt
                    decoded_token = jwt.decode(self.credentials.id_token, options={"verify_signature": False})
                    user_email = decoded_token.get('email')
                    if user_email:
                        self._update_notification(f"Authorized as: {user_email}")
                    else:
                        self._update_notification("Authorized, but email not found in token.")
                except ImportError:
                    self._update_notification("Authorized. Install 'PyJWT' for email logging if needed.")
                except Exception as e:
                    self._update_notification(f"Error decoding ID token: {e}")
            else:
                self._update_notification("Authorized. No ID token available to get email.")

            with open(TOKEN_FILE, 'w') as token:
                token.write(self.credentials.to_json())
            self._update_notification("Credentials saved.")
        
        return self.credentials

    def get_credentials(self):
        return self.credentials
