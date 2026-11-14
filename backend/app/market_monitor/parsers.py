"""Bounded structured parsing. Fixtures are never production fallback data."""
import calendar
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import math
import re
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET

from .catalog import BY_ID, COMPANIES, FOMC_URL
from .models import CalendarEvent, Filing, NewsItem, Observation, SourceData

MAX_BYTES = 2 * 1024 * 1024


def iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Expected a date-only observation")
    return date.fromisoformat(value)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("Expected a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Expected a finite number")
    return result


def xml(data):
    if len(data) > MAX_BYTES or re.search(br"<!\s*(DOCTYPE|ENTITY)", data, re.I):
        raise ValueError("Oversized or unsupported XML")
    try:
        return ET.fromstring(data)
    except (ET.ParseError, LookupError):
        raise ValueError("Malformed source XML") from None


def safe_link(value, hosts):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise ValueError("Invalid source link")
    parts = urlsplit(value)
    if parts.scheme != "https" or parts.hostname not in hosts or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError("Unsafe source link")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def text(value):
    parser = TextOnly()
    parser.feed(value or "")
    return " ".join(" ".join(parser.parts).split())[:400]


def parse_feed(data, source, hosts):
    root = xml(data)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("Expected RSS channel")
    entries = root.findall("./channel/item")
    if len(entries) > 500:
        raise ValueError("Oversized RSS item collection")
    seen, items = set(), []
    for item in entries:
        title = text(item.findtext("title"))
        try:
            link = safe_link((item.findtext("link") or "").strip(), hosts)
        except ValueError:
            continue
        if not title:
            continue
        guid = (item.findtext("guid") or link).strip()[:2048]
        if guid in seen or link in seen:
            continue
        seen.update((guid, link))
        published = None
        raw = item.findtext("pubDate")
        if raw:
            try:
                published = parsedate_to_datetime(raw)
                if published.tzinfo is None:
                    published = None
            except (ValueError, TypeError, OverflowError):
                pass
        items.append(NewsItem(id=f"{source}:{guid}", title=title, url=link, published_at=published))
        if len(items) == 30:
            break
    if entries and not items:
        raise ValueError("No usable feed items")
    return SourceData(items=items)


def series_observation(id, points, *, bps=False, timezone=None):
    # Same-date duplicates have a deterministic last-record policy.
    points = sorted(dict(points).items())
    if not points:
        return None
    day, value = points[-1]
    change, prior_date = None, None
    if len(points) > 1:
        prior_date, prior = points[-2]
        if bps:
            change = (value - prior) * (1 if BY_ID[id].unit == "bps" else 100)
        elif prior > 0:
            change = (value / prior - 1) * 100
    return Observation(instrument_id=id, value=value, observation_date=day, unit=BY_ID[id].unit,
                       change=change, change_unit="bps" if bps else "%", previous_date=prior_date,
                       timezone=timezone, session_complete=None)


def parse_treasury(payloads, *, first_date=None, last_date=None):
    rows = {}
    ns = {"m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata", "d": "http://schemas.microsoft.com/ado/2007/08/dataservices"}
    for data in payloads:
        root = xml(data)
        properties = root.findall(".//m:properties", ns)
        if root.tag not in {"feed", "{http://www.w3.org/2005/Atom}feed"} or (
            not properties and root.findall("./{*}entry")
        ):
            raise ValueError("Unsupported Treasury XML structure")
        for prop in properties:
            raw = prop.findtext("d:NEW_DATE", namespaces=ns)
            if not raw:
                raise ValueError("Missing Treasury date")
            day = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
            if (first_date is not None and day < first_date) or (last_date is not None and day > last_date):
                continue
            values = {}
            for key in ("BC_2YEAR", "BC_10YEAR", "BC_30YEAR"):
                elem = prop.find(f"d:{key}", ns)
                raw_value = elem.text if elem is not None else None
                values[key] = None if raw_value in (None, "", "N/A", ".") else number(raw_value)
            rows[day] = values
    observations = []
    maturities = ("treasury2y", "treasury10y", "treasury30y")
    for id in maturities:
        points = [(day, row[BY_ID[id].symbol]) for day, row in rows.items() if row[BY_ID[id].symbol] is not None]
        obs = series_observation(id, points, bps=True)
        if obs:
            observations.append(obs)
    spreads = [(day, (row["BC_10YEAR"] - row["BC_2YEAR"]) * 100) for day, row in rows.items()
               if row["BC_10YEAR"] is not None and row["BC_2YEAR"] is not None]
    spread = series_observation("treasury10y2y", spreads, bps=True)
    if spread:
        observations.append(spread)
    if not observations:
        raise ValueError("No usable Treasury observations")
    message = "Some Treasury series have no observation." if len(observations) < len(maturities) + 1 else None
    return SourceData(observations=observations, message=message)


def parse_market(data, id):
    instrument = BY_ID[id]
    if data.get("symbol") != instrument.symbol or data.get("currency") != instrument.currency:
        raise ValueError("Provider identity mismatch")
    expected = {"index": "INDEX", "company": "EQUITY", "futures_reference": "FUTURE"}[instrument.kind]
    if data.get("instrument_type") != expected:
        raise ValueError("Provider instrument kind mismatch")
    rows = data.get("rows")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10:
        raise ValueError("Missing or oversized daily observations")
    points = [(iso_date(row["date"]), number(row["close"])) for row in rows]
    if any(value <= 0 for _, value in points):
        raise ValueError("Invalid market observation")
    return SourceData(observations=[series_observation(id, points, timezone=data.get("timezone"))])


