"""Replaceable language-model adapters for the support workflow."""

from customer_support_agent.llm.adapter import DeepSeekChatModel, SupportLanguageModel
from customer_support_agent.llm.fake import ScriptedSupportLanguageModel

__all__ = ["DeepSeekChatModel", "ScriptedSupportLanguageModel", "SupportLanguageModel"]
