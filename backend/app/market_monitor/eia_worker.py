"""Disposable blocking EIA transport; keys arrive only on stdin, errors are generic."""
import json
import sys

MAX_BYTES = 2 * 1024 * 1024


def fetch(key):
    def guard(event, args):
        if event == "sqlite3.connect":
            raise RuntimeError("Monitor worker refuses SQLite")

    sys.addaudithook(guard)
    from urllib.parse import urlencode
    from urllib.request import HTTPRedirectHandler, Request, build_opener

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    params = [("api_key", key), ("frequency", "daily"), ("data[0]", "value"),
              ("facets[series][]", "RWTC"), ("facets[series][]", "RBRTE"),
              ("sort[0][column]", "period"), ("sort[0][direction]", "desc"), ("length", "40")]
    url = "https://api.eia.gov/v2/petroleum/pri/spt/data/?" + urlencode(params)
    # urllib has no httpx-style INFO URL log containing the required query key.
    with build_opener(NoRedirect()).open(Request(url), timeout=12) as response:
        raw = response.read(MAX_BYTES + 1)
        if response.status != 200 or len(raw) > MAX_BYTES:
            raise ValueError("EIA response refused")
        return raw


def main():
    try:
        raw = sys.stdin.buffer.read(8193)
        if len(raw) > 8192:
            raise ValueError("Invalid EIA configuration")
        key = json.loads(raw).get("api_key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Invalid EIA configuration")
        result = fetch(key)
    except Exception:
        # Never print exception text, query URLs or provider response errors.
        print('{"error":"EIA provider request failed"}')
        return 1
    sys.stdout.buffer.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
