from .metrics import *

def get_tools() -> tuple[list, dict]:
    """Return a list of tools and a dictionary of tools by name."""
    tools = [get_key_metrics]
    tools_by_name = {tool.name: tool for tool in tools}
    return tools, tools_by_name