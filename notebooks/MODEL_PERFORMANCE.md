# Model Performance Summary – Crop, Fertilizer & Disease Models

This document summarizes the empirical performance of the models trained in the project’s Kaggle-style notebooks and explicitly states **which models are wired into the current backend agents and REST endpoints**.

- Crop recommendation notebook: `CROP-RECOMMENDATION.ipynb`
- Fertilizer recommendation notebook: `fertilizer-recommendation.ipynb`
- Plant disease classification notebook: `plant-disease-classification-resnet-99-2.ipynb`

Backend consumers:
- Crop models are used by `CropAgent` and the `/crop_predict/predict` API.
- Fertilizer models are used by `FertilizerAgent` and the `/fertilizer_predict/predict` API.
- Disease models are used by `DiseaseDetectionAgent` and the `/crop_disease` APIs (see section 3 for PyTorch vs TensorFlow usage).

---

## 1. Crop Recommendation Notebook (`CROP-RECOMMENDATION.ipynb`)

### 1.1 Dataset

- **Source**: Kaggle Crop Recommendation Dataset
- **File**: `Crop_recommendation.csv`
- **Rows**: 2,200
- **Features (7 numeric)**:
  - `N`, `P`, `K` (soil macronutrients)
  - `temperature`, `humidity`, `ph`, `rainfall`
- **Target**: `label` (22 crop classes, each with 100 examples)

### 1.2 Models evaluated

Train–test split: `train_test_split(test_size=0.2, random_state=42)`.
Additional metric: 10-fold cross-validation on the full dataset.

| Model                   | Test accuracy (hold‑out) | 10‑fold CV mean accuracy | Notes |
|-------------------------|--------------------------:|--------------------------:|-------|
| Decision Tree (entropy, max_depth=5) | **86.59%** | **92.23%** | `DecisionTreeClassifier(criterion='entropy', max_depth=5, random_state=42)` |
| Gaussian Naive Bayes    | **99.55%**               | **99.50%**               | `GaussianNB()` – best performer, near-perfect generalization |
| SVM (`SVC(gamma='auto')`) | **9.09%**               | **29.00%**               | Extremely poor; notebook explicitly says to *ignore* this model |
| Logistic Regression     | **94.55%**               | **96.05%**               | Multiclass `LogisticRegression(random_state=2)` |
| Random Forest           | **99.32%**               | **99.41%**               | `RandomForestClassifier(n_estimators=20, random_state=0)` |

The notebook prints final per‑model accuracies (test split):

```text
Decision Tree --> 0.8659
Naive Bayes --> 0.99545
SVM --> 0.09091
Logistic Regression --> 0.94545
RF --> 0.99318
```

Multiple models are pickled (`DecisionTree.pkl`, `NBClassifier.pkl`, `LogisticRegression.pkl`, `RandomForest.pkl`), but SVM is explicitly discarded.

### 1.3 Model actually used by the agents

The production code makes it very clear which crop model is consumed:

- **Tool**: `backend/tools/crop_recommendation_tool.py`
  - Loads **`models/NBClassifier.pkl`**:
    - `MODEL_PATH = ... / "models" / "NBClassifier.pkl"`
  - Docstring: *"Recommends ... using a Naive Bayes classifier. Model: NBClassifier.pkl"*.
  - Uses `crop_model.predict` and `crop_model.predict_proba` to produce top‑N crop recommendations.

- **Agent**: `backend/agents/crop_agent.py`
  - Class `CropAgent` is a `ToolAgent` with `tool_callable=recommend_crop`.
  - The docstring states: *"handles crop recommendation queries using the Naive Bayes model through the crop_recommendation_tool"*.

- **REST endpoint**: `backend/routers/crop_predict.py`
  - Loads exactly the same Naive Bayes pickle:
    - `MODEL_PATH = ... / "models" / "NBClassifier.pkl"`
  - `/crop_predict/predict` uses this `model.predict(...)` to return `predicted_crop`.

#### ✅ Final choice for crop recommendation (agents & API)

