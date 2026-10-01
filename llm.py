import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True) 

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("MODEL")

if not OPENAI_API_KEY: 
    raise ValueError("OPENAI_API_KEY mangler i env")

if not MODEL: 
    raise ValueError("MODEL mangler i env")

client = OpenAI(api_key=OPENAI_API_KEY)

def call_llm(messages: list[dict], tools: list[dict] | None = None):
    """
    Sends messages to the LLM and returns the full response. 

    The full response is returned because the agent will later need to inspect whether the model returned normal text or a tool call.
    """

    request = {
        "model": MODEL, 
        "input": messages,
    }

    if tools: 
        request["tools"] = tools 

    response = client.responses.create(**request)
    
    return response 


if __name__ == "__main__":

    messages = [
        {
            "role": "user",
            "content": "Explain in one sentence what a stock is."
        }
    ]

    response = call_llm(messages)
    print(response.output_text)
