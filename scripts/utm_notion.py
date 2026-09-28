#!/usr/bin/env python3
"""Register one Feishu submission in the matching Notion host page."""

from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import re
import secrets
import string
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.notion_api import NotionAPI
from scripts.clean_cli import run_clean_cli
from scripts.vm_inventory import (
    InventoryError,
    claim_available_vm,
    claim_exact_available_vm,
    get_record,
    mark_used,
    rebind_application_name,
    scan_inventory,
)
from services.feishu_gateway import get_tenant_access_token
from services.host_config import (  # noqa: E402
    ConfigurationError,
    host_settings_snapshot,
)
from services.utm_notion_source import (
    SOURCE_ENV_KEYS,
    configured_feishu_source as configured_utm_notion_source,
    resolve_feishu_source as resolve_utm_notion_source,
)
from scripts.utm_env_download_assets import _request as _feishu_media_request


DEFAULT_DATABASE = PROJECT_ROOT / "runtime" / "vm-inventory.sqlite3"
UTM_NOTION_FEISHU_ENV_KEYS = SOURCE_ENV_KEYS
API_BASE = "https://open.feishu.cn/open-apis"

ACCOUNT_LABELS = (
    "用户名：",
    "邮箱：",
    "初始密码：",
    "修改后的密码：",
    "电话：",
    "电话短信接收平台：",
    "生日（格式年/月/日）：",
    "team ID:",
    "APP_ID：",
    "Renewal date：",
    "代理ip:",
    "代理端口:",
    "代理用户名：",
    "代理用户密码：",
    "代码链接：",
    "ABA Routing Number：",
    "Account Number：",
)

APPLICATION_LABELS = (
    "应用名: ",
    "团队: ",
    "顶级域名: ",
    "正式包名: ",
    "正式域名: ",
    "隐私协议: ",
    "用户协议: ",
    "支持链接: ",
    "应用类型：",
    "应用描述：",
    "关键词:",
    "Subtitle：",
    "Promotional Text：",
    "Description：",
    "Keywords：",
    "App Review Notes：",
)
APPLICATION_MULTILINE_LABELS = {
    "正式域名: ",
    "应用描述：",
    "Description：",
    "App Review Notes：",
}
REVIEW_COPY_FIELD = "提审文案"
REVIEW_COPY_LABELS = (
    "Subtitle：",
    "Promotional Text：",
    "Description：",
    "Keywords：",
    "App Review Notes：",
)
REVIEW_COPY_TEXTAREA_IDS = (
    ("subtitle", "Subtitle："),
    ("promotional_text", "Promotional Text："),
    ("description", "Description："),
    ("keywords", "Keywords："),
    ("review_notes", "App Review Notes："),
)
_REVIEW_COPY_ID_TO_LABEL = dict(REVIEW_COPY_TEXTAREA_IDS)
_REVIEW_COPY_VALUES_PATTERN = re.compile(r"const\s+values\s*=\s*\{", re.IGNORECASE)
_REVIEW_COPY_JS_STRING = re.compile(
    r"(?P<key>name|subtitle|promotional_text|description|whats_new|"
    r"keywords|copyright|review_notes)\s*:\s*"
    r"(?P<quote>['\"])(?P<value>(?:\\.|(?!(?P=quote)).)*)(?P=quote)",
    re.DOTALL,
)

CATEGORY_MAP = {
    "报刊杂志": "MAGAZINES_AND_NEWSPAPERS",
    "财务": "FINANCE",
    "参考资料": "REFERENCE",
    "导航": "NAVIGATION",
    "工具": "UTILITIES",
    "购物": "SHOPPING",
    "健康健美": "HEALTH_AND_FITNESS",
    "教育": "EDUCATION",
    "旅游": "TRAVEL",
    "美食佳饮": "FOOD_AND_DRINK",
    "软件开发工具": "DEVELOPER_TOOLS",
    "商务": "BUSINESS",
    "社交": "SOCIAL_NETWORKING",
    "摄影与录像": "PHOTO_AND_VIDEO",
    "生活": "LIFESTYLE",
    "体育": "SPORTS",
    "天气": "WEATHER",
    "贴纸": "STICKERS",
    "图书": "BOOKS",
    "图形与设计": "GRAPHICS_AND_DESIGN",
    "效率": "PRODUCTIVITY",
    "新闻": "NEWS",
    "医疗": "MEDICAL",
    "音乐": "MUSIC",
    "游戏": "GAMES",
    "娱乐": "ENTERTAINMENT",
}


def resolve_feishu_source(token: str) -> tuple[str, str, str]:
    """Resolve the configured Base source from one immutable project snapshot."""
    settings = host_settings_snapshot(
        env_path=PROJECT_ROOT / ".env",
        file_override_keys=UTM_NOTION_FEISHU_ENV_KEYS,
    )
    configured_source = configured_utm_notion_source(settings)
    return resolve_utm_notion_source(token, configured_source)
VALID_CATEGORIES = frozenset(CATEGORY_MAP.values())
CATEGORY_ALIASES = {
    "生活方式": "LIFESTYLE",
}
EMAIL_SUFFIX_PATTERN = (
    r"(?:co\.uk|com\.cn|com|net|org|edu|gov|io|co|cn|de|uk|jp|fr|me|app|dev)"
)
GENERATED_PASSWORD_LENGTH = 16
TEST_MISSING_VALUE = "test"
SKIP_MISSING_MUTEX_ERROR = (
    "--skip-missing cannot be combined with --fill-missing-with-test"
)
# Feishu fields that raise when empty and may be omitted under --skip-missing.
# 应用名, 正式包名, and 账号信息 stay required: they identify the page and login.
SKIPPABLE_EMPTY_FEISHU_FIELDS = (
    "代理信息",
    "代码 URL",
    "应用类型",
    "顶级域名",
    "待购买域名",
    "正式域名(app/h5/im/log)",
    "隐私协议",
    "用户协议",
    "支持协议",
    "应用描述",
    "关键词",
    REVIEW_COPY_FIELD,
)
REQUIRED_IDENTITY_FEISHU_FIELDS = (
    "应用名",
    "正式包名",
    "账号信息",
)


@dataclass(frozen=True)
class UtmNotionRuntimeConfig:
    feishu_app_id: str
    feishu_app_secret: str
    configured_source: tuple[str, str, str, str]
    notion_token: str
    notion_root_page_id: str
    notion_template_title: str
    host_title: str
    images_dir: Path
    images_dirs: tuple[Path, ...] = ()


def _required_runtime_setting(settings: Mapping[str, str], key: str) -> str:
    value = str(settings.get(key, "")).strip()
    if not value:
        raise ConfigurationError(f"missing required host setting: {key}")
    return value


