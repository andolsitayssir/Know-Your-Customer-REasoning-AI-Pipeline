from __future__ import annotations

from typing import List

from pydantic import BaseModel


class AgentResponse(BaseModel):
    is_conforme: bool
    violations: List[str]
    

    class Config:
        extra = "ignore"
