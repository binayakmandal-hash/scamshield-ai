# Contributing to ScamShield AI

Thanks for helping people spot scams. Every contribution is welcome, from fixing a typo in a Bengali template to adding a new URL check.

## Quick setup

```bash
git clone https://github.com/binayakmandal-hash/scamshield-ai.git
cd scamshield-ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -m unittest discover -s tests -t .           # tests need no AI model or internet
python app.py
```

You don't need a GPU or Ollama to contribute. With `AI_PROVIDER=none`, the app runs on the built-in rule engine.

## Good places to start

Look for issues labelled **good first issue** or **help wanted**. Some ideas that are always useful:

- **Add a brand** that scammers imitate (with its official domains) to `services/brands.py`.
- **Improve rule-engine patterns** in `services/rule_engine.py`, especially Hindi, Bengali and Hinglish phrases. Add a test with a realistic example message.
- **Report a wrong result** using the "Wrong analysis" issue template. Remove personal details first.
- **Translate** the family-note templates into another Indian language.

## How to make a change

1. Open or comment on an issue first for anything bigger than a small fix, so we can agree on the approach.
2. Keep each pull request focused on **one problem**.
3. For logic changes, **add or update a test** that fails before your change and passes after it.
4. Run the tests: `python -m unittest discover -s tests -t .`
5. Fill in the pull request template.

## Project rules

These keep ScamShield safe and honest. Pull requests that break them can't be merged.

- **Never open links from messages.** URL checks work on the text only: no fetching, resolving or redirects.
- **No certainty claims.** Write "shows signs commonly associated with", never "is definitely a scam" or "is safe".
- **Evidence must come from the message.** Don't add features that show quotes or facts the user didn't provide.
- **Open-weight models only.** The AI core uses open-weight models (Gemma 4 by default). Don't add a dependency on a closed, proprietary AI API.
- **Privacy first.** Don't store screenshots, and don't log message content.
- **No real personal data in tests or issues.** Use made-up numbers, names and domains.

## AI-use policy

You may use AI coding tools. If you do:

- You must **review, run and understand** every line you submit. You should be able to explain any part of your change if asked.
- Tick the AI-use box in the pull request template.
- Don't submit bulk, low-effort or auto-generated pull requests (for example, mass whitespace or typo changes). They will be closed and may be labelled `spam` or `invalid`.

## A note on Hacktoberfest 2026

This repository has the `hacktoberfest` topic and welcomes contributors during October. In 2026, Hacktoberfest rewards come from its activities, DEV challenges and events, and **pull requests no longer count toward rewards**. So please contribute because you want to improve the project, not to reach a PR count. Spammy pull requests will be closed.

## Code style

- Python: PEP 8, small functions, docstrings for anything non-obvious. No new dependencies without discussion.
- JavaScript: plain browser JS, no build step. Insert user content with `textContent`, never `innerHTML`.
- CSS: use the colour tokens in `:root` and check both light and dark themes.

## Code of conduct

By taking part you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).
