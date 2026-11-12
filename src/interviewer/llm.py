
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


def generate_response(prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a professional technical interviewer.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content
