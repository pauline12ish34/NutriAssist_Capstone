"""HTTP client for the NutriAssist-RW API, used by the Streamlit pages."""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests

DEFAULT_API_URL = os.environ.get("NUTRIASSIST_API_URL", "http://localhost:8000")


class ApiError(Exception):
    """A request failed. ``message`` is safe to show to the user."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class NutriAssistClient:
    base_url: str = DEFAULT_API_URL
    timeout_s: float = 180.0            # a long answer on a slow CPU can take a minute or more

    def health(self) -> dict:
        return self._request("GET", "/health", timeout=5)

    def chat(self, question: str) -> dict:
        return self._request("POST", "/chat", json={"question": question})

    def meal_plan(self, age_months: int, days: int, breastfed: bool, language: str,
                  available: list[str] | None = None, excluded: list[str] | None = None) -> dict:
        return self._request("POST", "/meal-plan", json={
            "age_months": age_months, "days": days, "breastfed": breastfed, "language": language,
            "available": available, "excluded": excluded or [],
        })

    def foods(self) -> list[dict]:
        return self._request("GET", "/foods")

    def _request(self, method: str, path: str, timeout: float | None = None, **kwargs):
        try:
            response = requests.request(method, f"{self.base_url}{path}", timeout=timeout or self.timeout_s, **kwargs)
        except requests.ConnectionError as error:
            raise ApiError(f"Cannot reach the NutriAssist server at {self.base_url}. Is it running?") from error
        except requests.Timeout as error:
            raise ApiError("The server took too long to answer. Please try again.") from error
        if response.status_code >= 400:
            raise ApiError(_error_detail(response), response.status_code)
        return response.json()


def _error_detail(response: requests.Response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        return f"Server error ({response.status_code})."
    if isinstance(detail, list):  # FastAPI validation errors
        return "; ".join(item.get("msg", "") for item in detail)
    return str(detail)
