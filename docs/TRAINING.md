# Training the learning model

ScamShield has a small machine-learning model that learns **what you consider a scam**. It adds one clearly labelled signal to the score, *"Similar to emails marked as scams"*, worth up to +20 points. The explainable checks always stay in charge.

## The model

- **Algorithm:** multinomial Naive Bayes with Laplace smoothing, written in plain Python in [`services/learner.py`](../services/learner.py), about 200 lines.
- **Features:**
  - words and word pairs (e.g. `share_otp`), including Hindi and Bengali script
  - signals such as "has a link", "mentions money" and "long number"
  - the sender's domain
- **Speed:** training takes milliseconds, so it retrains after **every** decision.
- **Evaluation:** 5-fold cross-validation, reporting accuracy, precision and recall (how many scams it catches). The results appear on the **Dashboard**.

## Where the training data comes from

| Source | How it's added | Weight |
|---|---|---|
| Built-in examples | [`services/seed_data.py`](../services/seed_data.py): 16 scam and 16 safe messages | 1× |
| Public datasets | `python train.py file.csv` | 1× |
| **Your decisions** | Spam, Block or Delete = scam; Safe = safe | **3×** |

Undo removes the example again. **Dashboard → Forget my feedback** clears all of your decisions.

## Train on a public dataset

Download a labelled CSV, for example:

- a **phishing email dataset** from Kaggle (columns `Email Text`, `Email Type`)
- the **SMS Spam Collection** from UCI or Kaggle (columns `v1` = ham/spam, `v2` = text)

Then run:

```bash
python train.py path/to/dataset.csv
```

It prints what it imported and how well the model does:

```
Using columns text='Email Text', label='Email Type'.
Importing N rows (N scam, N safe); skipped N unrecognised labels.
Training...
Trained on N examples, vocabulary N words.
Cross-validated accuracy XX%, precision XX%, recall XX% (on N examples).
Restart app.py to use the new model.
```

Your results depend on the dataset. Note the accuracy before and after training to show the improvement.

### Options

```bash
python train.py data.csv --text "Message" --label "Category"   # name the columns yourself
python train.py data.csv --limit 5000                           # use a random sample
python train.py --reset-dataset                                 # remove imported rows
```

**Recognised labels**

- **Scam:** `1`, `spam`, `phishing`, `phishing email`, `scam`, `fraud`, `smishing`, `malicious`
- **Safe:** `0`, `ham`, `safe`, `safe email`, `legit`, `legitimate`, `normal`

## Notes

- Imported text is stored in `database.db` with long numbers and email names masked.
- Seed and dataset examples are English-heavy. Your own Hindi and Bengali decisions are what teach it regional patterns.
- Large datasets make the model stronger, but your decisions still count 3× so it stays personal.
