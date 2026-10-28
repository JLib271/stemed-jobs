from dataclasses import asdict, dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    # Disciplines used for a posting when its title and hiring department name
    # none, for boards devoted to one field (e.g. MathJobs).
    disciplines: Tuple[str, ...] = ()


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