- **Chosen model**: **Gaussian Naive Bayes**
- **Serialized artifact**: `models/NBClassifier.pkl`
- **Performance (from notebook)**:
  - Hold‑out test accuracy: **99.55%**
  - 10‑fold CV mean accuracy: **99.50%**
- **Used by**:
  - `CropAgent` (LangGraph multi‑agent pipeline) via `crop_recommendation_tool.recommend_crop`
  - `/crop_predict/predict` FastAPI route

Random Forest is also very strong but is not wired into the current agents; Naive Bayes is the canonical model everywhere in the backend.

---

## 2. Fertilizer Recommendation Notebook (`fertilizer-recommendation.ipynb`)

### 2.1 Dataset

- **Source**: Kaggle Fertilizer Prediction dataset
- **File**: `Fertilizer Prediction.csv`
- **Features**:
  - Continuous: `Temparature`, `Humidity`, `Moisture`, `Nitrogen`, `Phosphorous`
  - Categorical: `Soil Type`, `Crop Type`
- **Target**: `Fertilizer Name` (7 classes: `Urea`, `DAP`, `14-35-14`, `28-28`, `17-17-17`, `20-20`, `10-26-26`)

After label encoding of categorical features, the data splits into:

- Train: 79 rows, Test: 20 rows (`train_test_split(test_size=0.2, random_state=0)`).

### 2.2 Models evaluated in the notebook

#### k‑Nearest Neighbors (via pipeline)

- Pipeline: `StandardScaler()` + `KNeighborsClassifier(k)` for k = 1..49.
- The notebook prints accuracy on the 20‑sample test set for each k:
  - Test accuracy ranges roughly from **35% to 75%** across k.
  - **Best observed test accuracy**:
    - **75% at k = 1** (error rate 0.25), reported as:
      - *"Minimum error: 0.25 at K = 1"*.

#### SVM pipeline

- Pipeline: `StandardScaler()` + `SVC(probability=True)`.
- Reported metrics:
  - **Test accuracy (20‑sample hold‑out)**: **80.0%**
  - **Whole dataset accuracy** (fit then predict on full data): **92.93%**
  - Confusion matrices are plotted for both test and full data.

#### XGBoost pipeline

- Pipeline: `StandardScaler()` + `XGBClassifier(random_state=18)`.
- Reported metrics:
  - **Test accuracy (20‑sample hold‑out)**: **95.0%**
  - **Whole dataset accuracy**: **98.99%**
  - Confusion matrices are again plotted for test and full data.

These XGBoost results are the **best** among the evaluated models in the notebook.

### 2.3 Models actually used by the agents

The backend again makes the choice explicit.

- **Tool**: `backend/tools/fertilizer_tool.py`
  - Loads an XGBoost pipeline and fertilizer label mapping lazily:
    - `model_path = backend_dir / "models" / "xgb_pipeline.joblib"`
    - `dict_path = backend_dir / "models" / "fertname_dict.joblib"`
  - `_xgb_model = joblib.load(model_path)`
  - `_fert_dict = joblib.load(dict_path)` (maps numeric codes → fertilizer names)
  - Core function `predict_fertilizer_core(...)`:
    - Encodes `soil_type` and `crop_type` using `SOIL_TYPE_ENCODING` and `CROP_TYPE_ENCODING`.
    - Builds feature vector `[Temperature, Humidity, Moisture, SoilTypeCode, CropTypeCode, Nitrogen, Phosphorous, Potassium]`.
    - Calls `xgb_model.predict(...)` to get the fertilizer class code.
    - Uses `_fert_dict` and `NPK_RATIOS` to return human‑readable fertilizer name and NPK ratio.

- **Agent**: `backend/agents/fertilizer_agent.py`
  - Docstring: *"handles fertilizer recommendation queries using the XGBoost model through the fertilizer_tool"*.
  - `FertilizerAgent` extends `ToolAgent` with `tool_callable=predict_fertilizer_core`.
  - The agent mainly adds:
    - Natural‑language parameter extraction (LLM + fast Hindi regex).
    - Multi‑turn clarification when `soil_type` or `crop_type` is missing.
    - Defaulting for optional fields.