def load_runtime_config(
    *,
    environ: Mapping[str, str] | None = None,
    env_path: Path | None = None,
) -> UtmNotionRuntimeConfig:
    if env_path is None:
        settings_path = None if environ is not None else PROJECT_ROOT / ".env"
    else:
        settings_path = Path(env_path)
    settings = host_settings_snapshot(
        environ=environ,
        env_path=settings_path,
        file_override_keys=UTM_NOTION_FEISHU_ENV_KEYS,
    )
    feishu_app_id = _required_runtime_setting(settings, "FEISHU_APP_ID")
    feishu_app_secret = _required_runtime_setting(settings, "FEISHU_APP_SECRET")
    notion_token = _required_runtime_setting(settings, "NOTION_TOKEN")
    notion_root_page_id = _required_runtime_setting(settings, "NOTION_ROOT_PAGE_ID")
    host_title = _required_runtime_setting(settings, "SUBMISSION_HOST_MACHINE")
    images_dirs_value = str(settings.get("SUBMISSION_VM_IMAGES_DIRS", "")).strip()
    if images_dirs_value:
        try:
            candidates = json.loads(images_dirs_value)
            if not isinstance(candidates, list) or not candidates or any(
                not isinstance(value, str) or not value.strip() for value in candidates
            ):
                raise ValueError
            images_dirs = tuple(Path(value).expanduser() for value in candidates)
            if any(not directory.is_absolute() for directory in images_dirs) or len(set(images_dirs)) != len(images_dirs):
                raise ValueError
        except (TypeError, ValueError):
            raise ConfigurationError("invalid host setting: SUBMISSION_VM_IMAGES_DIRS") from None
    else:
        images_dir_value = _required_runtime_setting(settings, "SUBMISSION_VM_IMAGES_DIR")
        images_dirs = (Path(images_dir_value).expanduser(),)
        if not images_dirs[0].is_absolute():
            raise ConfigurationError(
                "invalid host setting: SUBMISSION_VM_IMAGES_DIR must be an absolute path"
            )
    try:
        configured_source = configured_utm_notion_source(settings)
    except RuntimeError as error:
        raise ConfigurationError(str(error)) from error
    return UtmNotionRuntimeConfig(
        feishu_app_id=feishu_app_id,
        feishu_app_secret=feishu_app_secret,
        configured_source=configured_source,
        notion_token=notion_token,
        notion_root_page_id=notion_root_page_id,
        notion_template_title=str(
            settings.get("NOTION_TEMPLATE_TITLE", "模板") or "模板"
        ).strip(),
        host_title=host_title,
        images_dir=images_dirs[0],
        images_dirs=images_dirs,
    )


def notion_api_from_config(config: UtmNotionRuntimeConfig) -> NotionAPI:
    return NotionAPI(
        config.notion_token,
        config.notion_root_page_id,
        config.notion_template_title,
    )


def parse_feishu_wiki_url(value: str) -> tuple[str, str, str]:
    parsed = urllib.parse.urlsplit(str(value).strip())
    hostname = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    table_values = query.get("table", [])
    view_values = query.get("view", [])
    valid_host = hostname == "feishu.cn" or hostname.endswith(".feishu.cn")
    if (
        parsed.scheme != "https"
        or not valid_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or len(path_parts) != 2
        or path_parts[0] != "wiki"
        or not re.fullmatch(r"[A-Za-z0-9]+", path_parts[1])
        or len(table_values) != 1
        or len(view_values) != 1
        or not re.fullmatch(r"tbl[A-Za-z0-9]+", table_values[0])
        or not re.fullmatch(r"vew[A-Za-z0-9]+", view_values[0])
    ):
        raise RuntimeError("Feishu Wiki URL must identify one exact Base table and view")
    return path_parts[1], table_values[0], view_values[0]


def resolve_bitable_app_token(token: str, wiki_node_token: str) -> str:
    url = API_BASE + "/wiki/v2/spaces/get_node?" + urllib.parse.urlencode(
        {"token": wiki_node_token}
    )
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        try:
            result = json.load(error)
        except Exception:
            result = {}
        raise RuntimeError(
            f"Feishu Wiki API HTTP {error.code}: code={result.get('code', 'unknown')} "
            f"msg={result.get('msg', 'request failed')}"
        ) from None
    if result.get("code") != 0:
        raise RuntimeError(
            f"Feishu Wiki API failed: code={result.get('code')} msg={result.get('msg')}"
        )
    node = dict((result.get("data") or {}).get("node") or {})
    app_token = str(node.get("obj_token") or "").strip()
    if node.get("obj_type") != "bitable" or not re.fullmatch(
        r"[A-Za-z0-9]+", app_token
    ):
        raise RuntimeError("Feishu Wiki node does not resolve to one Base")
    return app_token


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return text.strip()
        return ""
    if isinstance(value, list):
        return "".join(_cell_text(item) for item in value).strip()
    return ""


class _ReviewCopyTextareaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: dict[str, str] = {}
        self._current_id: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "textarea":
            return
        textarea_id = dict(attrs).get("id")
        if textarea_id in _REVIEW_COPY_ID_TO_LABEL:
            self._current_id = textarea_id
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._current_id is not None:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "textarea" and self._current_id is not None:
            self.values[self._current_id] = "".join(self._chunks)
            self._current_id = None
            self._chunks = []


def _normalize_review_copy_value(label: str, value: str) -> str:
    normalized = html.unescape(value).replace("\r\n", "\n").replace("\r", "\n")
    if label in APPLICATION_MULTILINE_LABELS:
        lines = [line.rstrip() for line in normalized.split("\n")]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines)
    return " ".join(normalized.split())


def _slice_balanced_braces(text: str, start: int) -> str:
    if start >= len(text) or text[start] != "{":
        return ""
    depth = 0
    in_quote = ""
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_quote:
                in_quote = ""
            continue
        if char in {'"', "'"}:
            in_quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def _js_string_value(quote: str, raw: str) -> str:
    try:
        decoded = ast.literal_eval(quote + raw + quote)
    except (SyntaxError, ValueError):
        decoded = raw.replace("\\n", "\n").replace("\\'", "'").replace('\\"', '"')
    if not isinstance(decoded, str):
        decoded = raw
    return html.unescape(decoded)


def _review_copy_values_json(html_text: str) -> dict[str, str]:
    match = _REVIEW_COPY_VALUES_PATTERN.search(html_text)
    if not match:
        return {}
    blob = _slice_balanced_braces(html_text, match.end() - 1)
    if not blob:
        return {}
    parsed: dict[str, str] = {}
    for item in _REVIEW_COPY_JS_STRING.finditer(blob):
        parsed[item.group("key")] = _js_string_value(
            item.group("quote"), item.group("value")
        )
    return parsed


def parse_review_copy_html(html_text: str) -> dict[str, str]:
    """Parse review-copy fields from an App Store Connect 复制区 HTML attachment.

    Prefer textarea elements by stable id. If a mapped id is missing or empty,
    fall back to the same key in ``const values={...}``. Never read the later
    「不复制、只检查」 section or heading label text.
    """
    parser = _ReviewCopyTextareaParser()
    parser.feed(html_text)
    parser.close()
    fallback = _review_copy_values_json(html_text)
    parsed: dict[str, str] = {}
    for textarea_id, label in REVIEW_COPY_TEXTAREA_IDS:
        raw = parser.values.get(textarea_id, "")
        if not raw.strip():
            raw = fallback.get(textarea_id, "")
        value = _normalize_review_copy_value(label, raw)
        if value:
            parsed[label] = value
    return parsed


def review_copy_file_token(cell: object) -> str:
    if not isinstance(cell, list):
        return ""
    tokens = [
        str(item.get("file_token") or "").strip()
        for item in cell
        if isinstance(item, dict) and str(item.get("file_token") or "").strip()
    ]
    if len(tokens) > 1:
        raise RuntimeError("Feishu 提审文案 must contain exactly one attachment")
    return tokens[0] if tokens else ""


