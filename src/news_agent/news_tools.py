from langchain_core.tools import tool

@tool
def get_news():
    return