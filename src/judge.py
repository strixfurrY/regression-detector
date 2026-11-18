import json
from .classifier import client

JUDGE_MODEL = "gemini-3.1-flash-lite"

JUDGE_PROMPT = """You grade summaries of customer support emails.
Rate the CANDIDATE summary from 1 to 5 for how well it captures the key point of the email, using the REFERENCE summary as a guide.
5 = same meaning as the reference, accurate
4 = correct, a minor detail is missing
3 = partly right
2 = mostly wrong or too vague
1 = wrong or unrelated
Respond ONLY with JSON: {"score": <1-5>, "reason": "<short reason>"}"""


def judge_summary(email: str, reference: str, candidate: str) -> dict:
    user = f"EMAIL:\n{email}\n\nREFERENCE SUMMARY:\n{reference}\n\nCANDIDATE SUMMARY:\n{candidate}"
    resp = client.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=0.0,
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    score = int(data["score"])
    if not 1 <= score <= 5:
        raise ValueError(f"score out of range: {score}")
    return {"score": score, "reason": data.get("reason", "")}