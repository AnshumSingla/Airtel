"""Static file serving with explicit cache rules for the built PWA.

Without a Cache-Control header, browsers cache index.html and sw.js heuristically for
hours. After an upgrade, that serves an old app against a newer server. The old app has no
CSRF code, so its first action after starting a session fails with "missing or invalid
CSRF token". Hashed assets are safe to cache forever, since a changed file gets a new name.
"""

from __future__ import annotations

import os

from starlette.staticfiles import StaticFiles


class PwaStaticFiles(StaticFiles):
    def file_response(self, full_path, *args, **kwargs):
        response = super().file_response(full_path, *args, **kwargs)
        rel = os.path.relpath(str(full_path), str(self.directory)).replace("\\", "/")
        if rel.startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:  # index.html, sw.js, manifest, icon: always revalidate (cheap, they carry an ETag)
            response.headers["Cache-Control"] = "no-cache"
        return response
