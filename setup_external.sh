#!/bin/bash

# Script to clone necessary external modules for the Infra AI project
mkdir -p external_modules
cd external_modules

echo "Cloning external modules..."

git clone https://github.com/jayant1211/Image-Tampering-Detection-using-ELA-and-Metadata-Analysis.git
git clone https://github.com/loft-br/xgboost-survival-embeddings.git
git clone https://github.com/datadrivenconstruction/OpenConstructionERP.git
git clone https://github.com/NielsRogge/Transformers-Tutorials.git
git clone https://github.com/Ansarimajid/Construction-PPE-Detection.git
git clone https://github.com/Yashsonaar/LayoutLMv3-Fine-Tuning.git
git clone https://github.com/sutanmufti/leaflet-dashboard.git

echo "All external modules cloned successfully."
