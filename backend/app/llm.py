from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from app.config import get_settings


class LLMError(Exception):
    """The model call failed or gave unusable output
    (API error code: llm_failed)"""


def create_chat_model(*, http_client=None) -> BaseChatModel:
    settings = get_settings()
    return init_chat_model(
        settings.llm_model,
        api_key=settings.openai_api_key,
        timeout=30,
        max_retries=2,
        **({"http_async_client": http_client} if http_client is not None else {}),
    )


async def ask_structured[T: BaseModel](
    model: BaseChatModel,
    schema: type[T],
    system: str,
    user: str,
) -> T:
    try:
        structured = model.with_structured_output(schema)
        result = await structured.ainvoke([("system", system), ("user", user)])
    except Exception as e:
        # The provider SDK wraps transport failures after its retries. Preserve
        # safeguard denials rather than relabeling them as model failures.
        from app.usage import UsageLimited, UsageUnavailable

        cause = e
        for _ in range(10):
            if isinstance(cause, (UsageLimited, UsageUnavailable)):
                raise cause
            cause = cause.__cause__ or cause.__context__
            if cause is None:
                break
        raise LLMError(f"{schema.__name__} call failed: {e}") from e
    if not isinstance(result, schema):
        raise LLMError(f"{schema.__name__} call returned {type(result).__name__}")
    return result
