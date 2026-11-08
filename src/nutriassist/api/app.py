"""NutriAssist-RW REST API.

Run:   uvicorn nutriassist.api.app:app --port 8000
Docs:  http://localhost:8000/docs (Swagger UI)
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from .. import __version__
from ..assistant import AssistantReply, InvalidQuestion, NutritionAssistant, ReplySource
from ..inference.base import ChatModel
from ..knowledge import KnowledgeBase
from ..planner import FoodCatalogue, MealPlanner, PlanRequest
from ..screening import ScreeningInputError, ScreeningRequest, screen
from .schemas import (ChatRequest, ChatResponse, ErrorResponse, FoodOut, HealthResponse, MealPlanRequest,
                      MealPlanResponse, ScreeningRequestIn, ScreeningResponse)
from ..translation import Translator
from ..safety.relevance import RelevanceChecker
from ..safety.topics import TopicRules
from .settings import (Settings, build_chat_model, build_checks, build_embedder, build_example_index,
                       build_knowledge_base, build_translator, reviewed_only_languages)

log = logging.getLogger("nutriassist.api")


class Services:
    """Everything the endpoints need, built once at start-up."""

    def __init__(self, model: ChatModel, demo_mode: bool, catalogue: FoodCatalogue,
                 knowledge: KnowledgeBase | None = None, translator: Translator | None = None,
                 reviewed_only: frozenset[str] = frozenset(), unanswered_log: Path | None = None,
                 grounding: int = 0, examples: KnowledgeBase | None = None,
                 topics: TopicRules | None = None, checker: RelevanceChecker | None = None) -> None:
        self.assistant = NutritionAssistant(model, knowledge=knowledge, translator=translator,
                                            reviewed_only=reviewed_only, grounding=grounding, examples=examples,
                                            topics=topics, checker=checker)
        self.unanswered_log = unanswered_log
        self.demo_mode = demo_mode
        self.catalogue = catalogue
        self.planner = MealPlanner(catalogue)
        # No lock here: the model locks only its own generation (LlamaCppChatModel), so safety rules, reviewed
        # answers, growth checks and meal plans never wait behind another person's model answer.

    def record_unanswered(self, question: str, reply: AssistantReply) -> None:
        """Keep questions with no reviewed answer, so reviewers can write answers for the common ones.

        Only the question text, its language and the time are stored: no user or session data.
        """
        if self.unanswered_log is None or reply.source not in (ReplySource.NO_MATCH, ReplySource.OFF_TOPIC,
                                                                ReplySource.OUT_OF_SCOPE):
            return
        try:
            self.unanswered_log.parent.mkdir(parents=True, exist_ok=True)
            row = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "language": reply.language,
                   "question": question, "suggested": reply.suggestions}
            with self.unanswered_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:  # a read-only disk must not break the chat
            log.warning("Could not write %s", self.unanswered_log, exc_info=True)


def create_app(settings: Settings | None = None, model: ChatModel | None = None,
               catalogue: FoodCatalogue | None = None, knowledge: KnowledgeBase | None = None,
               translator: Translator | None = None, reviewed_only: frozenset[str] = frozenset(),
               unanswered_log: Path | None = None) -> FastAPI:
    """Build the app. Tests pass a ``model`` and ``catalogue`` (and optionally the other services);
    otherwise everything comes from ``settings``."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if model is not None:
            chat_model, demo, kb, mt = model, False, knowledge, translator
            only, unanswered, grounding = reviewed_only, unanswered_log, (settings.grounding if settings else 0)
            examples, topics, checker = None, None, None
        else:
            config = settings or Settings.from_env()
            chat_model, demo = build_chat_model(config)
            kb, mt = build_knowledge_base(config), build_translator(config)
            only, unanswered = reviewed_only_languages(config, kb, mt), config.unanswered_log
            embedder = build_embedder(config)
            grounding, examples = config.grounding, build_example_index(config, embedder)
            topics, checker = build_checks(config, embedder)
        log.info("Serving model %s (demo mode: %s); reviewed answers: %s; reviewed-only languages: %s; translator: %s; "
                 "grounding examples: %s; answer checks: %s", chat_model.name, demo, len(kb) if kb else "off",
                 ", ".join(sorted(only)) or "none", mt.name if mt else "off", grounding or "off",
                 "on" if checker else "off")
        app.state.services = Services(chat_model, demo, catalogue or FoodCatalogue.load(), kb, mt, only, unanswered,
                                      grounding, examples, topics, checker)
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
            reply = s.assistant.ask(body.question)
            s.record_unanswered(body.question, reply)
        except InvalidQuestion as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:  # the model failed: report it instead of returning a half answer
            log.exception("Model error")
            raise HTTPException(status_code=503, detail="The assistant is not available right now. Please try again.") from error
        return ChatResponse(answer=reply.answer, language=reply.language, safety_level=reply.safety_level,
                            danger_signs=reply.danger_signs, source=reply.source.value, model=reply.model_name,
                            latency_ms=reply.latency_ms, translated=reply.translated,
                            matched_question=reply.matched_question, suggestions=reply.suggestions)

    @app.post("/meal-plan", response_model=MealPlanResponse, tags=["meal planner"],
              responses={422: {"model": ErrorResponse}})
    def meal_plan(body: MealPlanRequest, request: Request) -> MealPlanResponse:
        s = services(request)
        try:
            plan = s.planner.plan(PlanRequest(
                age_months=body.age_months, days=body.days, breastfed=body.breastfed,
                available=frozenset(body.available) if body.available is not None else None,
                excluded=frozenset(body.excluded), conditions=frozenset(body.conditions),
            ))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return MealPlanResponse(**plan.to_dict(body.language))

    @app.post("/screening", response_model=ScreeningResponse, tags=["growth check"],
              responses={422: {"model": ErrorResponse}})
    def screening(body: ScreeningRequestIn, request: Request) -> ScreeningResponse:
        """Classify a child's nutritional status from weight, height and MUAC (WHO Child Growth Standards)."""
        s = services(request)
        try:
            result = screen(ScreeningRequest(age_months=body.age_months, sex=body.sex, weight_kg=body.weight_kg,
                                             height_cm=body.height_cm, muac_cm=body.muac_cm, oedema=body.oedema))
        except ScreeningInputError as error:
            raise HTTPException(status_code=422, detail=error.message(body.language)) from error
        data = result.to_dict(body.language)
        plan = None
        if data.pop("meal_plan"):
            plan = s.planner.plan(PlanRequest(age_months=body.age_months, days=1, breastfed=body.breastfed,
                                              conditions=frozenset(result.conditions)))
            plan = MealPlanResponse(**plan.to_dict(body.language))
        return ScreeningResponse(**data, meal_plan=plan)

    @app.get("/foods", response_model=list[FoodOut], tags=["meal planner"])
    def foods(request: Request) -> list[FoodOut]:
        catalogue = services(request).catalogue
        return [FoodOut(key=f.key, name_en=f.name_en, name_rw=f.name_rw, group=f.group,
                        min_age_months=f.min_age_months) for f in (catalogue[k] for k in catalogue.keys)]

    return app


app = create_app()
