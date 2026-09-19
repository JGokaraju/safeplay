"""GitHub Contents API helpers shared by the laptop monitor and the Raspberry Pi."""
import base64
import os
import time

import requests

API = "https://api.github.com"


class GitHubIO:
    def __init__(self, token=None, repo=None):
        self.repo = repo or os.environ["GITHUB_REPO"]
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token or os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
        })
        self._etags = {}
        self._cache = {}

    def _url(self, path):
        return f"{API}/repos/{self.repo}/contents/{path}"

    def _get(self, path, use_etag=False):
        """Returns (content_bytes, sha). With use_etag, unchanged files return cached data (304s are free)."""
        headers = {}
        if use_etag and path in self._etags:
            headers["If-None-Match"] = self._etags[path]
        r = self.s.get(self._url(path), headers=headers, timeout=30)
        if r.status_code == 304:
            return self._cache[path]
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        j = r.json()
        if not j.get("content") or j.get("encoding") != "base64":
            # empty or >1MB files come back without inline content; use the raw media type
            raw = self.s.get(self._url(path), headers={"Accept": "application/vnd.github.raw"}, timeout=60)
            raw.raise_for_status()
            data = raw.content
        else:
            data = base64.b64decode(j["content"])
        result = (data, j["sha"])
        if use_etag:
            self._etags[path] = r.headers.get("ETag", "")
            self._cache[path] = result
        return result

    def read_bytes(self, path, use_etag=False):
        return self._get(path, use_etag)[0]

    def read_text(self, path, use_etag=False):
        data = self._get(path, use_etag)[0]
        return None if data is None else data.decode("utf-8").strip()

    def write_file(self, path, data, message=None, retries=4):
        if isinstance(data, str):
            data = data.encode("utf-8")
        for attempt in range(retries):
            _, sha = self._get(path)
            body = {"message": message or f"update {path}",
                    "content": base64.b64encode(data).decode()}
            if sha:
                body["sha"] = sha
            r = self.s.put(self._url(path), json=body, timeout=60)
            if r.status_code in (409, 422) and attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            r.raise_for_status()
            return