def review_copy_media_url(file_token: str, table_id: str) -> str:
    token = str(file_token or "").strip()
    table = str(table_id or "").strip()
    if not token:
        raise RuntimeError("Feishu 提审文案 download is not configured")
    if not table:
        raise RuntimeError("Feishu 提审文案 download requires table_id")
    quoted = urllib.parse.quote(token, safe="")
    extra = json.dumps(
        {"bitablePerm": {"tableId": table}},
        separators=(",", ":"),
        ensure_ascii=True,
    )
    query = urllib.parse.urlencode({"extra": extra})
    return f"{API_BASE}/drive/v1/medias/{quoted}/download?{query}"


def download_review_copy_html(
    file_token: str, *, token: str, table_id: str
) -> str:
    if not file_token or not token:
        raise RuntimeError("Feishu 提审文案 download is not configured")
    url = review_copy_media_url(file_token, table_id)
    body = _feishu_media_request(
        url,
        token=token,
        label="提审文案 attachment download",
    )
    return body.decode("utf-8")


def load_review_copy_fields(
    cell: object,
    *,
    download_review_copy: Callable[[str], str],
    fill_missing_with_test: bool = False,
    skip_missing: bool = False,
    skipped: list[str] | None = None,
) -> dict[str, str]:
    if fill_missing_with_test and skip_missing:
        raise RuntimeError(SKIP_MISSING_MUTEX_ERROR)
    file_token = review_copy_file_token(cell)
    if not file_token:
        if fill_missing_with_test:
            return {label: TEST_MISSING_VALUE for label in REVIEW_COPY_LABELS}
        if skip_missing:
            if skipped is not None:
                skipped.append(REVIEW_COPY_FIELD)
            return {}
        raise RuntimeError(f"Feishu field is empty: {REVIEW_COPY_FIELD}")
    parsed = parse_review_copy_html(download_review_copy(file_token))
    loaded: dict[str, str] = {}
    for textarea_id, label in REVIEW_COPY_TEXTAREA_IDS:
        value = parsed.get(label, "")
        if value:
            loaded[label] = value
        elif fill_missing_with_test:
            loaded[label] = TEST_MISSING_VALUE
        elif skip_missing:
            if skipped is not None:
                skipped.append(f"{REVIEW_COPY_FIELD}.{textarea_id}")
        else:
            raise RuntimeError(f"Feishu field is empty: {REVIEW_COPY_FIELD}.{textarea_id}")
    return loaded


def _required_text(
    fields: dict[str, object],
    name: str,
    *,
    fill_missing_with_test: bool = False,
    skip_missing: bool = False,
    skipped: list[str] | None = None,
) -> str:
    value = _cell_text(fields.get(name))
    if not value:
        if fill_missing_with_test:
            return TEST_MISSING_VALUE
        if skip_missing:
            if skipped is not None:
                skipped.append(name)
            return ""
        raise RuntimeError(f"Feishu field is empty: {name}")
    return value


def _http_url(
    fields: dict[str, object],
    name: str,
    *,
    required: bool = True,
    fill_missing_with_test: bool = False,
    skip_missing: bool = False,
    skipped: list[str] | None = None,
) -> str | None:
    cell = fields.get(name)
    value = ""
    if isinstance(cell, dict) and isinstance(cell.get("link"), str):
        value = str(cell["link"]).strip()
    if not value:
        value = _cell_text(cell)
    if not value and fill_missing_with_test:
        return TEST_MISSING_VALUE
    if not value and skip_missing:
        if skipped is not None:
            skipped.append(name)
        return None
    if not value and not required:
        return ""
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(f"Feishu field is not a complete HTTP(S) URL: {name}")
    return value


def _normalize_us_phone(value: str) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    if 11 <= len(digits) <= 15:
        return "+" + digits
    raise RuntimeError("Feishu 账号信息 phone must contain 10 US digits")


GENERIC_EMAIL_PATTERN = re.compile(
    r"(?<![A-Z0-9._%+-])"
    r"[A-Z0-9._%+-]+@"
    r"[A-Z0-9](?:[A-Z0-9.-]*[A-Z0-9])?\.[A-Z]{2,63}"
    r"(?![A-Z0-9.-])",
    flags=re.IGNORECASE,
)
INLINE_HTTP_URL_PATTERN = re.compile(
    r"https?://[^\s，；。]+",
    flags=re.IGNORECASE,
)
PHONE_CANDIDATE_PATTERN = re.compile(r"(?<!\d)\+?\d{10,15}(?!\d)")
PASSWORD_LABEL_PATTERN = re.compile(
    r"(?:初始密码|密码|password)\s*[:：=]\s*([^\s,，;；|]+)",
    flags=re.IGNORECASE,
)
ACCOUNT_METADATA_PATTERN = re.compile(
    r"(?:初始密码|密码|账号|邮箱|电话|手机|接码|短信|链接|国家|"
    r"password|account|email|phone|sms|url|country)",
    flags=re.IGNORECASE,
)


def _has_mixed_password_characters(value: str) -> bool:
    return bool(re.search(r"[A-Za-z]", value) and re.search(r"\d", value))


def _generic_account_identity(identity_text: str, sms_url: str) -> dict[str, str] | None:
    email_matches = list(GENERIC_EMAIL_PATTERN.finditer(identity_text))
    if not email_matches:
        return None
    emails: dict[str, list[re.Match[str]]] = {}
    for match in email_matches:
        emails.setdefault(match.group(0).casefold(), []).append(match)
    if len(emails) != 1:
        raise RuntimeError("Feishu 账号信息 email could not be uniquely parsed")
    selected_email_matches = next(iter(emails.values()))
    email = selected_email_matches[0].group(0)
    email_spans = [match.span() for match in selected_email_matches]

    phone_matches = [
        match
        for match in PHONE_CANDIDATE_PATTERN.finditer(identity_text)
        if not any(
            match.start() < email_end and email_start < match.end()
            for email_start, email_end in email_spans
        )
    ]
    if not phone_matches:
        return None
    phones: dict[str, list[re.Match[str]]] = {}
    for match in phone_matches:
        phones.setdefault(_normalize_us_phone(match.group(0)), []).append(match)
    if len(phones) != 1:
        raise RuntimeError("Feishu 账号信息 must contain exactly one phone")
    phone, selected_phone_matches = next(iter(phones.items()))

    labelled_passwords = [
        match.group(1)
        for match in PASSWORD_LABEL_PATTERN.finditer(identity_text)
        if _has_mixed_password_characters(match.group(1))
    ]
    labelled_passwords = list(dict.fromkeys(labelled_passwords))
    if len(labelled_passwords) > 1:
        raise RuntimeError(
            "Feishu 账号信息 initial password could not be uniquely parsed"
        )
    if labelled_passwords:
        initial_password = labelled_passwords[0]
    else:
        masked = list(identity_text)
        for start, end in [
            *email_spans,
            *(match.span() for match in selected_phone_matches),
        ]:
            masked[start:end] = " " * (end - start)
        residual = "".join(masked)
        password_candidates = [
            token
            for token in re.split(r"[\s,，;；|:：=()\[\]{}<>]+", residual)
            if token
            and ACCOUNT_METADATA_PATTERN.fullmatch(token) is None
            and _has_mixed_password_characters(token)
        ]
        passwords = list(dict.fromkeys(password_candidates))
        if len(passwords) > 1:
            raise RuntimeError(
                "Feishu 账号信息 initial password could not be uniquely parsed"
            )
        if not passwords:
            return None
        initial_password = passwords[0]

    return {
        "email": email,
        "initial_password": initial_password,
        "phone": phone,
        "sms_url": sms_url,
}


