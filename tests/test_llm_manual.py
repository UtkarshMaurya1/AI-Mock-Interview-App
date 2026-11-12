
from interviewer.llm import generate_response

if __name__ == "__main__":
    result = generate_response(
        "Generate one Python backend interview question."
    )
    print(result)
