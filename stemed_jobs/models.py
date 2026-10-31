from dataclasses import asdict, dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    # Disciplines used for a posting when its title and hiring department name
    # none, for boards devoted to one field (e.g. MathJobs).
    disciplines: Tuple[str, ...] = ()
    # For boards that only list their newest postings: keep each posting seen in
    # an earlier run for this many days after it was posted, even when the board
    # no longer lists it. 0 (the default) keeps nothing extra.
    retain_days: int = 0
    # For a feed of editor-reviewed posts (such as the Seekers' Hub submissions):
    # the post's own categories decide its audience and disciplines, the
    # "Institution:", "Location:" and deadline lines in its body fill in the
    # details, and the keyword relevance screening is skipped because an editor
    # already approved it.
    curated: bool = False


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
    # Application deadline (YYYY-MM-DD) when the posting states one, else "".
    deadline: str = ""
    # Date review of applications is said to begin (YYYY-MM-DD), else "".
    review_date: str = ""
    # True for a job from a curated feed: its categories were chosen by an editor.
    curated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FeedResult:
    """What one feed produced in a run: its jobs, or the error that stopped it."""

    feed: Feed
    jobs: List[Job] = field(default_factory=list)
    error: Optional[str] = None
