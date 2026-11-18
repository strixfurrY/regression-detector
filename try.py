from src.loader import load_prompt
from src.classifier import classify_email

cfg = load_prompt("v1")
result = classify_email("I can't log in, it says my password is wrong", cfg)
print(result)