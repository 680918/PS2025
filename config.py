import os

from dotenv import load_dotenv


load_dotenv()


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))

LLM_RETRY_DELAY = float(os.getenv("LLM_RETRY_DELAY", "1"))
