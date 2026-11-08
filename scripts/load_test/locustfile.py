"""Locust load test for the NutriAssist-RW API: how response times change as more people use it at once.

Three kinds of visitors, as in a health-centre catchment area:
- ``Caregiver`` asks open questions that the fine-tuned model must answer (the slow, CPU-heavy path);
- ``UrgentCaregiver`` (always exactly one) reports a danger sign, answered by the safety rules;
- ``HealthWorker`` (always exactly one) runs growth checks and asks for meal plans (no model).

The number of ``Caregiver`` users is what scripts/load_test/run.py increases from run to run. The question is
whether the urgent answer and the growth check stay fast while the model is busy.

Run by hand:  locust -f scripts/load_test/locustfile.py --host http://127.0.0.1:8000
"""

import random

from locust import HttpUser, between, constant, task

TIMEOUT_S = 180   # a request still waiting after 3 minutes counts as failed

# English questions with no reviewed answer, so the model writes each answer (checked before the runs).
MODEL_QUESTIONS = [
    "Can I give my child Irish potatoes?",
    "Is it fine to give my toddler cassava bread every day?",
    "How can I make porridge thicker for my 10 month old?",
    "Can I add sugar to my baby's porridge to make it tasty?",
]
DANGER_SIGNS = [
    "My child is having a seizure",
    "My baby cannot drink or breastfeed",
    "My child vomits everything",
]


class Caregiver(HttpUser):
    wait_time = between(1, 3)

    @task
    def ask_the_model(self):
        self.client.post("/chat", json={"question": random.choice(MODEL_QUESTIONS)},
                         name="chat: model answer", timeout=TIMEOUT_S)


class UrgentCaregiver(HttpUser):
    fixed_count = 1
    wait_time = constant(3)

    @task
    def report_a_danger_sign(self):
        self.client.post("/chat", json={"question": random.choice(DANGER_SIGNS)},
                         name="chat: danger sign", timeout=TIMEOUT_S)


class HealthWorker(HttpUser):
    fixed_count = 1
    wait_time = constant(3)

    @task(2)
    def growth_check(self):
        self.client.post("/screening", json={"age_months": 12, "sex": "male", "weight_kg": 7.0, "height_cm": 72.0,
                                             "muac_cm": 12.0, "oedema": False, "breastfed": True, "language": "en"},
                         name="growth check", timeout=TIMEOUT_S)

    @task(1)
    def meal_plan(self):
        self.client.post("/meal-plan", json={"age_months": 9, "days": 7, "breastfed": True, "language": "en"},
                         name="meal plan (7 days)", timeout=TIMEOUT_S)