def _is_lixsms_https_url(value: object) -> bool:
    try:
        parsed = urllib.parse.urlsplit(str(value or "").strip())
        return parsed.scheme.lower() == "https" and parsed.hostname == "lixsms.com"
    except ValueError:
        return False


def _parse_lixsms_account_info(cell: object) -> dict[str, str] | None:
    phone = ""
    sms_url = ""
    credential_parts: list[str] = []

    if isinstance(cell, list):
        linked_indexes = []
        for index, item in enumerate(cell):
            if not isinstance(item, dict):
                continue
            link = str(item.get("link") or "").strip()
            if link:
                linked_indexes.append(index)
        if not linked_indexes:
            return None
        provider_index = linked_indexes[0]
        provider_item = cell[provider_index]
        if not isinstance(provider_item, dict) or not _is_lixsms_https_url(
            provider_item.get("link")
        ):
            return None
        if provider_index != 1 or len(cell) < 3:
            raise RuntimeError("Feishu Lixsms 账号信息 fragment order is invalid")
        phone_item = cell[0]
        credential_items = cell[2:]
        if (
            not isinstance(phone_item, dict)
            or str(phone_item.get("link") or "").strip()
            or not isinstance(provider_item, dict)
            or any(
                not isinstance(item, dict)
                or not str(item.get("link") or "").strip()
                or not isinstance(item.get("text"), str)
                for item in credential_items
            )
        ):
            raise RuntimeError("Feishu Lixsms 账号信息 fragment boundaries are invalid")
        phone = html.unescape(str(phone_item.get("text") or "")).strip()
        sms_url = str(provider_item.get("link") or "").strip()
        credential_parts = [
            html.unescape(str(item.get("text") or "")).strip()
            for item in credential_items
        ]
    elif isinstance(cell, str):
        lines = [html.unescape(line).strip() for line in cell.splitlines() if line.strip()]
        provider_indexes = []
        for index, line in enumerate(lines):
            if _is_lixsms_https_url(line):
                provider_indexes.append(index)
        if not provider_indexes:
            return None
        if len(provider_indexes) != 1 or provider_indexes[0] != 1 or len(lines) < 3:
            raise RuntimeError("Feishu Lixsms 账号信息 line order is invalid")
        phone = lines[0]
        sms_url = lines[1]
        credential_parts = lines[2:]
    else:
        return None

    try:
        parsed_sms_url = urllib.parse.urlsplit(sms_url)
        exact_provider = (
            parsed_sms_url.scheme.lower() == "https"
            and parsed_sms_url.hostname == "lixsms.com"
            and parsed_sms_url.username is None
            and parsed_sms_url.password is None
            and parsed_sms_url.port is None
        )
    except ValueError:
        exact_provider = False
    if not exact_provider:
        raise RuntimeError("Feishu Lixsms 账号信息 SMS URL is invalid")
    if re.fullmatch(r"\d{10}", phone) is None:
        raise RuntimeError("Feishu Lixsms 账号信息 phone must contain 10 digits")
    if not credential_parts or any(not part for part in credential_parts):
        raise RuntimeError("Feishu Lixsms 账号信息 credentials are incomplete")

    credential_tail = "".join(credential_parts)
    suffix_matches = list(
        re.finditer(rf"\.{EMAIL_SUFFIX_PATTERN}", credential_tail, flags=re.IGNORECASE)
    )
    if credential_tail.count("@") != 1 or len(suffix_matches) != 1:
        raise RuntimeError("Feishu Lixsms 账号信息 email boundary is ambiguous")
    email_end = suffix_matches[0].end()
    email = credential_tail[:email_end]
    initial_password = credential_tail[email_end:]
    if GENERIC_EMAIL_PATTERN.fullmatch(email) is None:
        raise RuntimeError("Feishu Lixsms 账号信息 email is invalid")
    if not initial_password or not _has_mixed_password_characters(initial_password):
        raise RuntimeError("Feishu Lixsms 账号信息 initial password is invalid")

    return {
        "email": email,
        "initial_password": initial_password,
        "phone": _normalize_us_phone(phone),
        "sms_url": sms_url,
    }


