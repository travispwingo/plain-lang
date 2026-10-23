"""The web: reading pages and APIs, and sending data."""

import json
import re
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit

from ..problems import Problem
from ..registry import List, Text, Value, step, value
from ..values import Record, show_value
from .files import decode, json_text, parse_json

TOPIC = "The web"


def clean_address(url):
    """Encode spaces and other characters a browser's address bar would encode."""
    return quote(url, safe=":/?#[]@!$&'()*+,;=%~")


def site_of(url):
    return urlsplit(url).netloc or url


def status_problem(reply, url):
    code = reply.status
    site = site_of(url)
    said = ""
    try:
        text = decode(reply.body).strip()
        if text.startswith("{"):
            data = json.loads(text)
            said = data.get("message") or data.get("error") or ""
            if isinstance(said, dict):      # {"error": {"code": 400, "message": "..."}}
                said = said.get("message") or said.get("error_description") or ""
            said = said if isinstance(said, str) else ""
        elif text and len(text) < 120 and "<" not in text:
            said = text
    except (ValueError, AttributeError):
        said = ""
    short = url.split("://", 1)[-1]
    if code == 404:
        return Problem(f"Check the address. There's nothing at {short} (code 404).",
                       "The website answered, but it has no page at that address.")
    if code in (401, 403):
        return Problem(f"Check whether {site} lets you read this. It refused the request (code {code}).",
                       f"It said: {said}" if said else None)
    if code == 429:
        return Problem("Wait a minute, then run this again.",
                       f"{site} says you've asked too often (code 429).")
    if code >= 500:
        return Problem("Try again later.", f"{site} had a problem of its own (code {code}).")
    return Problem(f"Check the address and try again. {site} answered with code {code}.",
                   f"It said: {said}" if said else None)


def check_address(url):
    if not url.lower().startswith(("https://", "http://")):
        raise Problem('Start the web address with "https://".', f'"{url}" isn\'t a web address.')


def body_value(reply):
    text = decode(reply.body)
    kind = (reply.kind or "").lower()
    stripped = text.lstrip()
    if "json" in kind or (stripped[:1] in "{[" and stripped):
        try:
            return parse_json(text)
        except ValueError:
            if "json" in kind:
                raise
    return text


def read_web(run, url, raw=False):
    check_address(url)
    reply = run.host.web("GET", clean_address(url), None, None)
    if not 200 <= reply.status < 300:
        raise status_problem(reply, url)
    return decode(reply.body) if raw else body_value(reply)


@step("send {data} to {address}", example='send message to "https://example.com/api" and call it reply',
      effects={"internet"}, topic=TOPIC)
def send(run, data: Value, address: Text) -> Value:
    """Sends records and lists as JSON, and anything else as text. The reply comes back the way "read" gives it."""
    check_address(address)
    if isinstance(data, (Record, list)):
        body, kind = json_text(data).encode(), "application/json"
    else:
        body, kind = show_value(data).encode(), "text/plain; charset=utf-8"
    reply = run.host.web("POST", clean_address(address), body, kind)
    if not 200 <= reply.status < 300:
        raise status_problem(reply, address)
    return body_value(reply)


class PageText(HTMLParser):
    SKIP = {"script", "style", "noscript", "head"}
    BLOCKS = {"p", "br", "div", "li", "ul", "ol", "table", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}
    CELLS = {"td", "th"}

    def __init__(self):
        super().__init__()
        self.parts, self.links, self.skipping = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        if tag in self.BLOCKS:
            self.parts.append("\n")
        elif tag in self.CELLS:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        if tag in self.BLOCKS:
            self.parts.append("\n")
        elif tag in self.CELLS:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def page_parts(page):
    parser = PageText()
    parser.feed(page if isinstance(page, str) else show_value(page))
    return parser


@value("the text of {page}", example="show the text of page", topic=TOPIC)
def text_of(run, page: Text) -> Text:
    """The words on a web page, without its formatting codes."""
    text = "".join(page_parts(page).parts)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


@value("the links of {page}", example="show the links of page", topic=TOPIC)
def links_of(run, page: Text) -> List:
    """A list of the addresses that a web page links to."""
    return page_parts(page).links
