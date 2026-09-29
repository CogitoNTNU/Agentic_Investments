import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("MODEL")

if not OPENAI_API_KEY : 
    raise ValueError("OPENAI_API_KEY mangler i env")

if not MODEL: 
    raise ValueError("MODEL mangler i env")

client = OpenAI(api_key= OPENAI_API_KEY)

def call_LLM(messages: list[dict], tools: list[dict]| None = None): 
    """
    Sends messages to the llm and retrn the full response. 
    The full response is returned becasue the agent will later need to inspect whether the model returned normal text or a tool call.
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
            "content": "Explain inone sentance what a stock is."
        }
    ]

    response = call_LLM(messages)
    print(response.output_text)

    


#lage tools for å finne beste aksjer

# market-data tools 
#research tools 
#agent 
#analysis step 
# final response 

def research_stock(ticker: str) -> dict: 
    """
    Collect the information needed to research one stock.
    """