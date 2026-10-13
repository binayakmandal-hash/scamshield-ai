# Changelog

## [1.2.0] - 2026-10-13

### Added
- **Chat check**: a scam script tracker. Matches a pasted chat or WhatsApp export (`.txt` / `.zip`) against 9 scam scripts, shows the step reached and the scammer's next move. The AI model's answer is only used when its quotes appear word for word in the chat.
- **UPI check**: decodes UPI QR codes (OpenCV) and payment-request screenshots and explains which way the money moves, in English, Hindi or Bengali.
- **On a call**: a call copilot that warns about pressure tactics live, using the browser's speech recognition. Includes a practice call and a one-tap family contact.
- **I already paid**: a golden-hour checklist with a timer, and a complaint drafted from the payment receipt.
- **Simple mode** for parents and grandparents, and the "evidence board" redesign with highlighted quotes and margin notes.
- Privacy policy and terms pages.
- `evaluation/`: held-out test cases and `docs/EVALUATION.md` with measured results.

### Fixed
- An email address was read as a UPI ID; naming the payment app ("on Google Pay") was treated as impersonating it; a screen-sharing request with no UPI ID was reported as "no payment found".

## [1.1.0] - 2026-10-03

### Added
- **Render deployment** with a `render.yaml` blueprint and gunicorn; see `docs/DEPLOY_RENDER.md`
- **Public mode** (`PUBLIC_MODE=true`): each visitor gets a private session with their own Gmail sign-in, history, learning, sender rules and demo inbox
- Per-visitor AI rate limit (`AI_REQUESTS_PER_HOUR`) to protect the API quota
- Automatic upgrade of databases created by v1.0 (no data lost)
- Tests for visitor isolation and database migration (42 tests in total)

## [1.0.0] - 2026-10-03

First public release, built during Hacktoberfest 2026.

### Added
- **Gmail inbox scanning** with Google OAuth: score your latest 10-50 emails
- **Actions with Undo:** Spam, Block sender (Gmail filter), Delete (to Trash), Mark safe, and "Move all risky to Spam"
- **Learning model:** Naive Bayes that retrains after every decision, with cross-validated accuracy on the Dashboard
- `train.py` to train on public phishing or spam datasets (CSV)
- **Sender verification** using Gmail's SPF / DKIM / DMARC results, plus trusted senders
- Real link destinations behind HTML buttons are analysed (links are never opened)
- **Evidence highlighting** and a transparent score built from named signals
- Validation of AI output: quotes checked against the email, score rebuilt from evidence
- **Gemma 4** (open weights) via Google AI Studio or local Ollama, with a rule-engine fallback
- **Send to family** notes, *Explain like I'm 12*, a 3-step action plan, and follow-up chat
- English, Hindi and Bengali explanations
- Screenshot analysis for WhatsApp and SMS scams
- **Demo inbox** with 10 sample emails
- History, dashboard, and Material-style light and dark themes
- 39 automated tests and GitHub Actions CI

### Changed
- Removed the copy-paste text box; the inbox and screenshots are now the inputs

### Fixed
- "Never share your OTP" and OTP notifications no longer count as requests for an OTP
- Free email providers (gmail.com, outlook.com) are never treated as verified senders
- Sign-in errors are now shown on the page instead of being hidden
