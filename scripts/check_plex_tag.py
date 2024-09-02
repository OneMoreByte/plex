import base64
import os
import sys

import oras.client
import requests
import semver


def get_tagged_versions() -> list[tuple[semver.Version, str]]:
    """Returns reverse sorted list of semver Versions and the docker tag they were derived from."""
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
            versions.append((ver, t))
        else:
            print(t, "isn't a version. not tagging")

    versions.sort()
    versions.reverse()
    return versions


def get_current_version() -> semver.Version:
    print("Reading repo's version")
    with open(".version", "r") as f:
        txt = f.read()
    if txt:
        versions = {}
        for l in txt.splitlines():
            l_parts = l.split("=")
            versions[l_parts[0]] = l_parts[1]
        if semver.Version.is_valid(versions.get("SEM_VER_BUILD", "")):
            return semver.Version.parse(versions["SEM_VER_BUILD"])

    return semver.Version.parse("0.0.0")


def update_repo_version(new_version: tuple[semver.Version, str]):
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
        "content": base64.b64encode(
            (
                f"SEM_VER={str(new_version[0]).split('+')[0]}\nSEM_VER_BUILD={str(new_version[0]).replace('+', '-')}\nDOCKER_TAG={new_version[1]}\n"
            ).encode()
        ).decode(),
    }
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_token}",
    }
    res = requests.get(url, headers)
    if res.status_code == 200:
        data = res.json()
        payload["sha"] = data.get("sha")
    else:
        print("failed to get repo file data")
        sys.exit(1)
    res = requests.put(url, headers=headers, json=payload)
    if res.status_code != 200:
        print("failed to update version.\n", res.text)
        sys.exit(1)
    res = requests.post(
        f"{api_url}/repos/{repo}/actions/workflows/build-containers.yaml/dispatches",
        json={"ref": "refs/heads/main"},
        headers=headers,
    )
    if res.status_code != 204:
        print("failed to trigger a rebuild\n", res.text)
        sys.exit(1)


def main():
    versions = get_tagged_versions()
    repo_version = get_current_version()
    latest_remote_version, remote_tag = versions[0]
    if latest_remote_version > repo_version:
        print(f"repo version {repo_version} is lower than newest tag {remote_tag}")
        update_repo_version((latest_remote_version, remote_tag))
    else:
        print(
            f"repo version {repo_version} greater or equal to newest tag {remote_tag}"
        )


if __name__ == "__main__":
    main()
