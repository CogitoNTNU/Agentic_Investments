"""Tools that an agent may execute.

Learning goal:
- Understand that tools are ordinary Python code.
- The model chooses *which* tool to request.
- Python remains responsible for actually executing the tool.
"""

from typing import Any, Protocol


class Tool:
   
