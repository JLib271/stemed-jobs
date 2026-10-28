import json
from pathlib import Path
from typing import Iterable

from stemed_jobs.models import Job


def write_jobs(jobs: Iterable[Job], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump([job.to_dict() for job in jobs], output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")
