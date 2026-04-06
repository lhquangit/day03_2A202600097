from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[[BaseModel], BaseModel]

    def invoke(self, payload: dict[str, Any] | BaseModel) -> BaseModel:
        request = payload
        if not isinstance(payload, BaseModel):
            request = self.input_model.model_validate(payload)
        return self.handler(request)

    def to_agent_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_model": self.input_model,
            "output_model": self.output_model,
            "handler": self.handler,
        }
