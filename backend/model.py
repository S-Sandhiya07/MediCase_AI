
from pathlib import Path
import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "case_intent_model.pkl"

TRAINING_DATA = [
    ("hello", "greeting"), ("hi", "greeting"), ("good morning", "greeting"),
    ("I have stomach pain", "chief_complaint"),
    ("my head hurts", "chief_complaint"),
    ("I am having chest discomfort", "chief_complaint"),
    ("I have been coughing", "chief_complaint"),
    ("for three days", "duration"), ("since yesterday", "duration"),
    ("it started last week", "duration"), ("for two months", "duration"),
    ("pain is 7", "severity"), ("seven out of ten", "severity"),
    ("it is very severe", "severity"), ("pain is mild", "severity"),
    ("I also have vomiting", "symptoms"), ("I have fever and nausea", "symptoms"),
    ("there is dizziness too", "symptoms"),
    ("I take metformin", "medications"), ("I am taking tablets", "medications"),
    ("no medicines", "medications"),
    ("I am allergic to penicillin", "allergies"), ("no known allergies", "allergies"),
    ("I have diabetes", "medical_history"), ("I had asthma before", "medical_history"),
    ("no past medical history", "medical_history"),
    ("I had surgery last year", "previous_surgeries"),
    ("my father has diabetes", "family_history"), ("no family history", "family_history"),
    ("I smoke", "lifestyle"), ("I do not smoke or drink", "lifestyle"),
    ("I exercise regularly", "lifestyle"),
]

class CaseTakingModel:
    """Small educational NLP classifier for conversation intent.

    It is NOT a diagnostic model. It only helps identify the type of
    information a patient message appears to contain.
    """
    def __init__(self):
        if MODEL_PATH.exists():
            self.pipeline = joblib.load(MODEL_PATH)
        else:
            X = [x for x,_ in TRAINING_DATA]
            y = [y for _,y in TRAINING_DATA]
            self.pipeline = Pipeline([
                ("tfidf", TfidfVectorizer(ngram_range=(1,2), lowercase=True)),
                ("clf", LogisticRegression(max_iter=1000))
            ])
            self.pipeline.fit(X, y)
            joblib.dump(self.pipeline, MODEL_PATH)

    def predict_intent(self, text):
        return self.pipeline.predict([text])[0]