def parse_account_info(cell: object) -> dict[str, str]:
    lixsms_account = _parse_lixsms_account_info(cell)
    if lixsms_account is not None:
        return lixsms_account

    text = _cell_text(cell)
    cell_link = str(cell.get("link") or "").strip() if isinstance(cell, dict) else ""

    country_first_multiline_account = re.fullmatch(
        rf"[^\r\n]+\s*\r?\n"
        rf"(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+?\.{EMAIL_SUFFIX_PATTERN})\s*\r?\n"
        rf"(?P<password>[A-Za-z0-9!#$%&*._-]+)\s*\r?\n"
        rf"(?P<phone>\+?\d{{10,15}})\s*\r?\n"
        rf"(?P<sms_url>https?://\S+)",
        text,
        flags=re.IGNORECASE,
    )
    if country_first_multiline_account and text.count("@") == 1:
        initial_password = country_first_multiline_account.group("password")
        if not re.search(r"[A-Za-z]", initial_password) or not re.search(
            r"\d", initial_password
        ):
            raise RuntimeError(
                "Feishu 账号信息 initial password must contain letters and digits"
            )
        return {
            "email": country_first_multiline_account.group("email"),
            "initial_password": initial_password,
            "phone": _normalize_us_phone(country_first_multiline_account.group("phone")),
            "sms_url": country_first_multiline_account.group("sms_url"),
        }

    compact_prefix = (
        rf"(?P<phone>\+\d{{10,11}})-{{4}}"
        rf"(?P<sms_url>https?://[A-Z0-9.-]+/smsrecord\?token=[A-Za-z0-9]{{34}})"
        rf"(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+?\.{EMAIL_SUFFIX_PATTERN})"
    )
    compact_account = re.fullmatch(
        compact_prefix
        + rf"(?P<password>[A-Za-z]+\d+[!#$%&*._-]?)"
        + rf"(?P<country>[A-Za-z][A-Za-z-]*)\s+.+",
        text,
        flags=re.IGNORECASE,
    ) or re.fullmatch(
        compact_prefix + rf"(?P<password>[^\s+]+)\s+.+",
        text,
        flags=re.IGNORECASE,
    )
    if compact_account and text.count("@") == 1:
        initial_password = compact_account.group("password")
        if not re.search(r"[A-Za-z]", initial_password) or not re.search(
            r"\d", initial_password
        ):
            raise RuntimeError(
                "Feishu 账号信息 initial password must contain letters and digits"
            )
        return {
            "email": compact_account.group("email"),
            "initial_password": initial_password,
            "phone": _normalize_us_phone(compact_account.group("phone")),
            "sms_url": compact_account.group("sms_url"),
        }

    spaced_phone_first = re.fullmatch(
        rf"(?P<phone>\+?\d{{10,15}})\s+"
        rf"(?P<sms_url>https?://\S+)\s+"
        rf"(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+?\.{EMAIL_SUFFIX_PATTERN})\s+"
        rf"(?P<password>[A-Za-z0-9]+)\s+"
        rf"(?P<country>.+)",
        text,
        flags=re.IGNORECASE,
    )
    if spaced_phone_first and text.count("@") == 1:
        initial_password = spaced_phone_first.group("password")
        if not re.search(r"[A-Za-z]", initial_password) or not re.search(
            r"\d", initial_password
        ):
            raise RuntimeError(
                "Feishu 账号信息 initial password must contain letters and digits"
            )
        return {
            "email": spaced_phone_first.group("email"),
            "initial_password": initial_password,
            "phone": _normalize_us_phone(spaced_phone_first.group("phone")),
            "sms_url": spaced_phone_first.group("sms_url"),
        }

    url_matches = list(INLINE_HTTP_URL_PATTERN.finditer(text))
    if len(url_matches) > 1:
        raise RuntimeError("Feishu 账号信息 must contain at most one HTTP(S) URL")
    if url_matches:
        url_match = url_matches[0]
        sms_url = url_match.group(0)
        identity_text = (
            text[: url_match.start()].rstrip() + text[url_match.end() :].lstrip()
        ).strip()
    else:
        sms_url = cell_link
        identity_text = text
    parsed_sms_url = urllib.parse.urlsplit(sms_url)
    if parsed_sms_url.scheme not in {"http", "https"} or not parsed_sms_url.netloc:
        raise RuntimeError("Feishu 账号信息 must contain an inline or cell-link HTTP(S) URL")
    space_separated = re.fullmatch(
        r"(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63})\s+"
        r"(?P<password>\S+)\s+"
        r"(?P<phone>\+?\d{10,15})",
        identity_text,
        flags=re.IGNORECASE,
    )
    if space_separated and identity_text.count("@") == 1:
        return {
            "email": space_separated.group("email"),
            "initial_password": space_separated.group("password"),
            "phone": _normalize_us_phone(space_separated.group("phone")),
            "sms_url": sms_url,
        }
    labelled_pattern = re.compile(
        rf".*?账号\s*[：:]\s*"
        rf"(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+?\.{EMAIL_SUFFIX_PATTERN})\s*"
        rf"密码\s*[：:]\s*(?P<password>[A-Za-z0-9]+)\s*"
        rf"接码\s*[：:]\s*(?P<phone>\+?\d{{7,15}})",
        flags=re.IGNORECASE,
    )
    labelled_matches = list(labelled_pattern.finditer(identity_text))
    if len(labelled_matches) == 1:
        labelled = labelled_matches[0]
        if labelled.end() != len(identity_text):
            raise RuntimeError("Feishu 账号信息 labelled fields must consume the full identity")
        initial_password = labelled.group("password")
        if not re.search(r"[A-Za-z]", initial_password) or not re.search(r"\d", initial_password):
            raise RuntimeError("Feishu 账号信息 initial password must contain letters and digits")
        return {
            "email": labelled.group("email"),
            "initial_password": initial_password,
            "phone": _normalize_us_phone(labelled.group("phone")),
            "sms_url": sms_url,
        }

    provider_first_match = re.fullmatch(
        rf"(?P<provider>[A-Za-z0-9]+)\s+.+?"
        rf"(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+?\.{EMAIL_SUFFIX_PATTERN})"
        rf"(?P<password>[^\s+]+)"
        rf"(?P<phone>\+\d{{10,11}})-{{4}}",
        identity_text,
        flags=re.IGNORECASE,
    )
    if provider_first_match and identity_text.count("@") == 1:
        initial_password = provider_first_match.group("password")
        if not re.search(r"[A-Za-z]", initial_password) or not re.search(
            r"\d", initial_password
        ):
            raise RuntimeError(
                "Feishu 账号信息 initial password must contain letters and digits"
            )
        return {
            "email": provider_first_match.group("email"),
            "initial_password": initial_password,
            "phone": _normalize_us_phone(provider_first_match.group("phone")),
            "sms_url": sms_url,
        }

    generic_identity = _generic_account_identity(identity_text, sms_url)
    if generic_identity is not None:
        return generic_identity

    plain_email_matches = list(
        re.finditer(
            rf"[A-Z0-9._%+-]+@[A-Z0-9.-]+?\.{EMAIL_SUFFIX_PATTERN}",
            identity_text,
            flags=re.IGNORECASE,
        )
    )
    if len(plain_email_matches) == 1 and identity_text.count("@") == 1:
        plain_email = plain_email_matches[0]
        tail = identity_text[plain_email.end() :]
        candidates: list[tuple[str, str]] = []
        for phone_length in (10, 11):
            if len(tail) <= phone_length:
                continue
            initial_password = tail[:-phone_length]
            phone = tail[-phone_length:]
            if (
                phone.isdigit()
                and (phone_length == 10 or phone.startswith("1"))
                and re.fullmatch(r"[A-Za-z0-9]+", initial_password)
                and re.search(r"[A-Za-z]", initial_password)
                and re.search(r"\d", initial_password)
            ):
                candidates.append((initial_password, phone))
        if len(candidates) == 1:
            initial_password, phone = candidates[0]
            return {
                "email": plain_email.group(0),
                "initial_password": initial_password,
                "phone": _normalize_us_phone(phone),
                "sms_url": sms_url,
            }

    email_match = re.match(
        rf"^(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+?\.{EMAIL_SUFFIX_PATTERN})(?P<tail>.+)$",
        identity_text,
        flags=re.IGNORECASE,
    )
    if not email_match:
        raise RuntimeError(
            "Feishu 账号信息 email could not be uniquely parsed "
            f"(markers={identity_text.count('@')} candidates=0)"
        )
    email = email_match.group("email")
    tail = email_match.group("tail")
    phone_matches = list(
        re.finditer(r"(?<!\d)(?P<phone>\+?\d{7,15})(?!\d)", tail)
    )
    if len(phone_matches) != 1:
        raise RuntimeError("Feishu 账号信息 must contain exactly one phone")
    phone_match = phone_matches[0]
    tail_without_phone = (
        tail[: phone_match.start()].rstrip() + tail[phone_match.end() :].lstrip()
    ).strip()
    password_match = re.match(
        r"(?P<password>[A-Za-z0-9]+)(?P<country>[^A-Za-z0-9].*)$",
        tail_without_phone,
    )
    if not password_match:
        raise RuntimeError("Feishu 账号信息 initial password could not be uniquely parsed")
    initial_password = password_match.group("password")
    if not re.search(r"[A-Za-z]", initial_password) or not re.search(r"\d", initial_password):
        raise RuntimeError("Feishu 账号信息 initial password must contain letters and digits")

    return {
        "email": email,
        "initial_password": initial_password,
        "phone": _normalize_us_phone(phone_match.group("phone")),
        "sms_url": sms_url,
    }


def password_meets_requirements(password: str) -> bool:
    value = str(password)
    return (
        len(value) >= 8
        and value.isascii()
        and value.isalnum()
        and any(character.islower() for character in value)
        and any(character.isupper() for character in value)
        and any(character.isdigit() for character in value)
    )


def generate_random_password() -> str:
    characters = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
    ]
    alphabet = string.ascii_letters + string.digits
    characters.extend(
        secrets.choice(alphabet)
        for _ in range(GENERATED_PASSWORD_LENGTH - len(characters))
    )
    for index in range(len(characters) - 1, 0, -1):
        swap_index = secrets.randbelow(index + 1)
        characters[index], characters[swap_index] = characters[swap_index], characters[index]
    password = "".join(characters)
    if not password_meets_requirements(password):
        raise RuntimeError("Generated password did not meet the required policy")
    return password


def _template_field_value(template: str, label: str) -> str:
    matches = [line[len(label) :] for line in template.splitlines() if line.startswith(label)]
    if len(matches) != 1:
        raise RuntimeError(f"Notion template label count must be one: {label}")
    return matches[0].strip()


