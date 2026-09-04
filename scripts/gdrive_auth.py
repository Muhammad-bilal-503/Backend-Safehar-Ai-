"""Run this ONCE, locally, on your own computer — not on Azure — to authorize
SafeHer AI's backend to use your Google Drive account for SOS evidence.

Setup before running:
1. Google Cloud Console (console.cloud.google.com) -> create/select a project.
2. "APIs & Services" -> "Enabled APIs" -> enable "Google Drive API".
3. "APIs & Services" -> "Credentials" -> "Create Credentials" -> "OAuth client ID"
   -> Application type "Desktop app" -> Create -> Download JSON.
4. Save that downloaded file as `client_secret.json` in this `scripts/` folder.
5. Install the auth library once: pip install google-auth-oauthlib
6. Run:  python scripts/gdrive_auth.py
   A browser window opens — sign in with the Google account whose Drive
   should store evidence folders, and click Allow.
7. This script prints a JSON blob at the end. Copy that ENTIRE blob and paste
   it as the value of the `GOOGLE_DRIVE_TOKEN_JSON` app setting in Azure
   (Configuration -> Application settings). Also paste the full contents of
   client_secret.json as `GOOGLE_DRIVE_CLIENT_JSON`.
"""
import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
HERE = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_PATH = os.path.join(HERE, "client_secret.json")


def main():
    if not os.path.exists(CLIENT_SECRET_PATH):
        raise SystemExit(
            f"Missing {CLIENT_SECRET_PATH}\n"
            "Download your OAuth client JSON from Google Cloud Console and save it there first."
        )

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
    creds = flow.run_local_server(port=0)

    token_json = creds.to_json()
    print("\n=== COPY EVERYTHING BELOW INTO THE AZURE 'GOOGLE_DRIVE_TOKEN_JSON' SETTING ===\n")
    print(token_json)
    print("\n=== END ===\n")

    with open(os.path.join(HERE, "token.json"), "w") as f:
        f.write(token_json)
    print(f"(Also saved a local copy to {os.path.join(HERE, 'token.json')} for reference.)")


if __name__ == "__main__":
    main()
