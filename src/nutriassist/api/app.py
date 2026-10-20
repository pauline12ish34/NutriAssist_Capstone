"""NutriAssist-RW REST API.

Run:   uvicorn nutriassist.api.app:app --port 8000
Docs:  http://localhost:8000/docs (Swagger UI)
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from .. import __version__
from ..assistant import InvalidQuestion, NutritionAssistant
from ..inference.base import ChatModel
from ..planner import FoodCatalogue, MealPlanner, PlanRequest
from .schemas import (ChatRequest, ChatResponse, ErrorResponse, FoodOut, HealthResponse, MealPlanRequest,
                      MealPlanResponse)
from .settings import Settings, build_chat_model

log = logging.getLogger("nutriassist.api")


class Services:
    """Everything the endpoints need, built once at start-up."""

    def __init__(self, model: ChatModel, demo_mode: bool, catalogue: FoodCatalogue) -> None:
        self.assistant = NutritionAssistant(model)
        self.demo_mode = demo_mode
        self.catalogue = catalogue
        self.planner = MealPlanner(catalogue)
        # llama.cpp keeps one context per model, so generate one answer at a time.
        self.model_lock = threading.Lock()


def create_app(settings: Settings | None = None, model: ChatModel | None = None,
               catalogue: FoodCatalogue | None = None) -> FastAPI:
    """Build the app. Tests pass a ``model`` and ``catalogue``; otherwise they come from ``settings``."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if model is not None:
            chat_model, demo = model, False
        else:
            chat_model, demo = build_chat_model(settings or Settings.from_env())
        log.info("Serving model %s (demo mode: %s)", chat_model.name, demo)
        app.state.services = Services(chat_model, demo, catalogue or FoodCatalogue.load())
        yield

    app = FastAPI(
        title="NutriAssist-RW API",
        version=__version__,
        description=(
            "Nutrition advice for caregivers of children under 5 in Rwanda, in English and Kinyarwanda.\n\n"
            "- **/chat** answers a question. Danger signs are answered by safety rules before the model "
            "is called; medicine doses from the model are blocked.\n"
            "- **/meal-plan** builds a 1-7 day meal plan from local foods for a child aged 6-59 months.\n\n"
            "Not a substitute for a health worker."
        ),
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def timing_header(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Process-Time-ms"] = f"{1000 * (time.perf_counter() - start):.1f}"
        return response

    def services(request: Request) -> Services:
        return request.app.state.services

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health(request: Request) -> HealthResponse:
        s = services(request)
        return HealthResponse(status="ok", model=s.assistant.model.name, demo_mode=s.demo_mode, version=__version__)

    @app.post("/chat", response_model=ChatResponse, tags=["assistant"],
              responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
    def chat(body: ChatRequest, request: Request) -> ChatResponse:
        s = services(request)
        try:
            with s.model_lock:
                reply = s.assistant.ask(body.question)
        except InvalidQuestion as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:  # the model failed: report it instead of returning a half answer
            log.exception("Model error")
            raise HTTPException(status_code=503, detail="The assistant is not available right now. Please try again.") from error
        return ChatResponse(answer=reply.answer, language=reply.language, safety_level=reply.safety_level,
                            danger_signs=reply.danger_signs, source=reply.source.value, model=reply.model_name,
                            latency_ms=reply.latency_ms)

    @app.post("/meal-plan", response_model=MealPlanResponse, tags=["meal planner"],
              responses={422: {"model": ErrorResponse}})
    def meal_plan(body: MealPlanRequest, request: Request) -> MealPlanResponse:
        s = services(request)
        try:
            plan = s.planner.plan(PlanRequest(
                age_months=body.age_months, days=body.days, breastfed=body.breastfed,
                available=frozenset(body.available) if body.available is not None else None,
                excluded=frozenset(body.excluded),
            ))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return MealPlanResponse(**plan.to_dict(body.language))

    @app.get("/foods", response_model=list[FoodOut], tags=["meal planner"])
    def foods(request: Request) -> list[FoodOut]:
        catalogue = services(request).catalogue
        return [FoodOut(key=f.key, name_en=f.name_en, name_rw=f.name_rw, group=f.group,
                        min_age_months=f.min_age_months) for f in (catalogue[k] for k in catalogue.keys)]

    return app


app = create_app()