def ensure_modified_password(template: str, replacements: dict[str, str]) -> bool:
    label = "修改后的密码："
    if _template_field_value(template, label):
        return False
    replacements[label] = generate_random_password()
    return True


def _proxy_parts(fields: dict[str, object]) -> tuple[str, str, str, str]:
    source = _required_text(fields, "代理信息")
    parts = source.split(":", 3)
    if len(parts) != 4 or any(not part.strip() for part in parts):
        raise RuntimeError("Feishu 代理信息 must contain IP, port, username and password")
    host, port, username, password = (part.strip() for part in parts)
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise RuntimeError("Feishu proxy port is invalid")
    return host, port, username, password


def normalize_category(source: str) -> str:
    value = str(source).strip().replace("和", "与")
    if value in VALID_CATEGORIES:
        return value
    if value in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[value]
    if value in CATEGORY_MAP:
        return CATEGORY_MAP[value]
    prefix, separator, suffix = value.rpartition("-")
    prefix = prefix.strip() if separator else ""
    suffix = suffix.strip() if separator else ""
    if suffix in VALID_CATEGORIES:
        return suffix
    if prefix in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[prefix]
    if prefix in CATEGORY_MAP:
        return CATEGORY_MAP[prefix]
    if prefix in VALID_CATEGORIES:
        return prefix
    raise RuntimeError("Feishu application category is unsupported")


def build_registration_fields(
    fields: dict[str, object],
    *,
    fill_missing_with_test: bool = False,
    skip_missing: bool = False,
    skipped_fields: list[str] | None = None,
    download_review_copy: Callable[[str], str] | None = None,
    feishu_token: str = "",
    feishu_table_id: str = "",
) -> tuple[dict[str, str], dict[str, str]]:
    if fill_missing_with_test and skip_missing:
        raise RuntimeError(SKIP_MISSING_MUTEX_ERROR)
    skipped = skipped_fields if skipped_fields is not None else []
    app_name = _required_text(fields, "应用名")
    if fill_missing_with_test and not _cell_text(fields.get("账号信息")):
        account_info = {
            "email": TEST_MISSING_VALUE,
            "initial_password": TEST_MISSING_VALUE,
            "phone": TEST_MISSING_VALUE,
            "sms_url": TEST_MISSING_VALUE,
        }
    else:
        account_info = parse_account_info(fields.get("账号信息"))
    proxy_ip: str | None
    proxy_port: str | None
    proxy_username: str | None
    proxy_password: str | None
    if fill_missing_with_test and not _cell_text(fields.get("代理信息")):
        proxy_ip = proxy_port = proxy_username = proxy_password = TEST_MISSING_VALUE
    elif skip_missing and not _cell_text(fields.get("代理信息")):
        skipped.append("代理信息")
        proxy_ip = proxy_port = proxy_username = proxy_password = None
    else:
        proxy_ip, proxy_port, proxy_username, proxy_password = _proxy_parts(fields)
    code_url = _http_url(
        fields,
        "代码 URL",
        fill_missing_with_test=fill_missing_with_test,
        skip_missing=skip_missing,
        skipped=skipped,
    )

    def text(name: str) -> str:
        return _required_text(
            fields,
            name,
            fill_missing_with_test=fill_missing_with_test,
            skip_missing=skip_missing,
            skipped=skipped,
        )

    category_source = text("应用类型")
    if category_source:
        category = (
            TEST_MISSING_VALUE
            if category_source == TEST_MISSING_VALUE and fill_missing_with_test
            else normalize_category(category_source)
        )
    else:
        category = ""

    top_level_domain = _cell_text(fields.get("顶级域名"))
    if not top_level_domain:
        if (
            skip_missing
            and not fill_missing_with_test
            and not _cell_text(fields.get("待购买域名"))
        ):
            skipped.append("顶级域名")
            skipped.append("待购买域名")
        else:
            top_level_domain = _required_text(
                fields,
                "待购买域名",
                fill_missing_with_test=fill_missing_with_test,
            )
    formal_domains = _cell_text(fields.get("正式域名(app/h5/im/log)"))
    if not formal_domains:
        if fill_missing_with_test or top_level_domain == TEST_MISSING_VALUE:
            formal_domains = TEST_MISSING_VALUE
        elif top_level_domain:
            formal_domains = "\n".join(
                f"{prefix}.{top_level_domain}"
                for prefix in ("app", "h5", "im", "log")
            )
        elif skip_missing:
            skipped.append("正式域名(app/h5/im/log)")

    account = {
        "邮箱：": account_info["email"],
        "初始密码：": account_info["initial_password"],
        "电话：": account_info["phone"],
        "电话短信接收平台：": account_info["sms_url"],
    }
    if proxy_ip is not None:
        account["代理ip:"] = proxy_ip
        account["代理端口:"] = proxy_port
        account["代理用户名："] = proxy_username
        account["代理用户密码："] = proxy_password
    if code_url is not None:
        account["代码链接："] = code_url
    routing_number = _cell_text(fields.get("ABA Routing Number"))
    account_number = _cell_text(fields.get("Account Number"))
    if routing_number:
        account["ABA Routing Number："] = routing_number
    if account_number:
        account["Account Number："] = account_number
    application: dict[str, str] = {
        "应用名: ": app_name,
        "团队: ": "灵光",
        "正式包名: ": _required_text(
            fields,
            "正式包名",
            fill_missing_with_test=fill_missing_with_test,
        ),
    }
    if top_level_domain:
        application["顶级域名: "] = top_level_domain
    if formal_domains:
        application["正式域名: "] = formal_domains
    privacy = _http_url(
        fields,
        "隐私协议",
        fill_missing_with_test=fill_missing_with_test,
        skip_missing=skip_missing,
        skipped=skipped,
    )
    if privacy is not None:
        application["隐私协议: "] = privacy
    terms = _http_url(
        fields,
        "用户协议",
        fill_missing_with_test=fill_missing_with_test,
        skip_missing=skip_missing,
        skipped=skipped,
    )
    if terms is not None:
        application["用户协议: "] = terms
    support = _http_url(
        fields,
        "支持协议",
        fill_missing_with_test=fill_missing_with_test,
        skip_missing=skip_missing,
        skipped=skipped,
    )
    if support is not None:
        application["支持链接: "] = support
    if category:
        application["应用类型："] = category
    description = text("应用描述")
    if description:
        application["应用描述："] = description
    keywords = text("关键词")
    if keywords:
        application["关键词:"] = keywords

    def _download(file_token: str) -> str:
        if download_review_copy is not None:
            return download_review_copy(file_token)
        return download_review_copy_html(
            file_token,
            token=feishu_token,
            table_id=feishu_table_id,
        )

    application.update(
        load_review_copy_fields(
            fields.get(REVIEW_COPY_FIELD),
            download_review_copy=_download,
            fill_missing_with_test=fill_missing_with_test,
            skip_missing=skip_missing,
            skipped=skipped,
        )
    )
    return account, application


def verify_registration_readback(
    account_after: str,
    account_desired: str,
    application_after: str,
    application_desired: str,
) -> None:
    if account_after != account_desired or application_after != application_desired:
        raise RuntimeError("Notion independent registration readback mismatch")


