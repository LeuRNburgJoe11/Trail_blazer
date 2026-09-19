# Judge-facing demo assets

`assets/door/normal_reference.json` is generated from the official labelled Door
training stream by `app/railpulse/scripts/build_door_reference.py`.

`assets/rail/v0_baseline/{model.joblib,metadata.json}` is the nested dashboard Rail
pipeline trained on official training files, with file-level 5-fold validation.
It is NOT the canonical Rail artifact. Metadata includes the feature schema,
validation and artifact checksum. No held-out labels are used. Load only trusted
artifacts; joblib can execute code.

The cloud image copies these assets to its private registry at build time and
fails its preflight if required files are absent. They are not web-accessible.
Raw training data, feature caches and user recordings are not included here.

Reproduce from the repository root (with prepared official training data):

```bash
.venv/bin/python app/railpulse/scripts/build_door_reference.py --output deploy/assets/door/normal_reference.json
cd app/railpulse
PYTHONPATH=src ../../.venv/bin/python scripts/extract_rail_features.py --data-dir ../../data/Rail_Corrugation/Train --output rail_features_train.csv
PYTHONPATH=src ../../.venv/bin/python scripts/train_rail.py --feature-cache rail_features_train.csv --labels ../../data/Rail_Corrugation/Train_Labels.csv --registry-dir ../../deploy/assets
```
