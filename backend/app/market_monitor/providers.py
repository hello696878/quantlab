import asyncio
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import sys

import httpx

from .catalog import BY_ID, COMPANIES, FEEDS, FOMC_URL
from .parsers import MAX_BYTES, parse_eia, parse_feed, parse_fomc, parse_market, parse_sec, parse_treasury, series_observation

HTTP_TOTAL_SECONDS = 15
EIA_TOTAL_SECONDS = 15
TREASURY_TOTAL_SECONDS = 15
TREASURY_CURRENT_SECONDS = 9
TREASURY_OPTIONAL_SECONDS = 6
TREASURY_MONTHLY_XML = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
TREASURY_DAILY_XML = "https://home.treasury.gov/sites/default/files/interest-rates/yield.xml"
TREASURY_FETCH_ERRORS = (httpx.HTTPError, TimeoutError, ValueError)


class Providers:
    def __init__(self, eia_key=None, sec_user_agent=None):
        self.eia_key = eia_key
        self.sec_user_agent = sec_user_agent
        self._sec_lock = asyncio.Lock()

    async def get(self, url, params=None, headers=None):
        # URLs are internal constants. No user URL, redirect or provider symbol input.
        async with asyncio.timeout(HTTP_TOTAL_SECONDS):
            async with httpx.AsyncClient(timeout=httpx.Timeout(12), follow_redirects=False) as client:
                async with client.stream("GET", url, params=params, headers=headers) as response:
                    response.raise_for_status()
                    if response.status_code != 200:
                        raise ValueError("Unexpected source status")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_BYTES:
                            raise ValueError("Source response exceeds limit")
                    return bytes(data)

    async def market(self, id):
        # A process bounds total yfinance work and isolates its mutable caches.
        def run():
            result = subprocess.run([sys.executable, "-m", "app.market_monitor.market_worker", id],
                                    cwd=Path(__file__).resolve().parents[2], capture_output=True, timeout=25)
            if result.returncode or len(result.stdout) > 32_768:
                raise ValueError("Daily provider unavailable")
            return parse_market(json.loads(result.stdout), id)
        return await asyncio.to_thread(run)

    async def treasury(self, today):
        first = today.replace(day=1)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + TREASURY_TOTAL_SECONDS

        async def read(last_date, first_date=None, *, seconds):
            url, params = TREASURY_DAILY_XML, None
            if first_date is not None:
                url = TREASURY_MONTHLY_XML
                params = {"data": "daily_treasury_yield_curve", "field_tdr_date_value_month": first_date.strftime("%Y%m")}
            now = loop.time()
            if now >= deadline:
                raise TimeoutError("Treasury retrieval deadline exceeded")
            async with asyncio.timeout_at(min(deadline, now + seconds)):
                payload = await self.get(url, params)
                return parse_treasury([payload], first_date=first_date, last_date=last_date)

        try:
            current = await read(today, first, seconds=TREASURY_CURRENT_SECONDS)
        except TREASURY_FETCH_ERRORS:
            # The daily file is an alternative, not another source to merge
            # into already validated monthly observations.
            fallback = await read(today, seconds=TREASURY_OPTIONAL_SECONDS)
            fallback.message = " ".join(note for note in (
                "Current-month Treasury publication could not be verified; showing observations from the official daily XML file.",
                fallback.message,
            ) if note)
            return fallback

        if all(obs.previous_date is not None for obs in current.observations):
            return current
        previous_day = first - timedelta(days=1)
        try:
            history = await read(previous_day, previous_day.replace(day=1), seconds=TREASURY_OPTIONAL_SECONDS)
            prior = {obs.instrument_id: obs for obs in history.observations}
            # Only fill comparisons. History cannot supply missing current
            # maturities, overwrite values, or create a cross-date spread.
            current.observations = [
                series_observation(obs.instrument_id, [(earlier.observation_date, earlier.value),
                                                      (obs.observation_date, obs.value)], bps=True)
                if obs.previous_date is None and (earlier := prior.get(obs.instrument_id)) else obs
                for obs in current.observations
            ]
        except TREASURY_FETCH_ERRORS:
            pass
        if any(obs.previous_date is None for obs in current.observations):
            current.message = " ".join(note for note in (
                current.message, "Some prior Treasury comparisons are unavailable.",
            ) if note)
        return current

    async def feed(self, id):
        _, _, url, hosts = FEEDS[id]
        return parse_feed(await self.get(url), id, hosts)

    async def eia(self):
        if not self.eia_key:
            raise ValueError("EIA is not configured")
        # The blocking, key-bearing request is isolated in a disposable process.
        # subprocess.run kills and waits on timeout; cancelling a thread alone
        # would leave the underlying provider work running. The key uses stdin.
        def fetch():
            result = subprocess.run([sys.executable, "-m", "app.market_monitor.eia_worker"],
                                    cwd=Path(__file__).resolve().parents[2], capture_output=True,
                                    input=json.dumps({"api_key": self.eia_key}).encode("utf-8"),
                                    timeout=EIA_TOTAL_SECONDS)
            if result.returncode or len(result.stdout) > MAX_BYTES:
                raise ValueError("EIA provider unavailable")
            return result.stdout
        return parse_eia(json.loads(await asyncio.to_thread(fetch)))

    async def sec(self, company):
        if not self.sec_user_agent:
            raise ValueError("SEC is not configured")
        async with self._sec_lock:
            # At most one SEC request per second per local process, plus 15m cache.
            try:
                raw = await self.get(f"https://data.sec.gov/submissions/CIK{COMPANIES[company][1]}.json",
                                     headers={"User-Agent": self.sec_user_agent, "Accept-Encoding": "gzip, deflate"})
                return parse_sec(json.loads(raw), company)
            finally:
                await asyncio.sleep(1)

    async def calendar(self, today):
        return parse_fomc(await self.get(FOMC_URL), today)