def fill_template_fields(
    template: str,
    labels: Iterable[str],
    replacements: dict[str, str],
    *,
    multiline_labels: set[str] | None = None,
) -> str:
    ordered_labels = tuple(labels)
    multiline = multiline_labels or set()
    lines = template.split("\n")
    indexes: dict[str, int] = {}
    for label in ordered_labels:
        matches = [index for index, line in enumerate(lines) if line.startswith(label)]
        if len(matches) != 1:
            raise RuntimeError(f"Notion template label count must be one: {label}")
        indexes[label] = matches[0]
    positions = [indexes[label] for label in ordered_labels]
    if positions != sorted(positions):
        raise RuntimeError("Notion template labels are out of order")
    unknown = set(replacements) - set(ordered_labels)
    if unknown:
        raise RuntimeError("Notion replacements contain unknown labels")

    for label in reversed(ordered_labels):
        if label not in replacements:
            continue
        value = str(replacements[label])
        if "\r" in value:
            raise RuntimeError("Notion field values must not contain carriage returns")
        start = indexes[label]
        if label in multiline:
            position = ordered_labels.index(label)
            end = indexes[ordered_labels[position + 1]] if position + 1 < len(ordered_labels) else len(lines)
            lines[start:end] = [label + part for part in value.split("\n", 1)] if "\n" not in value else [label + value.split("\n", 1)[0], *value.split("\n")[1:]]
        else:
            if "\n" in value:
                raise RuntimeError(f"Notion field must remain one line: {label}")
            lines[start] = label + value
    return "\n".join(lines)


def read_template_fields(
    template: str,
    labels: Iterable[str],
    *,
    multiline_labels: set[str] | None = None,
) -> dict[str, str]:
    """Read filled Notion section values with the same single-row ranges as fill."""
    ordered_labels = tuple(labels)
    multiline = multiline_labels or set()
    lines = template.split("\n")
    indexes: dict[str, int] = {}
    for label in ordered_labels:
        matches = [index for index, line in enumerate(lines) if line.startswith(label)]
        if len(matches) != 1:
            raise RuntimeError(f"Notion template label count must be one: {label}")
        indexes[label] = matches[0]
    positions = [indexes[label] for label in ordered_labels]
    if positions != sorted(positions):
        raise RuntimeError("Notion template labels are out of order")

    values: dict[str, str] = {}
    for position, label in enumerate(ordered_labels):
        start = indexes[label]
        if label in multiline:
            end = (
                indexes[ordered_labels[position + 1]]
                if position + 1 < len(ordered_labels)
                else len(lines)
            )
            first = lines[start][len(label) :]
            rest = lines[start + 1 : end]
            values[label] = "\n".join([first, *rest]) if rest else first
        else:
            values[label] = lines[start][len(label) :]
    return values


def _stable_field_value(value: object) -> object:
    if isinstance(value, list):
        return [_stable_field_value(item) for item in value]
    if isinstance(value, dict):
        volatile = {"url", "tmp_url"} if "file_token" in value else set()
        return {
            key: _stable_field_value(item)
            for key, item in value.items()
            if key not in volatile
        }
    return value