- **REST endpoint**: `backend/routers/fertilizer_predict.py`
  - Loads the same XGBoost pipeline and dictionary at import time:
    - `xgb_model = joblib.load("models/xgb_pipeline.joblib")`
    - `fert_dict = joblib.load("models/fertname_dict.joblib")`
  - `/fertilizer_predict/predict`:
    - Accepts already‑encoded numeric `SoilType` and `CropType`.
    - Predicts `pred = xgb_model.predict(data)[0]`.
    - Maps the prediction via `fertilizer_name = fert_dict.get(pred, "Unknown")`.

#### ✅ Final choice for fertilizer recommendation (agents & API)

- **Chosen model**: **XGBoost classifier (wrapped in a `StandardScaler` + XGB pipeline)**
- **Serialized artifacts**:
  - `models/xgb_pipeline.joblib` – full scikit‑learn pipeline (scaler + XGBClassifier)
  - `models/fertname_dict.joblib` – mapping from class index → fertilizer name
- **Performance (from notebook XGBoost section)**:
  - Hold‑out test accuracy: **95.0%**
  - Accuracy on full dataset: **98.99%**
- **Used by**:
  - `FertilizerAgent` via `fertilizer_tool.predict_fertilizer_core`
  - `/fertilizer_predict/predict` FastAPI route

k‑NN and SVM are explored in the notebook but are **not** used by the production agents; the backend consistently uses the XGBoost‑based pipeline.

---

## 3. Plant Disease Classification Notebook (`plant-disease-classification-resnet-99-2.ipynb`)

### 3.1 Dataset

- **Source**: New Plant Diseases Dataset (Augmented), derived from the original PlantVillage dataset.
- **Training images**: 70,295 (as reported in the notebook).
- **Validation split**: Pre-split `train` / `valid` directories used via `ImageFolder` (roughly 80/20, matching dataset description).
- **Image resolution**: 256×256 RGB (images resized on input).
- **Classes**:
  - **38** disease classes (including healthy variants).
  - Across **14** distinct crops (e.g., tomato, potato, corn, apple, grape, etc.).

### 3.2 Model evaluated

The notebook builds and trains a **ResNet‑9** convolutional neural network in PyTorch:

- Architecture: custom **ResNet‑9** with residual blocks and batch normalization:
  - Conv → Conv+MaxPool → Residual block (128 channels)
  - Conv+MaxPool → Conv+MaxPool → Residual block (512 channels)
  - Final MaxPool → Flatten → Linear(512 → 38).
- Total parameters: **6,589,734**.
- Input: 3×256×256 RGB images.

Training configuration (from the notebook):

- Optimizer: `Adam`.
- Learning rate schedule: **One Cycle** policy (`OneCycleLR`).
- Epochs: **2**.
- Max learning rate: `0.01`.
- Gradient clipping: `0.1`.
- Weight decay: `1e-4`.

Reported metrics:

- Initial (before training) validation performance:
  - `val_loss ≈ 3.64`, `val_accuracy ≈ 0.019` (≈1.9%).
- After training for 2 epochs:
  - Epoch 0: `val_loss ≈ 0.5865`, `val_accuracy ≈ 0.8319`.
  - Epoch 1: `val_loss ≈ 0.0269`, `val_accuracy ≈ 0.9923`.
- The notebook summarizes this as:
  - **Validation accuracy: ~99.2%**.
- Test set evaluation:
  - A small held‑out test folder with **33 images**.
  - The model correctly classifies **all 33/33 images**.
  - Effectively **100% accuracy on this small test set**.

### 3.3 Models actually used by the agents and APIs

The backend contains **two implementations** for disease detection: a new PyTorch ResNet‑9 pipeline and a legacy TensorFlow/Keras CNN. They both operate over the same 38 PlantVillage classes.

