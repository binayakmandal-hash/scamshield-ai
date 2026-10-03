# Deploy to Render

This puts ScamShield online at `https://<your-app>.onrender.com` on Render's free plan. The repo includes a [`render.yaml`](../render.yaml) blueprint, so most settings are filled in for you.

> **Public mode is on for deployments.** Every visitor gets a private session with their own Gmail sign-in, history, learning and demo inbox. Nobody can see anyone else's emails. AI calls are limited to 60 per visitor per hour so your API quota is protected.

## 1. Push the latest code

```bash
git add .
git commit -m "Add Render deployment"
git push
```

## 2. Create the service on Render

1. Open <https://dashboard.render.com> → **New** → **Blueprint**.
2. Connect GitHub if asked, then pick the **scamshield-ai** repository.
3. Render reads `render.yaml` and asks for the secret values:

| Key | Value |
|---|---|
| `OPENAI_API_KEY` | Your Google AI Studio key (for Gemma 4) |
| `GOOGLE_CLIENT_ID` | From Google Cloud → Clients → ScamShield |
| `GOOGLE_CLIENT_SECRET` | Same client (copy with the ⧉ icon) |
| `GMAIL_REDIRECT_URI` | `https://scamshield-ai.onrender.com/oauth2callback` (fix it in step 3 if Render gives a different URL) |

4. Click **Apply**. The first build takes 2–4 minutes. When it says **Live**, open the URL at the top of the service page.

**No Blueprint?** Use **New → Web Service** instead, choose the repo, and set:
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn app:app --workers 1 --threads 8 --timeout 180 --bind 0.0.0.0:$PORT`
- **Environment:** add the variables from `render.yaml`, including `PUBLIC_MODE=true` and a long random `SECRET_KEY`.

## 3. Allow Gmail sign-in on the live URL

1. Copy your live URL from Render, e.g. `https://scamshield-ai-x1y2.onrender.com`.
2. In **Render → your service → Environment**, set `GMAIL_REDIRECT_URI` to that URL plus `/oauth2callback`, then **Save**. Render redeploys automatically.
3. In **Google Cloud → Google Auth Platform → Clients → ScamShield → Authorized redirect URIs**, click **+ Add URI** and add the same address:
   ```
   https://scamshield-ai-x1y2.onrender.com/oauth2callback
   ```
   Keep the `http://127.0.0.1:5000/oauth2callback` entry too, so local use keeps working. Click **Save**; it can take a few minutes to apply.
4. In **Audience → Test users**, add the Gmail address of anyone who should be able to connect, such as teammates and judges.

## 4. Check it

- The **Demo inbox** loads and scans.
- The pill at the top right shows `gemma-4-26b-a4b-it`.
- **Gmail → Connect Gmail** returns to the site and lists your inbox.
- `https://<your-app>.onrender.com/api/health` shows `"ai_ready": true`.

## Free-plan behaviour

| What happens | Effect | Option |
|---|---|---|
| The service sleeps after ~15 minutes without visitors | The first visit afterwards takes about a minute | Open the site a few minutes before a demo |
| The disk is temporary | History, learning and Gmail sign-ins reset on each deploy or restart | Paid plan: add a persistent disk and set `DATABASE_PATH=/var/data/database.db`, `TOKENS_DIR=/var/data/tokens` |

## Troubleshooting

| Problem | Fix |
|---|---|
| Build fails on a package | Make sure `PYTHON_VERSION` is `3.12.7` in Environment |
| `redirect_uri_mismatch` | `GMAIL_REDIRECT_URI` on Render and the URI in Google Cloud must match exactly, with `https://` and no trailing slash |
| `Access blocked` | Add the Gmail address under **Audience → Test users** |
| Sign-in returns but isn't connected | Check Render's **Logs** for the `WARNING` line, e.g. an invalid client secret |
| Pill says "Offline rule engine" | Check `AI_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` and `OPENAI_MODEL` |
| "hourly limit" message | Raise `AI_REQUESTS_PER_HOUR` in Environment |

## Before a real public launch

Testing-mode OAuth limits Gmail sign-in to your listed test users, which is ideal for demos. To let anyone sign in, Google requires app verification, and because `gmail.modify` is a restricted scope, that includes a security assessment. Also add proper accounts, persistent storage and monitoring. See [PRIVACY.md](PRIVACY.md).
