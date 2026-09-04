"""Load test for DocMind's API.

Run against a real deployment (not this sandbox — see README):
    locust -f loadtest/locustfile.py --host http://localhost:8000

Simulates the realistic traffic mix: mostly queries, occasional ingestion,
occasional cache-hitting repeat questions (to see whether the semantic
cache actually reduces load on the LLM under concurrent traffic).
"""
import random

from locust import HttpUser, task, between


SAMPLE_QUESTIONS = [
    "What does DocMind track per pipeline stage?",
    "What two retrieval methods does DocMind combine?",
    "What happens when confidence is below the threshold?",
    "What orchestration framework powers the routing?",
]


class DocMindUser(HttpUser):
    wait_time = between(1, 3)

    @task(6)
    def ask_question(self):
        question = random.choice(SAMPLE_QUESTIONS)
        self.client.post("/api/query", json={"query": question}, name="/api/query")

    @task(2)
    def ask_repeat_question(self):
        """Deliberately repeats the same question to exercise the semantic
        cache path under concurrent load."""
        self.client.post("/api/query", json={"query": SAMPLE_QUESTIONS[0]}, name="/api/query [cache-hit candidate]")

    @task(1)
    def check_health(self):
        self.client.get("/api/health", name="/api/health")

    @task(1)
    def cache_stats(self):
        self.client.get("/api/cache/stats", name="/api/cache/stats")
