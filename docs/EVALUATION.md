# Evaluation

How well do ScamShield's checks work? This page reports what was measured, how, and what the numbers can't tell you.

Run it yourself from the repo root:

```bash
python -m evaluation.evaluate_tools
```

## Read this first

- **The test cases are hand-written**, by the same person who wrote the rules. There is no public, labelled dataset of Indian WhatsApp scam chats, UPI requests or scam call transcripts to test against. Real-world accuracy will be lower than these numbers.
- **The sets are small** (12 to 24 cases per tool). One case is worth 4 to 8 percentage points, so treat every number as a rough indication.
- **Everything here is the offline rule engine**, with no AI model. The AI model can add a second opinion, but its answers are only accepted when its quotes are found word for word in the input.
- **Batch 1 is not a fair test.** Its first run found three bugs in the UPI check (listed below), which were fixed. Batch 1 now scores 100% on everything, which mainly shows that the fixes worked.
- **Batch 2 is the held-out set.** It was written after batch 1 and has never been used to change the rules. Its numbers are the ones to quote.

## Held-out results (batch 2)

| Tool | Cases | Catches scams | False alarms on normal input |
|---|---|---|---|
| Message analyzer (emails and SMS) | 12 scam, 12 safe | **11 of 12** (92%) | **0 of 12** |
| Chat check (scam script tracker) | 10 scam chats, 5 normal | **7 of 10** (70%), all 7 with the right script | **0 of 5** |
| UPI check | 6 tricks, 6 other | **5 of 6** (83%) | **0 of 6** |
| Call copilot | 7 scam calls, 5 normal | **7 of 7** | **0 of 5** |

The message analyzer's precision on this set was 11 of 11: everything it flagged was a scam.

### What it missed, and why

| Tool | Missed case | Why |
|---|---|---|
| Message analyzer | "Hi mom, this is my new number, my phone broke. Can you send 20000 urgently?" | Scored 20, just under the 25 threshold. Family-impersonation messages have no link, brand or OTP to anchor on. |
| Chat check | Bank of Baroda KYC message with a `bit.ly` link | The link has no `http://`, so the "rushed to a link" step wasn't seen, and one step alone isn't enough for a match. |
| Chat check | FedEx customs-fee message | "Shipment is held at customs" isn't one of the parcel script's phrasings, so only one step was seen. |
| Chat check | Marketplace buyer sending a QR, in one message | Only one step ("scan it to receive") matched. The tracker needs two steps before naming a script. |
| UPI check | "Scan this qr code, it will credit 500 rs cashback into ur account" | "Credit … into your account" isn't covered by the receive-trick wording yet. |

Requiring two steps before naming a script is deliberate: it keeps false alarms on normal chats at zero, at the cost of missing very short scam chats. For those, the main message analyzer still runs on any message you paste.

## Bugs found by batch 1 (fixed)

1. "Install AnyDesk … pay Rs 10" with no UPI ID was reported as "no payment found". A screen-sharing request now counts as a payment risk.
2. "Kiran Traders has requested Rs 1,200 … on Google Pay" was flagged as impersonating Google Pay. Naming the payment app being used no longer counts as claiming to be that company.
3. `hr@company.com` was read as a UPI ID. Email addresses are now excluded.

## Unit tests

`python -m unittest discover -s tests` runs 75 tests covering the analyzers, the safety tools (including QR decoding of generated images and a WhatsApp `.zip` export), the API and the pages. They run without an AI model or internet access, and on every push in GitHub Actions.

## The learning model

The per-user Naive Bayes model that learns from your Spam/Safe decisions reports its own 5-fold cross-validated accuracy, precision and recall on the Dashboard, computed live on your own feedback. See [TRAINING.md](TRAINING.md).
