"""CLI for project + API key management.

    python manage.py create-project "Acme Pay"
    python manage.py rotate-key 3

Keys are shown once, in plaintext, at creation/rotation time. The server only
ever stores a hash, so there is no way to recover a lost key -- rotate it.
"""
import argparse

from server import db


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    create = sub.add_parser("create-project", help="Create a new project and its API key")
    create.add_argument("name")

    rotate = sub.add_parser("rotate-key", help="Issue a new API key for a project, invalidating the old one")
    rotate.add_argument("project_id", type=int)

    a = ap.parse_args()
    db.init()

    if a.cmd == "create-project":
        p = db.create_project(a.name)
        print(f"created project {p['id']} ({p['name']}). api key (shown once): {p['api_key']}")
    elif a.cmd == "rotate-key":
        try:
            p = db.rotate_key(a.project_id)
        except KeyError as e:
            raise SystemExit(str(e))
        print(f"rotated key for project {p['id']} ({p['name']}). new api key (shown once): {p['api_key']}")


if __name__ == "__main__":
    main()
