from dataclasses import asdict, dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Feed:
    name: str
    url: str


@dataclass(frozen=True)
class JobBoard:
    name: str
    url: str
    disciplines: List[str]


@dataclass(frozen=True)
class Job:
    id: str
    title: str
    company: str
    location: str
    url: str
    published: Optional[str]
    summary: str
    source: str
    source_url: str
    categories: List[str]
    functions: List[str]
    disciplines: List[str]

    def to_dict(self) -> dict:
        return asdict(self)