- **Agentic pipeline (Supervisor V2, multi‑agent system)**
  - **Agent**: `backend/agents/disease_detection_agent.py`
    - `DiseaseDetectionAgent` is a `ToolAgent` configured with `tool_callable=detect_plant_disease_pytorch`.
    - Docstring explicitly states:
      - Architecture: **ResNet‑9**
      - Accuracy: **99.2% validation, 100% test**.
  - **Tool**: `backend/tools/disease_detection_tool_pytorch.py`
    - Defines `ResNet9` with the same architecture as in the notebook.
    - `PyTorchDiseaseDetectionService` loads a state‑dict from:
      - `models/disease_detection_state_dict.pth` (default `model_path`).
    - `detect_plant_disease_pytorch(...)` wraps `disease_service.predict(...)` and exposes it as a LangChain tool.
    - `get_model_info()` reports:
      - `model_type = "ResNet-9"`
      - `accuracy = "99.2% (validation), 100% (test)"`
      - `num_classes = 38`.

- **REST disease APIs**
  - **Service**: `backend/services/crop_disease_detection.py`
    - `CropDiseaseDetector` loads a **TensorFlow/Keras** CNN from:
      - `models/trained_model.keras`.
    - Uses the same 38 PlantVillage class names but with different input size (128×128).
  - **Endpoints**: `backend/routers/crop_disease.py`
    - `/crop_disease/detect-disease` and `/crop_disease/detect-disease-detailed` call `get_crop_disease_detector().predict_disease(image_data)`.
    - These routes therefore currently use the **TensorFlow/Keras model**, not the PyTorch ResNet‑9.

#### ✅ Final choice for disease detection (agentic pipeline vs. REST APIs)

- **Agentic multi‑agent pipeline** (Supervisor V2):
  - **Chosen model**: **ResNet‑9 (PyTorch) CNN**, matching the notebook architecture and metrics.
  - **Serialized artifact**: `models/disease_detection_state_dict.pth` (PyTorch state_dict).
  - **Performance (from notebook & tool docstrings)**:
    - Validation accuracy: **≈99.2%**.
    - Small 33‑image test set: **100% accuracy**.
  - **Used by**:
    - `DiseaseDetectionAgent` via `detect_plant_disease_pytorch` tool.

- **Standalone disease REST endpoints** (`/crop_disease/...`):
  - **Chosen model**: TensorFlow/Keras CNN (PlantVillage 38‑class model).
  - **Serialized artifact**: `models/trained_model.keras`.
  - Metrics for this TF model are not detailed in the provided notebook; it is a separate training pipeline.

---

## 4. Quick Reference: Models & Usage

| Task                      | Notebook model candidates                             | Best notebook metrics (test / CV or full) | **Model used in backend**                        | Serialized artifact(s)                    | Consumed by |
|---------------------------|--------------------------------------------------------|-------------------------------------------|--------------------------------------------------|------------------------------------------|-------------|
| **Crop recommendation**   | Decision Tree, Naive Bayes, SVM, Logistic Regression, Random Forest | NB: **99.55% test**, **99.50% CV**<br>RF: **99.32% test**, **99.41% CV** | **Gaussian Naive Bayes classifier**                | `models/NBClassifier.pkl`                | `CropAgent`, `/crop_predict/predict` |
| **Fertilizer recommendation** | k‑NN (various k), SVM pipeline, XGBoost pipeline    | XGB: **95.0% test**, **98.99% full**<br>SVM: 80% test, 92.93% full | **XGBoost classifier within a scikit‑learn pipeline** | `models/xgb_pipeline.joblib`, `models/fertname_dict.joblib` | `FertilizerAgent`, `/fertilizer_predict/predict` |

This file should give you a single source of truth connecting:
- The **experimental results in the notebooks**, and
- The **concrete model artifacts and classes** actually used by the agentic pipeline and REST APIs.

Summary of agent models:
- `CropAgent` uses a **Gaussian Naive Bayes** classifier loaded from `models/NBClassifier.pkl`.
- `FertilizerAgent` uses an **XGBoost classifier** wrapped in a scikit-learn pipeline loaded from `models/xgb_pipeline.joblib` and `models/fertname_dict.joblib`.
- `DiseaseDetectionAgent` uses a **ResNet-9 (PyTorch) CNN** loaded from `models/disease_detection_state_dict.pth` (while `/crop_disease` REST endpoints use a separate TensorFlow/Keras model `models/trained_model.keras`).
