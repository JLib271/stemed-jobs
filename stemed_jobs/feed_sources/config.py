import json
from pathlib import Path
from typing import List

from stemed_jobs.disciplines import DISCIPLINES
from stemed_jobs.models import Feed


def load_feeds(path: Path) -> List[Feed]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Could not read feed configuration at {}: {}".format(path, error)) from error

    if not isinstance(data, dict) or not isinstance(data.get("feeds"), list):
        raise ValueError("Feed configuration must be a JSON object with a 'feeds' list.")

    feeds = []
    for index, item in enumerate(data["feeds"]):
        if not isinstance(item, dict):
            raise ValueError("Feed {} must be an object with 'name' and 'url'.".format(index + 1))
        name, url = item.get("name"), item.get("url")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Feed {} must have a non-empty name.".format(index + 1))
        if not isinstance(url, str) or not url.strip():
            raise ValueError("Feed '{}' must have a non-empty URL.".format(name))
        disciplines = item.get("disciplines", [])
        if not isinstance(disciplines, list):
            raise ValueError("Feed '{}' disciplines must be a list.".format(name))
        invalid = [discipline for discipline in disciplines if discipline not in DISCIPLINES]
        if invalid:
            raise ValueError("Feed '{}' has unknown discipline(s): {}.".format(name, ", ".join(map(str, invalid))))
        retain_days = item.get("retain_days", 0)
        if isinstance(retain_days, bool) or not isinstance(retain_days, int) or retain_days < 0:
            raise ValueError("Feed '{}' retain_days must be a whole number of days, 0 or more.".format(name))
        curated = item.get("curated", False)
        if not isinstance(curated, bool):
            raise ValueError("Feed '{}' curated must be true or false.".format(name))
        feeds.append(
            Feed(
                name=name.strip(),
                url=url.strip(),
                disciplines=tuple(disciplines),
                retain_days=retain_days,
                curated=curated,
            )
        )

    return feeds