def _fields_digest(fields: dict[str, object], *, omit: set[str] | None = None) -> str:
    filtered = {
        key: _stable_field_value(value)
        for key, value in fields.items()
        if key not in (omit or set())
    }
    payload = json.dumps(filtered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class FeishuBitableClient:
    def __init__(self, token: str, app_token: str, table_id: str, view_id: str) -> None:
        if not all((token, app_token, table_id, view_id)):
            raise RuntimeError("Feishu Base client configuration is incomplete")
        self.token = token
        self.app_token = app_token
        self.table_id = table_id
        self.view_id = view_id

    @property
    def _records_path(self) -> str:
        return f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, object] | None = None,
        payload: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        url = API_BASE + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            try:
                result = json.load(error)
            except Exception:
                result = {}
            raise RuntimeError(
                f"Feishu API HTTP {error.code}: code={result.get('code', 'unknown')} "
                f"msg={result.get('msg', 'request failed')}"
            ) from None
        if result.get("code") != 0:
            raise RuntimeError(
                f"Feishu API failed: code={result.get('code')} msg={result.get('msg')}"
            )
        return dict(result.get("data") or {})

    def list_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_token = ""
        while True:
            query: dict[str, object] = {
                "page_size": 500,
            }
            if page_token:
                query["page_token"] = page_token
            data = self._request("GET", self._records_path, query=query)
            records.extend(data.get("items") or [])
            if not data.get("has_more"):
                return records
            page_token = str(data.get("page_token") or "")
            if not page_token:
                raise RuntimeError("Feishu pagination is missing page_token")

    def find_exact_record(
        self,
        *,
        run_id: str = "",
        app_name: str = "",
    ) -> dict[str, Any]:
        run_id = str(run_id).strip()
        app_name = str(app_name).strip()
        if not run_id and not app_name:
            raise RuntimeError("run_id or app_name is required")

        def exact_matches(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
            matches = []
            for record in records:
                fields = dict(record.get("fields") or {})
                if run_id and _cell_text(fields.get("Run ID")) != run_id:
                    continue
                if app_name and _cell_text(fields.get("应用名")) != app_name:
                    continue
                matches.append(record)
            return matches

        matches = exact_matches(self.list_records())
        if len(matches) != 1:
            raise RuntimeError(f"Feishu exact record match count must be one, got {len(matches)}")
        return matches[0]

    def get_record(self, record_id: str) -> dict[str, Any]:
        data = self._request("GET", f"{self._records_path}/{record_id}")
        record = data.get("record")
        if not isinstance(record, dict):
            raise RuntimeError("Feishu record readback is missing")
        return record

    def preflight_vm_write(self, record: dict[str, Any]) -> None:
        record_id = str(record.get("record_id") or "")
        if not record_id:
            raise RuntimeError("Feishu record_id is missing")
        before = self.get_record(record_id)
        before_fields = dict(before.get("fields") or {})
        current = _cell_text(before_fields.get("虚拟机"))
        if current:
            record["fields"] = before_fields
            return
        before_digest = _fields_digest(before_fields, omit={"虚拟机"})
        try:
            self._request(
                "PUT",
                f"{self._records_path}/{record_id}",
                payload={"fields": {"虚拟机": None}},
            )
        except RuntimeError as error:
            if "code=91403" in str(error):
                raise RuntimeError(
                    "Feishu app identity lacks record-write permission: code=91403"
                ) from None
            raise
        after = self.get_record(record_id)
        after_fields = dict(after.get("fields") or {})
        if _cell_text(after_fields.get("虚拟机")) != "":
            raise RuntimeError("Feishu VM write preflight readback mismatch")
        if _fields_digest(after_fields, omit={"虚拟机"}) != before_digest:
            raise RuntimeError("Feishu VM write preflight changed another field")
        record["fields"] = after_fields

    def ensure_vm(self, record: dict[str, Any], vm_name: str) -> bool:
        if not re.fullmatch(r"[a-z]{4}", vm_name):
            raise RuntimeError("VM name must be four lowercase letters")
        record_id = str(record.get("record_id") or "")
        if not record_id:
            raise RuntimeError("Feishu record_id is missing")
        before = self.get_record(record_id)
        before_fields = dict(before.get("fields") or {})
        current = _cell_text(before_fields.get("虚拟机"))
        if current and current != vm_name:
            raise RuntimeError(f"Feishu VM column already contains a different value: {current}")
        if current == vm_name:
            record["fields"] = before_fields
            return False
        before_digest = _fields_digest(before_fields, omit={"虚拟机"})
        changed = not current
        self._request(
            "PUT",
            f"{self._records_path}/{record_id}",
            payload={"fields": {"虚拟机": vm_name}},
        )
        after = self.get_record(record_id)
        after_fields = dict(after.get("fields") or {})
        if _cell_text(after_fields.get("虚拟机")) != vm_name:
            raise RuntimeError("Feishu VM column readback mismatch")
        if _fields_digest(after_fields, omit={"虚拟机"}) != before_digest:
            raise RuntimeError("Feishu update changed a field outside the VM column")
        record["fields"] = after_fields
        return changed


def _bind_vm(
    fields: dict[str, object],
    app_name: str,
    database: Path,
    images_dir: Path | tuple[Path, ...],
    *,
    expected_vm_name: str = "",
    rename_from: str = "",
) -> str:
    if expected_vm_name and not re.fullmatch(r"[a-z]{4}", expected_vm_name):
        raise InventoryError("expected VM name must be four lowercase letters")
    current = _cell_text(fields.get("虚拟机"))
    if not current:
        scan_inventory(database, images_dir)
        if expected_vm_name:
            return claim_exact_available_vm(database, expected_vm_name, app_name)
        return claim_available_vm(database, app_name)
    if not re.fullmatch(r"[a-z]{4}", current):
        raise RuntimeError("Feishu VM value must be four lowercase letters")
    if expected_vm_name and current != expected_vm_name:
        raise InventoryError(
            f"Feishu VM does not match the inherited clone: {current}"
        )
    record = get_record(database, current)
    if record.get("status") != "complete" or int(record.get("directory_present") or 0) != 1:
        raise InventoryError(f"Feishu VM is not a complete present inventory row: {current}")
    bound = record.get("application_name")
    if bound not in (None, app_name):
        if not rename_from:
            raise InventoryError(f"Feishu VM is already bound to another application: {current}")
        rebind_application_name(database, current, rename_from, app_name)
        bound = app_name
    if bound is None:
        if int(record.get("available") or 0) != 1:
            raise InventoryError(f"unbound Feishu VM is not available: {current}")
        mark_used(database, current, app_name)
    return current


def format_skipped_fields_marker(skipped_fields: Iterable[str]) -> str:
    names = [str(name).strip() for name in skipped_fields if str(name).strip()]
    if not names:
        return "status=verified"
    return "status=verified;skipped_fields=" + ",".join(names)


def execute(
    *,
    run_id: str = "",
    app_name: str = "",
    vm_name: str = "",
    database: Path = DEFAULT_DATABASE,
    fill_missing_with_test: bool = False,
    skip_missing: bool = False,
    rename_from: str = "",
) -> dict[str, object]:
    if fill_missing_with_test and skip_missing:
        raise RuntimeError(SKIP_MISSING_MUTEX_ERROR)
    explicit_vm_name = bool(vm_name)
    runtime_config = load_runtime_config(env_path=PROJECT_ROOT / ".env")
    token = get_tenant_access_token(
        runtime_config.feishu_app_id,
        runtime_config.feishu_app_secret,
    )
    app_token, table_id, view_id = resolve_utm_notion_source(
        token, runtime_config.configured_source
    )
    client = FeishuBitableClient(
        token,
        app_token,
        table_id,
        view_id,
    )
    record = client.find_exact_record(run_id=run_id, app_name=app_name)
    fields = dict(record.get("fields") or {})
    skipped_fields: list[str] = []
    account_replacements, application_replacements = build_registration_fields(
        fields,
        fill_missing_with_test=fill_missing_with_test,
        skip_missing=skip_missing,
        skipped_fields=skipped_fields,
        feishu_token=token,
        feishu_table_id=table_id,
    )
    exact_app_name = application_replacements["应用名: "]
    if not explicit_vm_name:
        client.preflight_vm_write(record)
    notion = notion_api_from_config(runtime_config)
    notion.verify_parent(runtime_config.host_title)
    vm_name = _bind_vm(
        fields,
        exact_app_name,
        database.resolve(),
        runtime_config.images_dirs or (runtime_config.images_dir,),
        expected_vm_name=vm_name,
        rename_from=rename_from,
    )
    feishu_changed = (
        False if explicit_vm_name else client.ensure_vm(record, vm_name)
    )
    page_title = f"{exact_app_name}-{vm_name}"
    page_id, page_created = notion.create_registration_copy(page_title)

    notion.verify_parent(runtime_config.host_title)
    account_before = notion.read_section(page_title, "账号信息")
    application_before = notion.read_section(page_title, "应用信息")
    modified_password_generated = ensure_modified_password(
        account_before, account_replacements
    )
    account_desired = fill_template_fields(
        account_before,
        ACCOUNT_LABELS,
        account_replacements,
    )
    application_desired = fill_template_fields(
        application_before,
        APPLICATION_LABELS,
        application_replacements,
        multiline_labels=APPLICATION_MULTILINE_LABELS,
    )

    notion.verify_parent(runtime_config.host_title)
    changed = notion.write_registration_sections(
        page_title,
        {"账号信息": account_desired, "应用信息": application_desired},
    )
    notion.verify_parent(runtime_config.host_title)
    account_after = notion.read_section(page_title, "账号信息")
    application_after = notion.read_section(page_title, "应用信息")
    verify_registration_readback(
        account_after,
        account_desired,
        application_after,
        application_desired,
    )

    return {
        "action": "utm-notion",
        "record_id": str(record.get("record_id") or ""),
        "page_id": page_id,
        "page_title": page_title,
        "vm_name": vm_name,
        "feishu_vm_changed": feishu_changed,
        "notion_page_created": page_created,
        "account_changed": changed["账号信息"],
        "application_changed": changed["应用信息"],
        "modified_password_generated": modified_password_generated,
        "test_filled_labels": sorted(
            label
            for label, value in {**account_replacements, **application_replacements}.items()
            if fill_missing_with_test and value == TEST_MISSING_VALUE
        ),
        "skipped_fields": list(skipped_fields),
        "account_bytes": len(account_after.encode("utf-8")),
        "account_sha256": hashlib.sha256(account_after.encode("utf-8")).hexdigest(),
        "application_bytes": len(application_after.encode("utf-8")),
        "application_sha256": hashlib.sha256(application_after.encode("utf-8")).hexdigest(),
        "status": "verified",
        "handoff": "utm-clash-ip",
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--run-id", default="")
    target.add_argument("--app-name", default="")
    parser.add_argument("--vm-name", default="")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    missing_mode = parser.add_mutually_exclusive_group()
    missing_mode.add_argument("--fill-missing-with-test", action="store_true")
    missing_mode.add_argument(
        "--skip-missing",
        action="store_true",
        help=(
            "Skip Feishu fields that are empty instead of failing. "
            "Leave the matching Notion template rows blank. "
            "Mutually exclusive with --fill-missing-with-test."
        ),
    )
    parser.add_argument("--rename-from", default="")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.fill_missing_with_test and args.skip_missing:
        parser.error(SKIP_MISSING_MUTEX_ERROR)
    result: dict[str, object] = {}

    def operation() -> int:
        result.update(
            execute(
                run_id=args.run_id,
                app_name=args.app_name,
                vm_name=args.vm_name,
                database=args.database,
                fill_missing_with_test=args.fill_missing_with_test,
                skip_missing=args.skip_missing,
                rename_from=args.rename_from,
            )
        )
        return 0

    return run_clean_cli(
        skill_name="utm-notion",
        success_marker=lambda: format_skipped_fields_marker(
            [str(item) for item in list(result.get("skipped_fields") or [])]
        ),
        operation=operation,
        preserve_error_detail=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
