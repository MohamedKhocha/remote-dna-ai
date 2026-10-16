# Threat model

What could go wrong with the Remote DNA model and the way the app uses it,
worked through with STRIDE. Scope: this repository, the exported model file,
and the code in the app that runs it.

## Assets

- **The user's TV and their trust in the app.** A wrong code can switch the TV
  off or change its input in the middle of a session.
- **The user's privacy.** Which TV they own and which codes it answers to.
- **The integrity of the model.** Its settings and the catalogue it reasons
  from.
- **This repository**, published for evaluation.

## STRIDE

| Threat | What it would look like here | What stops it |
|---|---|---|
| **Spoofing** | A fake model file passed off as ours | The app does not download models. The file is bundled at build time, so replacing it means shipping a new app through Google Play. A future remote update would have to be signed and checked on the phone, with the bundled copy as fallback |
| **Tampering** | Someone changes the catalogue or the settings so the model favours harmful codes | `catalogue_sha256` in the exported file, and the app's test checks its catalogue has the same hash. The parity tests fail if the phone's numbers drift from the Python's. Changes go through commits and CI |
| **Repudiation** | Not knowing which model a given app version runs | The exported file names the commit it came from and the catalogue hash |
| **Information disclosure** | Codes or device details leaving the phone | The model runs on the phone with no network call. The training data contains no user data. Secret scanning and push protection are on for this repository, which holds no keys at all |
| **Denial of service** | The model making a session hang or crash the app | Work per answer is bounded by the catalogue size. Any exception leaves the usual order in place. Sessions give up after 300 questions in the simulation; in the app the user can stop at any time |
| **Elevation of privilege** | The model doing more than suggest an order | It only reorders codes the app was going to try anyway. Power and source codes, as known for that address, are never moved forward. Nothing is saved unless the user confirmed it |

## Data poisoning, later

Today the model learns from the published catalogue only. If confirmed remotes
from users are added later, a few false contributions could steer it. The plan
for that day: train offline, use only remotes confirmed by a minimum number of
different contributors (the app's backend already applies such a threshold to
its community catalogue), and keep the bundled model as the reviewed baseline.

## What is not covered

The app's other features, its backend and its payment flow are outside this
repository and have their own review.
