import requests

notes = '''29F — dizziness especially when standing, tired climbing stairs, headaches sometimes. Periods have become very heavy over last ~8 months, changing pad every 1-2 hrs on worst days.
Hb 8.9
MCV 69
MCH low
Ferritin 6
Platelets 438
Started oral iron. Takes ibuprofen during periods.
No drug allergies.
Needs gyn review for heavy menstrual bleeding. Repeat CBC/iron profile later.'''

try:
    res = requests.post("http://localhost:8000/extract", json={"raw_notes": notes, "patient_id": "TEST-003"})
    print(res.status_code)
    print(res.text)
except Exception as e:
    print("Error:", e)
