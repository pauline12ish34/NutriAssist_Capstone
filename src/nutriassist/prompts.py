"""The system prompt and chat-message layout shared by training, evaluation and the app.

The model is trained with exactly this prompt, so the app must send the same text.
"""

from __future__ import annotations

SYSTEM_PROMPT = (
    "You are NutriAssist-RW, a nutrition assistant for parents and caregivers of young children in Rwanda. "
    "Give practical, safe advice on breastfeeding, feeding children from 6 months to 5 years, and nutrition "
    "for pregnant and breastfeeding mothers, using local foods. Reply in the language of the question "
    "(English or Kinyarwanda). You do not diagnose illness or recommend medicines or doses; when there are "
    "danger signs, tell the caregiver to go to the health centre."
)

Message = dict[str, str]


GROUNDING_INSTRUCTION = (
    "Here are checked answers to similar questions. Use their facts and wording where they fit, and do not "
    "add facts they do not support. Answer only the caregiver's question, in the language of the question, "
    "in a few sentences."
)
MAX_EXAMPLE_CHARS = 600   # keeps three examples inside the GGUF model's 2048-token context


def build_grounded_messages(question: str, examples: list[tuple[str, str]],
                            system_prompt: str = SYSTEM_PROMPT) -> list[Message]:
    """Like :func:`build_messages`, with reviewed question-answer pairs in the system turn (RAG)."""
    if not examples:
        return build_messages(question, system_prompt=system_prompt)
    notes = "\n\n".join(f"Q: {q}\nA: {a[:MAX_EXAMPLE_CHARS]}" for q, a in examples)
    return build_messages(question, system_prompt=f"{system_prompt}\n\n{GROUNDING_INSTRUCTION}\n\n{notes}")


def build_messages(question: str, answer: str | None = None, system_prompt: str = SYSTEM_PROMPT) -> list[Message]:
    """System + user turns, plus the assistant turn when ``answer`` is given (training examples)."""
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    if answer is not None:
        messages.append({"role": "assistant", "content": answer})
    return messages
