import base64
import os

import oras.client
import requests
import semver


def get_tagged_versions() -> list[semver.Version]:
    """Returns reverse sorted list of plex versions.
    Converts version tags to semver"""
    print("Getting tagged versions on docker.io")
    client = oras.client.OrasClient(
        hostname="index.docker.io",
        insecure=False,
    )
    tags = client.get_tags("plexinc/pms-docker")

    versions = []

    for t in tags:
        cleaned = t.split("-")[0]
        if "." in cleaned:
            sv = cleaned.split(".")
            cleaned = f"{sv[0]}.{sv[1]}.{sv[2]}+{sv[3]}"
        if semver.Version.is_valid(cleaned):
            ver = semver.Version.parse(cleaned)
            versions.append(ver)
        else:
            print(t, "isn't a version. not tagging")

    versions.sort()
    versions.reverse()
    return versions


def get_current_version() -> semver.Version:
    print("Reading repo's version")
    with open(".version", "r") as f:
        txt = f.read()
    if txt and semver.Version.is_valid(txt):
        return semver.Version.parse(txt)
    else:
        return semver.Version.parse("0.0.0")


def update_repo_version(new_version: semver.Version):
    """ "Update version in github repo. Assumes it's running in the context of github actions"""
    print("trying to update version in repo")
    api_url = os.environ["GITHUB_API_URL"]
    repo = os.environ["GITHUB_REPOSITORY"]
    api_token = os.environ["GH_TOKEN"]
    url = f"{api_url}/repos/{repo}/contents/.version"
    payload = {
        "message": f"Bump version to {new_version}",
        "name": "Auto Update Script",
        "email": "admin@jackhil.de",
        "content": base64.b64encode((str(new_version) + "\n").encode()).decode(),
    }
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_token}",
        "X-Github-Api-Version": "2022-11-28",
    }
    res = requests.get(url, headers)
    if res.status_code == 200:
        data = res.json()
        payload["sha"] = data.get("sha")
    else:
        print("failed to get repo file data")
        return
    res = requests.put(url, headers=headers, json=payload)
    if res.status_code != "200":
        print("failed to update version.\n", res.text)


def main():
    versions = get_tagged_versions()
    repo_version = get_current_version()
    if versions[0] > repo_version:
        print(f"repo version {repo_version} is lower than newest tag {versions[0]}")
        update_repo_version(versions[0])
    else:
        print(
            f"repo version {repo_version} greater or equal to newest tag {versions[0]}"
        )


if __name__ == "__main__":
    main()
