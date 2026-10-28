import json
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from stemed_jobs.disciplines import DISCIPLINES
from stemed_jobs.models import JobBoard


def load_job_boards(path: Path) -> List[JobBoard]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Could not read job board configuration at {}: {}".format(path, error)) from error

    if not isinstance(data, dict) or not isinstance(data.get("job_boards"), list):
        raise ValueError("Job board configuration must contain a 'job_boards' list.")

    boards = []
    for index, item in enumerate(data["job_boards"]):
        if not isinstance(item, dict):
            raise ValueError("Job board {} must be an object.".format(index + 1))
        name, url, disciplines = item.get("name"), item.get("url"), item.get("disciplines")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Job board {} must have a non-empty name.".format(index + 1))
        if not isinstance(url, str) or urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
            raise ValueError("Job board '{}' must have an absolute HTTP(S) URL.".format(name))
        if not isinstance(disciplines, list) or not disciplines:
            raise ValueError("Job board '{}' must have at least one discipline.".format(name))
        invalid = [discipline for discipline in disciplines if discipline not in DISCIPLINES]
        if invalid:
            raise ValueError(
                "Job board '{}' has unknown discipline(s): {}.".format(name, ", ".join(invalid))
            )
        boards.append(JobBoard(name=name.strip(), url=url.strip(), disciplines=disciplines))

    return boards
