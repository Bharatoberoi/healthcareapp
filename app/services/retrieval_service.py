from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class RetrievalService(ABC):
    @abstractmethod
    def resolve_service_code(
        self, query: str, service_code: Optional[str] = None
    ) -> Dict[str, Any]:
        pass
