# Changelog

## [1.0.0] — 2026-10-03

First public release, built during Hacktoberfest 2026.

### Added
- **Gmail inbox scanning** with Google OAuth: score your latest 10–50 emails
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
