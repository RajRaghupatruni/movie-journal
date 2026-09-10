"""Static SPA serving for the one-origin production deployment."""

from pathlib import Path

from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if (
                exc.status_code != 404
                or not self._is_spa_route(path)
                or not self._is_spa_route(scope.get("path", ""))
            ):
                raise
            response = await super().get_response("index.html", scope)
        if response.status_code == 200:
            headers = MutableHeaders(raw=response.raw_headers)
            if path == "" or path == "index.html" or "." not in Path(path).name:
                headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            elif path.startswith("assets/"):
                headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                headers["Cache-Control"] = "public, max-age=3600"
        return response

    @staticmethod
    def _is_spa_route(path: str) -> bool:
        # A missing asset must remain a real 404; only extensionless client routes fall back.
        path = path.strip("/")
        if path in {"api", "healthz", "readyz"} or path.startswith("api/"):
            return False
        return "." not in Path(path).name