def parse_eia(data):
    rows = data.get("response", {}).get("data")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 40:
        raise ValueError("Invalid EIA data collection")
    points = {"RWTC": [], "RBRTE": []}
    for row in rows:
        if row.get("series") not in points or row.get("units") not in ("$/BBL", "Dollars per Barrel"):
            raise ValueError("EIA series or units mismatch")
        day = iso_date(row["period"])
        if row.get("value") not in (None, ""):
            points[row["series"]].append((day, number(row["value"])))
    observations = [series_observation(id, points[BY_ID[id].symbol]) for id in ("eia_wti", "eia_brent")]
    if not any(observations):
        raise ValueError("No usable EIA observations")
    return SourceData(observations=[obs for obs in observations if obs])


def parse_sec(data, company_id):
    ticker, cik = COMPANIES[company_id]
    if str(data.get("cik", "")).zfill(10) != cik or not isinstance(data.get("tickers"), list) or ticker not in data["tickers"] or not isinstance(data.get("name"), str) or not data["name"].strip():
        raise ValueError("SEC issuer mismatch")
    recent = data.get("filings", {}).get("recent", {})
    keys = ("accessionNumber", "form", "filingDate", "primaryDocument")
    if any(not isinstance(recent.get(key), list) for key in keys):
        raise ValueError("Missing SEC filing columns")
    count = len(recent[keys[0]])
    if count > 3000 or any(len(recent[key]) != count for key in keys):
        raise ValueError("Misaligned SEC filing columns")
    accepted = recent.get("acceptanceDateTime", [None] * count)
    if not isinstance(accepted, list) or len(accepted) != count:
        raise ValueError("Misaligned SEC acceptance column")
    filings = []
    for accession, form, filed, doc, raw_time in zip(*(recent[key] for key in keys), accepted):
        if form not in {"10-K", "10-Q", "8-K", "10-K/A", "10-Q/A", "8-K/A"}:
            continue
        if not isinstance(accession, str) or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
            raise ValueError("Invalid accession")
        day = iso_date(filed)
        if not isinstance(doc, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", doc) or doc in (".", ".."):
            raise ValueError("Invalid primary document")
        timestamp = datetime.fromisoformat(raw_time.replace("Z", "+00:00")) if raw_time else None
        if timestamp and timestamp.tzinfo is None:
            raise ValueError("Missing acceptance timezone")
        filings.append(Filing(accession=accession, form=form, filing_date=day, accepted_at=timestamp,
                              url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{doc}"))
    filings.sort(key=lambda filing: (filing.filing_date, filing.accession), reverse=True)
    return SourceData(filings=filings[:20])


class FomcParser(HTMLParser):
    def __init__(self, today):
        super().__init__(convert_charrefs=True)
        self.today, self.year, self.month = today, None, None
        self.heading, self.field, self.depth, self.buffer = None, None, 0, []
        self.events = []

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "").split()
        if tag == "h4":
            self.heading = []
        if tag == "div":
            if self.field:
                self.depth += 1
            elif "fomc-meeting__month" in classes or "fomc-meeting__date" in classes:
                self.field = "month" if "fomc-meeting__month" in classes else "date"
                self.buffer, self.depth = [], 1

    def handle_data(self, data):
        if self.heading is not None:
            self.heading.append(data)
        if self.field:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "h4" and self.heading is not None:
            match = re.search(r"\b(20\d{2}) FOMC Meetings\b", "".join(self.heading))
            self.year = int(match.group(1)) if match else None
            self.heading = None
        if tag == "div" and self.field:
            self.depth -= 1
            if self.depth == 0:
                value = "".join(self.buffer).strip()
                if self.field == "month":
                    self.month = value
                else:
                    self.add_event(value)
                self.field = None

    def add_event(self, value):
        if self.year not in (self.today.year, self.today.year + 1) or not self.month:
            return
        months = self.month.replace(" ", "").split("/")
        lookup = {name: index for index, name in enumerate(calendar.month_name) if name}
        match = re.fullmatch(r"(\d{1,2})(?:-(\d{1,2}))?\*?", value)
        if not match or not 1 <= len(months) <= 2 or any(month not in lookup for month in months):
            raise ValueError("Unsupported FOMC date range")
        start = date(self.year, lookup[months[0]], int(match.group(1)))
        end = date(self.year, lookup[months[-1]], int(match.group(2) or match.group(1)))
        if end < start:
            raise ValueError("Invalid FOMC range")
        if end >= self.today:
            self.events.append(CalendarEvent(id=f"fomc:{start}:{end}", title="FOMC meeting", start_date=start, end_date=end, url=FOMC_URL))


def parse_fomc(data, today):
    if len(data) > MAX_BYTES:
        raise ValueError("Calendar response too large")
    parser = FomcParser(today)
    parser.feed(data.decode("utf-8"))
    if not parser.events:
        raise ValueError("No supported upcoming FOMC schedule found")
    return SourceData(events=sorted({event.id: event for event in parser.events}.values(), key=lambda event: event.start_date)[:12])
