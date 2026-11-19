FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY prompts/ prompts/
COPY data/golden_v1.json data/golden_v1.json
COPY baselines/ baselines/

# Configured at run time, never baked into the image
ENV GEMINI_API_KEY="" \
    SLACK_WEBHOOK_URL="" \
    WARN_THRESHOLD="0.03" \
    CRITICAL_THRESHOLD="0.08" \
    DRIFT_WINDOW="7" \
    DRIFT_MIN_PASS_RATE="0.90"

ENTRYPOINT ["python", "-m", "src.ci"]
CMD ["v1"]