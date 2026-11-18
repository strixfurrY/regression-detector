import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError
from .schemas import ClassifierOutput, PromptConfig

load_dotenv()
client = OpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

def classify_email(email: str, config: PromptConfig) -> dict:
    messages = [{"role": "system", "content": config.system_prompt}]
    for ex in config.few_shot_examples:
        messages.append({"role": "user", "content": ex["email"]})
        messages.append({"role": "assistant", "content": ex["output"]})
    messages.append({"role": "user", "content": email})

    start = time.perf_counter()
    resp = client.chat.completions.create(
        model=config.model,
        temperature=config.temperature,
        messages=messages,
        response_format={"type": "json_object"},
    )
    latency = time.perf_counter() - start

    raw = resp.choices[0].message.content
    try:
        output = ClassifierOutput.model_validate_json(raw)
        error = None
    except ValidationError as e:
        output = None
        error = f"schema_violation: {e.errors()[0]['msg']}"

    return {
        "output": output,
        "raw": raw,
        "error": error,
        "latency_s": latency,
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }