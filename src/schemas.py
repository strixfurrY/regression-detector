from typing import Literal
from pydantic import BaseModel, Field

Category = Literal["billing", "technical", "account", "general"]

class ClassifierOutput(BaseModel):
    category: Category
    summary: str = Field(description="One-sentence summary of the email")

class PromptConfig(BaseModel):
    version: str
    timestamp: str
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    system_prompt: str
    few_shot_examples: list[dict] = []