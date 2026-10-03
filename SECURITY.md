# Security Policy

ScamShield handles messages that may contain personal details, so security reports are taken seriously.

## Reporting a vulnerability

Please **don't open a public issue**. Report it privately through
[GitHub security advisories](https://github.com/binayakmandal-hash/scamshield-ai/security/advisories/new)
or by email to **[your contact email]**. Include the steps to reproduce it and what an attacker could do.

You should get a reply within a week.

## Scope

Especially important:

- Any way to make ScamShield fetch, open or resolve a URL from a message
- Script injection through message text, screenshots or AI output
- Personal data stored or logged when it shouldn't be
- Prompt injection that makes the AI tell users to click links, pay or share codes

## Deployment note

ScamShield is designed to run locally. Before putting it on the public internet, add authentication, rate limiting and CSRF protection, and set a strong `SECRET_KEY`.
