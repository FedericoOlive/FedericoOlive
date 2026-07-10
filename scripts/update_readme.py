import datetime
import os
import re
import time
from pathlib import Path

import requests

BIRTHDAY = datetime.date(1994, 11, 18)
GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"

USER_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { nameWithOwner stargazerCount }
    }
  }
}
"""

CONTRIBUTED_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositoriesContributedTo(first: 100, contributionTypes: [COMMIT], includeUserRepositories: false) {
      nodes { nameWithOwner }
    }
  }
}
"""

COMMITS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
    }
  }
}
"""


def graphql(query: str, variables: dict, token: str) -> dict:
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers={"Authorization": f"bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["data"]


def uptime(today: datetime.date) -> str:
    years = today.year - BIRTHDAY.year
    months = today.month - BIRTHDAY.month
    days = today.day - BIRTHDAY.day
    if days < 0:
        months -= 1
        last_day_prev_month = today.replace(day=1) - datetime.timedelta(days=1)
        days += last_day_prev_month.day
    if months < 0:
        years -= 1
        months += 12
    return f"{years} years, {months} months, {days} days"


def total_commits(login: str, created_at: str, token: str) -> int:
    start = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    now = datetime.datetime.now(datetime.timezone.utc)
    total = 0
    while start < now:
        end = min(start + datetime.timedelta(days=365), now)
        data = graphql(
            COMMITS_QUERY,
            {"login": login, "from": start.isoformat(), "to": end.isoformat()},
            token,
        )
        collection = data["user"]["contributionsCollection"]
        total += collection["totalCommitContributions"] + collection["restrictedContributionsCount"]
        start = end
    return total


def lines_of_code(login: str, repo_full_names: list, token: str) -> tuple:
    headers = {"Authorization": f"bearer {token}"}
    additions = 0
    deletions = 0
    for full_name in repo_full_names:
        url = f"{REST_URL}/repos/{full_name}/stats/contributors"
        response = None
        for _ in range(5):
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 202:
                break
            time.sleep(3)
        if response is None or response.status_code != 200:
            continue
        for contributor in response.json() or []:
            author = contributor.get("author") or {}
            if author.get("login", "").lower() != login.lower():
                continue
            for week in contributor["weeks"]:
                additions += week["a"]
                deletions += week["d"]
    return additions, deletions


def own_repositories(login: str, token: str) -> tuple:
    nodes = []
    cursor = None
    while True:
        user = graphql(USER_QUERY, {"login": login, "cursor": cursor}, token)["user"]
        repos = user["repositories"]
        nodes.extend(repos["nodes"])
        if not repos["pageInfo"]["hasNextPage"]:
            return user, nodes, repos["totalCount"]
        cursor = repos["pageInfo"]["endCursor"]


def fetch_stats(login: str, token: str, include_loc: bool) -> dict:
    user, repo_nodes, repo_count = own_repositories(login, token)
    stats = {
        "uptime": uptime(datetime.date.today()),
        "repos": f"{repo_count:,}",
        "stars": f"{sum(node['stargazerCount'] for node in repo_nodes):,}",
        "commits": f"{total_commits(login, user['createdAt'], token):,}",
        "followers": f"{user['followers']['totalCount']:,}",
    }
    if include_loc:
        contributed = graphql(CONTRIBUTED_QUERY, {"login": login}, token)
        contributed_nodes = contributed["user"]["repositoriesContributedTo"]["nodes"]
        full_names = sorted(
            {node["nameWithOwner"] for node in repo_nodes}
            | {node["nameWithOwner"] for node in contributed_nodes}
        )
        additions, deletions = lines_of_code(login, full_names, token)
        stats["loc"] = f"{additions - deletions:,}"
        stats["loc_add"] = f"{additions:,}"
        stats["loc_del"] = f"{deletions:,}"
    return stats


ALIGN_GROUPS = [("repos", "commits"), ("stars", "followers")]


def align_stats(stats: dict) -> dict:
    for group in ALIGN_GROUPS:
        present = [key for key in group if key in stats]
        if not present:
            continue
        width = max(len(stats[key]) for key in present)
        for key in present:
            stats[key] = stats[key].rjust(width)
    return stats


def replace_field(content: str, key: str, value: str) -> str:
    pattern = f"(<!--{key}-->)(.*?)(<!--/{key}-->)"
    return re.sub(pattern, rf"\g<1>{value}\g<3>", content, flags=re.DOTALL)


def main() -> None:
    svg_file = Path(__file__).resolve().parent.parent / "assets" / "profile-panel.svg"
    content = svg_file.read_text(encoding="utf-8")
    stats = align_stats(fetch_stats(os.environ["GH_USER"], os.environ["GH_TOKEN"], "<!--loc-->" in content))
    for key, value in stats.items():
        content = replace_field(content, key, value)
    svg_file.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
