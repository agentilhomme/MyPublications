#!/usr/bin/env python3
"""Fetch a publication list (with per-year citation counts) from OpenAlex
and save it to data/publications.json.

Usage:
    python scripts/fetch_publications.py --author-id A5009459257
    python scripts/fetch_publications.py --orcid 0000-0000-0000-0000
    python scripts/fetch_publications.py --search "Jane Q. Doe"

Run from the repository root.
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.openalex.org"
HEADERS = {"User-Agent": "MyPublications-fetch-script (mailto:anais@agentilhomme.com)"}


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def resolve_author_id(args):
    if args.author_id:
        return args.author_id
    if args.orcid:
        data = fetch_json(f"{API}/authors/orcid:{args.orcid}")
        return data["id"].rsplit("/", 1)[-1]
    if args.search:
        q = urllib.parse.quote(args.search)
        data = fetch_json(f"{API}/authors?search={q}")
        results = data["results"]
        if not results:
            sys.exit(f"No OpenAlex authors found for search: {args.search!r}")
        print("Matches:")
        for a in results:
            print(f"  {a['id']}  {a['display_name']}  works_count={a['works_count']}")
        best = max(results, key=lambda a: a["works_count"])
        print(f"Using best match: {best['display_name']} ({best['id']})")
        return best["id"].rsplit("/", 1)[-1]
    sys.exit("Provide one of --author-id, --orcid, or --search")


def extract_work(w):
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    counts_by_year = sorted(
        w.get("counts_by_year", []), key=lambda c: c["year"]
    )
    authors = [
        a["author"]["display_name"]
        for a in w.get("authorships", [])
        if a.get("author", {}).get("display_name")
    ]
    return {
        "title": w["title"],
        "year": w["publication_year"],
        "type": w["type"],
        "venue": src.get("display_name"),
        "link": w.get("doi") or loc.get("landing_page_url"),
        "authors": authors,
        "cited_by_count_total": w["cited_by_count"],
        "cited_by_count_by_year": {
            str(c["year"]): c["cited_by_count"] for c in counts_by_year
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--author-id", help="OpenAlex author ID, e.g. A5009459257")
    group.add_argument("--orcid", help="ORCID iD, e.g. 0000-0000-0000-0000")
    group.add_argument("--search", help="Author name to search for on OpenAlex")
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent.parent / "data" / "publications.json"),
        help="Output JSON path (default: data/publications.json)",
    )
    args = parser.parse_args()

    author_id = resolve_author_id(args)
    works_data = fetch_json(
        f"{API}/works?filter=author.id:{author_id}&per-page=200"
    )

    works = [extract_work(w) for w in works_data["results"]]
    works.sort(key=lambda w: (w["year"] or 0), reverse=True)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "openalex_author_id": author_id,
                "work_count": len(works),
                "works": works,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved {len(works)} works to {out_path}")


if __name__ == "__main__":
    main()
