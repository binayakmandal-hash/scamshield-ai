# Connect Gmail

ScamShield reads your inbox through Google's official Gmail API. You create your own OAuth client in Google Cloud. It's free, takes about 10 minutes, and means no third-party server ever sees your mail.

> **Just want to try it?** The **Demo inbox** tab works without any of this.

## 1. Prepare your Google account

Google Cloud Console requires **2-Step Verification** on your Google account. If the console asks you to "enable MFA", turn it on at <https://myaccount.google.com/signinoptions/twosv>, then come back.

## 2. Pick a project and enable the Gmail API

1. Open <https://console.cloud.google.com/apis/library/gmail.googleapis.com>.
2. In the project picker at the top, choose a project or create a new one, such as `ScamShield`.
3. Click **Enable**.

## 3. Set up the consent screen

Open **Google Auth Platform** at <https://console.cloud.google.com/auth/overview>.

1. If it says the app isn't configured, click **Get started**:
   - **App name:** `ScamShield AI`; **support email:** yours
   - **Audience:** **External**
   - **Contact email:** yours, then agree and **Create**
2. Open **Audience** → **Test users** → **+ Add users** and add **every Gmail address that will connect**: yours, your teammates', and a judge's if they want to try it.

The app stays in **Testing** mode. That's normal for personal and hackathon projects, and it needs no Google review.

## 4. Create the OAuth client

1. **Clients** → **+ Create client**
2. **Application type:** Web application, **Name:** `ScamShield`
3. **Authorized redirect URIs** → **+ Add URI**, then paste exactly:
   ```
   http://127.0.0.1:5000/oauth2callback
   ```
4. Click **Create**.

## 5. Give ScamShield the credentials

Use either option.

**Option A: `.env`** (copy with the ⧉ icons; don't type them by hand)
```env
GOOGLE_CLIENT_ID=1234567890-abc...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...
```

**Option B: JSON file.** Download it (↓ icon next to the client secret), rename it to `client_secret.json`, and put it next to `app.py`. If the `.env` values are set, they take priority over the file.

Both `.env` and `client_secret.json` are git-ignored, so they will never be pushed.

## 6. Connect

1. Restart the app: `Ctrl+C`, then `python app.py`. The `.env` file is only read at startup.
2. Open **http://127.0.0.1:5000**. Use `127.0.0.1`, **not** `localhost`, so the redirect matches.
3. **Your inbox** → **Gmail** → **Connect Gmail** → choose your account.
4. Google shows **"Google hasn't verified this app"**. Click **Continue** (this is expected in Testing mode), then allow the permissions.

You'll return to ScamShield, which scans your inbox.

## Permissions ScamShield asks for

| Scope | Why |
|---|---|
| `gmail.modify` | Read inbox emails; move them to Spam or Trash and back (Undo) |
| `gmail.settings.basic` | Create a filter when you **Block** a sender, and remove it when you unblock |

ScamShield **never sends email** and **never permanently deletes** anything. **Disconnect** revokes the token at Google and deletes it from your computer.

## Troubleshooting

The reason for a failed sign-in appears in red on the page and as a `WARNING` line in the terminal.

| Message | Fix |
|---|---|
| `The provided client secret is invalid` | The secret in `.env` has a typo, space or quote. Copy it again with the ⧉ icon, or use **Add secret** to make a new one. Restart the app. |
| `redirect_uri_mismatch` | The URI in Google Cloud must be exactly `http://127.0.0.1:5000/oauth2callback`, and you must open the app at `127.0.0.1`. |
| `Access blocked: ... has not completed the Google verification process` | Add your Gmail address under **Audience → Test users**. |
| `The sign-in link expired` | You opened the app at `localhost` but the redirect went to `127.0.0.1`, or the app restarted mid-sign-in. Try again from `http://127.0.0.1:5000`. |
| Console asks to enable MFA | Turn on 2-Step Verification (step 1). |
| New client doesn't work yet | Google says changes can take up to 5 minutes. |
| Connected, but disconnected a week later | In Testing mode Google expires the sign-in after 7 days. Click **Connect Gmail** again. |
