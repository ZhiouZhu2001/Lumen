from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from app.config import get_settings


class LLMError(Exception):
    """The model call failed or gave unusable output
    (API error code: llm_failed)"""


def create_chat_model() -> BaseChatModel:
    settings = get_settings()
    return init_chat_model(
        settings.llm_model,
        api_key=settings.openai_api_key,
        timeout=30,
        max_retries=2,
    )


async def ask_structured[T: BaseModel](
    model: BaseChatModel,
    schema: type[T],
    system: str,
    user: str,
) -> T:
    structured = model.with_structured_output(schema)
    try:
        result = await structured.ainvoke([("system", system), ("user", user)])
    except Exception as e:
        raise LLMError(f"{schema.__name__} call failed: {e}") from e
    if not isinstance(result, schema):
        raise LLMError(f"{schema.__name__} call returned {type(result).__name__}")
    return result
