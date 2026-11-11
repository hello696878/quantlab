import asyncio
from datetime import datetime, timedelta, timezone
import os
import re

from .catalog import BY_ID, COMPANIES, FEEDS, FOMC_URL, TREASURY_URL
from .models import Snapshot, SourceBlock
from .providers import Providers


def utcnow():
    return datetime.now(timezone.utc)


def configured_sec(value):
    # Configuration must declare an application/organization AND a contact.
    if not value or len(value) > 250 or "\n" in value or "\r" in value:
        return None
    match = re.search(r"\S+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", value)
    if not match or not value[:match.start()].strip() or match.group(1).lower() in {"example.com", "example.org", "example.net"}:
        return None
    return value


class MonitorService:
    def __init__(self, providers=None, clock=utcnow):
        self.providers = providers or Providers(os.environ.get("MARKET_MONITOR_EIA_API_KEY") or None,
                                               configured_sec(os.environ.get("MARKET_MONITOR_SEC_USER_AGENT")))
        self.clock = clock
        self.cache = {}
        self.inflight = {}
        self.limit = asyncio.Semaphore(4)

    async def source(self, id, label, category, cadence, url, ttl, fetch, configured=True, setup=None):
        meta = dict(id=id, label=label, category=category, cadence=cadence, source_url=url)
        if not configured:
            return SourceBlock(**meta, status="not_configured", message=setup)
        now = self.clock()
        entry = self.cache.get(id)
        if entry and now < entry["next"]:
            return self.view(meta, entry, now)
        if id not in self.inflight:
            async def retrieve():
                try:
                    async with self.limit:
                        data = await fetch()
                    stamp = self.clock()
                    self.cache[id] = {"data": data, "retrieved": stamp, "checked": stamp,
                                      "next": stamp + timedelta(seconds=ttl), "error": None}
                except Exception:
                    stamp = self.clock()
                    self.cache[id] = {"data": entry["data"] if entry else None,
                                      "retrieved": entry["retrieved"] if entry else None, "checked": stamp,
                                      "next": stamp + timedelta(seconds=60),
                                      "error": "Source request or validation failed. Last successful data, if any, are retained; retry after backoff."}
                finally:
                    self.inflight.pop(id, None)
            self.inflight[id] = asyncio.create_task(retrieve())
        await asyncio.shield(self.inflight[id])
        return self.view(meta, self.cache[id], self.clock())

    def view(self, meta, entry, now):
        data = entry["data"]
        status = "unavailable" if data is None else "stale" if entry["error"] else "ready"
        old = data is not None and any((now.date() - obs.observation_date).days > 7 for obs in data.observations)
        if old:
            status = "stale"
        payload = data.model_dump() if data else {}
        if data:
            payload["events"] = [event for event in data.events if event.end_date >= now.date()]
        return SourceBlock(**meta, **payload, status=status,
                           retrieved_at=entry["retrieved"], checked_at=entry["checked"],
                           message=entry["error"] or ("Daily observation is more than seven calendar days old; no exchange-calendar completion claim." if old else None))

    async def snapshot(self, ids, company=None):
        # Validation is repeated here so non-HTTP callers cannot expand requests.
        if len(ids) > 16 or len(set(ids)) != len(ids) or any(id not in BY_ID for id in ids) or company is not None and company not in COMPANIES:
            raise ValueError("Unsupported or oversized Monitor selection")
        today = self.clock().date()
        jobs = []
        selected = list(dict.fromkeys([*ids, *([company] if company and company not in ids else [])]))
        for id in selected:
            item = BY_ID[id]
            if item.source == "yahoo":
                jobs.append(self.source(f"market:{id}", item.name, "market", "daily", item.source_url, 900,
                                        lambda id=id: self.providers.market(id)))
        jobs.append(self.source("treasury", "US Treasury", "rates", "daily", TREASURY_URL, 1800, lambda: self.providers.treasury(today)))
        if any(BY_ID[id].source == "eia" for id in ids):
            jobs.append(self.source("eia", "EIA spot observations", "spot", "daily", "https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm", 1800,
                                    self.providers.eia, bool(self.providers.eia_key), "Set MARKET_MONITOR_EIA_API_KEY on the server."))
        for id, (label, category, url, _) in FEEDS.items():
            jobs.append(self.source(id, label, category, "event", url, 600, lambda id=id: self.providers.feed(id)))
        jobs.append(self.source("fomc", "FOMC calendar", "calendar", "scheduled dates", FOMC_URL, 21600, lambda: self.providers.calendar(today)))
        if company:
            jobs.append(self.source(f"sec:{company}", f"SEC {COMPANIES[company][0]}", "filings", "event",
                                    f"https://www.sec.gov/edgar/browse/?CIK={COMPANIES[company][1]}", 900,
                                    lambda: self.providers.sec(company), bool(self.providers.sec_user_agent), "Set MARKET_MONITOR_SEC_USER_AGENT with your application and real contact address on the server."))
        sources = await asyncio.gather(*jobs)
        return Snapshot(generated_at=self.clock(), sources=sources, company_id=company)
