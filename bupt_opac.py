"""Read-only client and small HTTP gateway for BUPT's public OPAC."""

from __future__ import annotations

import argparse
import html
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
import json
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen


BASE_URL = "https://opac.bupt.edu.cn"
FIELDS = {
    "title": "TITLE",
    "author": "AUTHOR",
    "year": "PUBDATE",
    "publisher": "PUBLISHER",
    "isbn": "ISN_SHOW",  # The site's “标准号” also covers ISSN.
    "subject": "SUBJECT",
}
CAMPUSES = {"all": "all", "main": "A01", "hongfu": "A02", "shahe": "A03"}
PAGE_SIZES = {10, 20, 30, 50, 100}
ID_PATTERN = re.compile(r"[A-Za-z0-9]+")
SPACE = re.compile(r"\s+")
TAG = re.compile(r"<[^>]+>")


class OPACError(Exception):
    pass


def clean(value: object) -> str:
    return SPACE.sub(" ", html.unescape(TAG.sub("", str(value or "")))).strip()


class DetailParser(HTMLParser):
    """Extract bibliographic text and the public holdings table from server HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.paragraphs: list[str] = []
        self.headers: list[str] = []
        self.table_headers: list[str] = []
        self.rows: list[list[dict[str, str]]] = []
        self.capture_tag: str | None = None
        self.capture_text: list[str] = []
        self.table_depth = 0
        self.in_head = False
        self.in_holdings = False
        self.in_row = False
        self.row: list[dict[str, str]] = []
        self.cell: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs)
        if tag == "h3" and not self.title and self.capture_tag is None:
            self.capture_tag, self.capture_text = "h3", []
        elif tag == "p" and self.capture_tag is None:
            self.capture_tag, self.capture_text = "p", []
        if tag == "table":
            self.table_depth += 1
            self.table_headers = []
        elif tag == "thead" and self.table_depth:
            self.in_head = True
        elif tag == "tbody" and attrs.get("id") == "guancanglist":
            self.in_holdings = True
            self.headers = self.table_headers[:]
        elif tag == "tr" and (self.in_head or self.in_holdings):
            self.in_row, self.row = True, []
        elif tag in ("td", "th") and self.in_row:
            self.cell = {"text": "", "href": ""}
        elif tag == "a" and self.cell is not None:
            self.cell["href"] = attrs.get("href") or ""

    def handle_data(self, data: str) -> None:
        if self.capture_tag is not None:
            self.capture_text.append(data)
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == self.capture_tag:
            value = clean("".join(self.capture_text))
            if tag == "h3" and not self.title:
                self.title = value
            elif tag == "p" and value:
                self.paragraphs.append(value)
            self.capture_tag, self.capture_text = None, []
        if tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = clean(self.cell["text"])
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.in_row:
            if self.in_head:
                self.table_headers = [cell["text"] for cell in self.row]
            elif self.in_holdings and self.row:
                self.rows.append(self.row)
            self.in_row = False
        elif tag == "thead":
            self.in_head = False
        elif tag == "tbody" and self.in_holdings:
            self.in_holdings = False
        elif tag == "table" and self.table_depth:
            self.table_depth -= 1


class OPACClient:
    def __init__(self, *, timeout: float = 15, min_interval: float = 1) -> None:
        self.timeout = timeout
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last_request = 0.0

    def _request(
        self, path: str, form: dict[str, str] | None = None, *, referer: str = "/search-full-result.html"
    ) -> bytes:
        with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
        data = urlencode(form).encode("utf-8") if form is not None else None
        request = Request(
            BASE_URL + path,
            data=data,
            headers={
                "User-Agent": "BUPT-OPAC-readonly/1.0 (public catalogue client)",
                "Accept": "application/json, text/html;q=0.9",
                "Referer": BASE_URL + referer,
                **({"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"} if data is not None else {}),
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise OPACError(f"图书馆请求失败：{exc}") from exc

    def _json(self, path: str, form: dict[str, str], *, referer: str) -> dict:
        try:
            result = json.loads(self._request(path, form, referer=referer))
        except (ValueError, UnicodeDecodeError) as exc:
            raise OPACError("图书馆接口未返回有效 JSON") from exc
        if not isinstance(result, dict):
            raise OPACError("图书馆接口返回了意外的数据结构")
        if result.get("result", {}).get("code") != 0:
            raise OPACError(result.get("result", {}).get("msg", "查询失败"))
        return result

    def search(
        self, keyword: str, *, field: str = "title", campus: str = "all",
        page: int = 1, page_size: int = 20,
    ) -> dict:
        keyword = keyword.strip()
        if not keyword or len(keyword) > 200:
            raise ValueError("q 必须为 1–200 个字符")
        if field not in FIELDS:
            raise ValueError(f"field 可选：{', '.join(FIELDS)}")
        if campus not in CAMPUSES:
            raise ValueError(f"campus 可选：{', '.join(CAMPUSES)}")
        if page < 1 or page > 1000 or page_size not in PAGE_SIZES:
            raise ValueError("page 范围为 1–1000；page_size 可选 10、20、30、50、100")
        body = {
            "keyword": keyword,
            "solrType": FIELDS[field],
            "xiaoqu": CAMPUSES[campus],
            "pageNo": str(page),
            "pageSize": str(page_size),
            "classSearch": "0",
            "searchPrecision": "",
        }
        result = self._json("/search-full-result.json", body, referer="/search-full-result.html")
        items = []
        for record in result.get("data") or []:
            record_id = str(record.get("recCtrlId") or "")
            items.append({
                "id": record_id,
                "title": clean(record.get("title")),
                "authors": clean(record.get("authors")),
                "publisher": clean(record.get("publisher")),
                "publication_year": clean(record.get("pubdateDate")),
                "isbn_issn": clean(record.get("isn")),
                "call_number": clean(record.get("bookSearchNo")),
                "holdings_count": record.get("guancangCount"),
                "available_count": record.get("kejieCount"),
                "detail_url": BASE_URL + f"/bookInfo_{record_id}.html",
            })
        return {
            "query": {"q": keyword, "field": field, "campus": campus, "page": page, "page_size": page_size},
            "total": result.get("total", 0),
            "total_pages": result.get("totalPage", 0),
            "items": items,
        }

    def detail(self, record_id: str) -> dict:
        if not ID_PATTERN.fullmatch(record_id) or len(record_id) > 40:
            raise ValueError("无效的馆藏记录 ID")
        raw = self._request(f"/bookInfo_{record_id}.html")
        parser = DetailParser()
        parser.feed(raw.decode("utf-8", errors="replace"))
        if not parser.title:
            raise OPACError("详情页中未找到书刊记录")
        metadata = {}
        label_map = {
            "ISBN/ISSN": "isbn_issn", "出版": "publication", "责任者": "responsibility",
            "中图分类号": "classification", "载体形态": "physical_description",
            "并列题名": "parallel_title", "价格": "price",
        }
        for paragraph in parser.paragraphs:
            for label, key in label_map.items():
                if paragraph.startswith(label + "："):
                    metadata.setdefault(key, paragraph.split("：", 1)[1].strip())
        holdings = []
        for row in parser.rows:
            by_header = {label: row[i] for i, label in enumerate(parser.headers) if i < len(row)}
            def cell(label: str) -> str:
                return by_header.get(label, {}).get("text", "")
            nav = by_header.get("架位导航", {}).get("href", "")
            host = urlsplit(nav).hostname
            try:
                private_navigation = bool(host and ip_address(host).is_private)
            except ValueError:
                private_navigation = False
            holdings.append({
                "department": cell("馆藏部门"),
                "barcode": cell("图书条码"),
                "call_number": cell("索书号"),
                "accession_number": cell("登录号"),
                "volume": cell("卷期"),
                "status": cell("状态"),
                "navigation_url": nav,
                "navigation_is_private_network": private_navigation,
            })
        detail = {
            "id": record_id, "title": parser.title, **metadata,
            "holdings": holdings, "detail_url": BASE_URL + f"/bookInfo_{record_id}.html",
        }
        if 'id="qikanInfos"' in raw.decode("utf-8", errors="replace"):
            referer = f"/bookInfo_{record_id}.html"
            form = {"rec_ctrl_id": record_id}
            current = self._json("/qikanInfos.json", form, referer=referer).get("data") or []
            bound = self._json("/bindings.json", form, referer=referer).get("data") or []
            detail["periodical_current"] = [{
                "library": clean(item.get("name")),
                "current_year": clean(item.get("curYear")),
                "current_count": item.get("curCount"),
                "previous_year": clean(item.get("lastYear")),
                "previous_count": item.get("lastCount"),
            } for item in current]
            issues = []
            for library in current:
                seen_years = set()
                for year_key, count_key in (("curYear", "curCount"), ("lastYear", "lastCount")):
                    year = str(library.get(year_key) or "")
                    if not year or year in seen_years or int(library.get(count_key) or 0) <= 0:
                        continue
                    seen_years.add(year)
                    issue_form = {"rec_ctrl_id": record_id, "library_id": str(library.get("libID") or ""), "s_year": year}
                    records = self._json("/serialnobinding.json", issue_form, referer=referer).get("data") or []
                    issues.extend({
                        "library": clean(library.get("name")),
                        "year": clean(item.get("year")),
                        "volume": clean(item.get("volume")),
                        "issue": clean(item.get("issue")),
                        "status": clean(item.get("codeDesc")),
                        "shelf_number": clean(item.get("shelfDistribute")),
                        "department": clean(item.get("departmentName")),
                    } for item in records)
            detail["current_issues"] = issues
            detail["holdings"] = [{
                "department": clean(item.get("departmentName")),
                "barcode": clean(item.get("bookBarcode")),
                "call_number": clean(item.get("bookSearchNo")),
                "accession_number": clean(item.get("accessNo")),
                "volume": clean(item.get("issus")),
                "status": clean(item.get("circul")),
                "navigation_url": "",
                "navigation_is_private_network": False,
            } for item in bound]
        return detail


CLIENT = OPACClient()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlsplit(self.path)
        query = parse_qs(path.query)
        value = lambda key, default="": query.get(key, [default])[0]
        try:
            if path.path == "/api/search":
                payload = CLIENT.search(
                    value("q"), field=value("field", "title"), campus=value("campus", "all"),
                    page=int(value("page", "1")), page_size=int(value("page_size", "20")),
                )
            elif re.fullmatch(r"/api/books/[A-Za-z0-9]+", path.path):
                payload = CLIENT.detail(path.path.rsplit("/", 1)[-1])
            else:
                self._json(404, {"error": "接口不存在"})
                return
            self._json(200, payload)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except OPACError as exc:
            self._json(502, {"error": str(exc)})

    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="北京邮电大学图书馆公开书刊检索")
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="检索书刊")
    search.add_argument("keyword")
    search.add_argument("--field", choices=FIELDS, default="title")
    search.add_argument("--campus", choices=CAMPUSES, default="all")
    search.add_argument("--page", type=int, default=1)
    search.add_argument("--page-size", type=int, choices=sorted(PAGE_SIZES), default=20)
    detail = commands.add_parser("detail", help="查看书刊详情和馆藏")
    detail.add_argument("record_id")
    serve = commands.add_parser("serve", help="启动本地只读 HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command == "search":
            result = CLIENT.search(args.keyword, field=args.field, campus=args.campus,
                                   page=args.page, page_size=args.page_size)
        elif args.command == "detail":
            result = CLIENT.detail(args.record_id)
        else:
            server = ThreadingHTTPServer((args.host, args.port), Handler)
            print(f"http://{args.host}:{args.port}", flush=True)
            server.serve_forever()
            return
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OPACError) as exc:
        parser.exit(1, f"错误：{exc}\n")


if __name__ == "__main__":
    main()
