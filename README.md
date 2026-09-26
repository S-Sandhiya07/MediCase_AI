
# MediCase AI – Beginner-Friendly SIH Prototype

## What this project is
A Flask + SQLite healthcare case-taking prototype with:
- Patient registration/login
- Patient-specific records
- Voice input using browser Web Speech API
- Simple NLP intent classifier (TF-IDF + Logistic Regression)
- Dynamic consultation conversation
- Structured case sheet
- Patient history
- Doctor login/dashboard/review/finalization

The AI model is an educational **information-intent classifier**. It does not diagnose disease.

## Demo doctor
Email: doctor@medicase.ai
Password: Doctor@123

## Run
1. Open this folder in VS Code.
2. Open Terminal.
3. Create environment:
   `python -m venv venv`
4. Activate on Windows PowerShell:
   `.\venv\Scripts\Activate.ps1`
5. If PowerShell blocks activation, use:
   `venv\Scripts\activate.bat`
6. Install:
   `python -m pip install -r requirements.txt`
7. Start:
   `python app.py`
8. Open:
   `http://127.0.0.1:5000`

The first run creates `medicase.db` and trains/saves `case_intent_model.pkl`.
