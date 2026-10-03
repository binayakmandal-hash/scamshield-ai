# Demo guide

## Before judging (10 minutes)

1. `python app.py`, then open **http://127.0.0.1:5000** (use 127.0.0.1, not localhost).
2. **Gmail:** if `client_secret.json` is set up (README → Connect Gmail), connect your account now, not in front of judges. Send yourself 2–3 scam-style test emails from another account, using the demo inbox emails as templates, so your real inbox has something to catch.
3. **Backup:** the **Demo inbox** tab works with no internet and no Google account. If sign-in or Wi-Fi fails, switch to it and keep going.
4. Optional, for a stronger model: `python train.py dataset.csv` with a phishing-email CSV, then restart.
5. Zoom the browser to 110%.

## Demo flow (about 3 minutes)

| # | Action | What to say |
|---|---|---|
| 1 | Show the inbox: scored emails, risky ones on top in red | "ScamShield scanned my latest emails. The SBI 'account blocked' email is very high risk, and my real HDFC OTP email is low." |
| 2 | Point at the **HDFC** row | "It's not just keyword matching. That email mentions an OTP too, but it says *never share* your OTP, and Gmail verified it really came from hdfcbank.com." |
| 3 | Open the **SBI** email | Highlights: urgency, the request for account number and OTP. "Claims to be SBI but writes from Gmail." The link shows the **real destination behind the button**: a .xyz look-alike that ScamShield never opened. |
| 4 | **How the score was built** | "Every point is explained, including one from our learning model." |
| 5 | **Send to family** in हिन्दी | The note you'd forward to a parent. |
| 6 | Back to inbox, click **Spam** on the SBI email, then **Undo**, then **Spam** again | "Everything is reversible. And it just learned from that decision." |
| 7 | **Move all risky emails to Spam** | One click cleans the inbox. |
| 8 | Click **Safe** on a borderline email | "If it's wrong, I correct it, and it trusts that sender from now on." |
| 9 | Click **Scan inbox** again | Scores have shifted from what it learned. |
| 10 | **Dashboard → What ScamShield has learned** | Training examples, your decisions, cross-validated accuracy, trusted and blocked senders. |
| 11 | Screenshot tab (optional) | A WhatsApp scam screenshot, read automatically. |

## 2-minute script

> **(0:00 – Problem)**
> Scam emails like *"Your SBI account will be blocked in 30 minutes, verify now"* reach every inbox, and the people we love click them. Spam filters miss them, and when they do catch one, they never tell you *why*.
>
> **(0:20 – Product)**
> ScamShield AI connects to Gmail, scores every email, and explains the warning signs. *[Show inbox.]* The fake SBI alert is at the top, very high risk. My real HDFC OTP email is low risk. It mentions an OTP too, but it says *never share it*, and Gmail confirms it really came from hdfcbank.com.
>
> **(0:45 – Explain)**
> *[Open the SBI email.]* Every warning sign is highlighted: time pressure, a request for my account number and OTP. It claims to be SBI but comes from a Gmail address, and the button hides a .xyz look-alike link, which we found without ever opening it. The score is the sum of these signals, so nothing is a black box.
>
> **(1:10 – Act and learn)**
> *[Click Spam, then "Move all risky to Spam".]* One click moves scams out, and everything can be undone. Each decision trains our learning model. *[Dashboard.]* Here's what it has learned and how accurate it is, measured with cross-validation. If it's ever wrong, I mark the email safe and it adapts.
>
> **(1:40 – How it's built, close)**
> Flask, Gmail's official API with OAuth, Gemma 4 for explanations, and a Naive Bayes model we wrote ourselves that learns from you. Don't trust the message. Understand it.

## Likely questions

- **"Is my Gmail safe with this?"** Google's official OAuth. The token stays on this computer, Disconnect revokes it, it never sends email, and deletes go to Trash, not permanent.
- **"How does it learn?"** A multinomial Naive Bayes classifier on words and word pairs. Your decisions count 3x, and it retrains in milliseconds after each one. It can also be trained on public datasets with `train.py`.
- **"Why not just use Gmail's spam filter?"** We complement it: we explain *why*, in Hindi and Bengali too, catch personal-targeted scams that slip through, and learn your own definition of a scam.
- **"Accuracy?"** Shown live on the dashboard with 5-fold cross-validation. It rises with more data and feedback.
