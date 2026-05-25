from langchain_ollama import ChatOllama

from slm.config.settings import get_settings
from slm.models.base import LangChainChatModelAdapter


def create_ollama_model(model_id: str | None = None) -> LangChainChatModelAdapter:
    settings = get_settings()
    resolved = model_id or settings.default_model
    llm = ChatOllama(
        model=resolved,
        base_url=settings.ollama_base_url,
        temperature=0.2,
        num_predict=4096,
    )
    return LangChainChatModelAdapter(llm, model_id=resolved)
