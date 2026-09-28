from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import scripts.utm_notion as utm_notion
from scripts.vm_inventory import (
    get_record as get_inventory_record,
    mark_used,
    register_clone,
    reserve_vm_name,
    scan_inventory,
    set_available,
)

from scripts.utm_notion import (
    ACCOUNT_LABELS,
    APPLICATION_LABELS,
    APPLICATION_MULTILINE_LABELS,
    REVIEW_COPY_LABELS,
    FeishuBitableClient,
    build_registration_fields,
    fill_template_fields,
    normalize_category,
    parse_review_copy_html,
    read_template_fields,
    review_copy_file_token,
    verify_registration_readback,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TARGET_FEISHU_WIKI_URL = (
    "https://qv0zc1dq6qy.feishu.cn/wiki/C70TwyJevipDZakMTWYcusTwnhh"
    "?table=tbl5OOyYst8BqZ6x&view=vewjQVBVeu"
)
FIXTURE_APP_IDENTIFIER = "app-id"
FIXTURE_APP_CREDENTIAL = "app-secret"
FIXTURE_NOTION_CREDENTIAL = "notion-token"
FIXTURE_NOTION_ROOT = "notion-root"
REVIEW_COPY_FILE_TOKEN = "file-review-copy-synthetic"
REVIEW_COPY_HTML_FULL = (FIXTURES / "review_copy_full.html").read_text(encoding="utf-8")
REVIEW_COPY_HTML_MERGED = (
    FIXTURES / "review_copy_merged_heading.html"
).read_text(encoding="utf-8")
REVIEW_COPY_HTML_BY_TOKEN = {
    REVIEW_COPY_FILE_TOKEN: REVIEW_COPY_HTML_FULL,
    "file-review-copy-merged": REVIEW_COPY_HTML_MERGED,
}
REAL_DOWNLOAD_REVIEW_COPY_HTML = utm_notion.download_review_copy_html

FULL_REVIEW_COPY_PARSED = {
    "Subtitle：": "Daily notes in one glance",
    "Promotional Text：": "Capture, tag, and revisit what matters",
    "Description：": (
        "StringBed keeps short notes and reminders together.\n"
        "\n"
        "Write freely, then find them later. It doesn't keep drafts."
    ),
    "Keywords：": "notes, reminders, tags",
    "App Review Notes：": (
        "This submission uses placeholder review notes\n"
        "for a synthetic fixture only.\n"
        "\n"
        "Please check the demo account."
    ),
}
MERGED_REVIEW_COPY_PARSED = {
    "Subtitle：": "Compact habit tracker",
    "Promotional Text：": "Track a habit without extra noise",
    "Description：": (
        "FixtureApp records one habit a day.\n"
        "\n"
        "Open it, tap once, and close it."
    ),
    "Keywords：": "habit, tracker, daily",
    "App Review Notes：": "Synthetic review notes for the merged-heading fixture.",
}


@pytest.fixture(autouse=True)
def isolate_utm_notion_feishu_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in utm_notion.UTM_NOTION_FEISHU_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def mock_review_copy_download(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        utm_notion,
        "download_review_copy_html",
        lambda file_token, token="": REVIEW_COPY_HTML_BY_TOKEN.get(
            file_token, REVIEW_COPY_HTML_FULL
        ),
    )


def test_account_template_keeps_one_explicit_year_month_day_birthday_label() -> None:
    assert ACCOUNT_LABELS.count("生日（格式年/月/日）：") == 1
    assert "生日：" not in ACCOUNT_LABELS


ACCOUNT_TEMPLATE = """用户名：

邮箱：

初始密码：

修改后的密码：

电话：+1

电话短信接收平台：

生日（格式年/月/日）：

team ID:

APP_ID：

Renewal date：

代理ip:

代理端口:

代理用户名：

代理用户密码：

代码链接：

ABA Routing Number：

Account Number：

"""

APPLICATION_TEMPLATE = """应用名: 
团队: 灵光
顶级域名: 
正式包名: 
正式域名: 
隐私协议: 
用户协议: 
支持链接: 
应用类型：
应用描述：
关键词:
Subtitle：
Promotional Text：
Description：
Keywords：
App Review Notes："""


def review_copy_attachment(
    file_token: str = REVIEW_COPY_FILE_TOKEN,
    name: str = "StringBed-review-copy-synthetic.html",
) -> list[dict[str, object]]:
    return [
        {
            "file_token": file_token,
            "name": name,
            "size": 2048,
            "tmp_url": "https://expired.example.test/tmp/review-copy",
            "type": "text/html",
            "url": (
                "https://open.feishu.cn/open-apis/drive/v1/medias/"
                f"{file_token}/download"
            ),
        }
    ]


def stringbed_fields() -> dict[str, object]:
    return {
        "Run ID": "run-stringbed-20260731",
        "应用名": "StringBed",
        "账号信息": {
            "text": (
                "stringbed@example.comAbc1D2ef🇩🇪德国2025550123"
                "https://sms-display.example.test/?code=visible"
            ),
            "link": "https://sms.example.test/?code=authoritative",
        },
        "代理信息": "192.0.2.10:1080:proxy-user:proxy-password",
        "代码 URL": {
            "text": "https://code.example.com/team/stringbed.git",
            "link": "https://code.example.com/team/stringbed.git",
        },
        "ABA Routing Number": "123456789",
        "Account Number": "9876543210",
        "顶级域名": "example.com",
        "正式包名": "com.example.stringbed",
        "正式域名(app/h5/im/log)": "app.example.com\nh5.example.com\nim.example.com\nlog.example.com",
        "隐私协议": {"text": "隐私", "link": "https://example.com/privacy"},
        "用户协议": {"text": "用户", "link": "https://example.com/terms"},
        "支持协议": {"text": "支持", "link": "https://example.com/support"},
        "应用类型": "生活方式-LIFESTYLE",
        "应用描述": "第一段\n\n第二段",
        "关键词": "生活,记录",
        "提审文案": review_copy_attachment(),
        "虚拟机": "",
    }


def test_absolute_script_entry_starts_outside_project_directory(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "utm_notion.py"), "--help"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--run-id RUN_ID" in result.stdout
    assert "--app-name APP_NAME" in result.stdout
    assert "--vm-name VM_NAME" in result.stdout


def test_parse_feishu_wiki_url_returns_exact_node_table_and_view() -> None:
    assert utm_notion.parse_feishu_wiki_url(TARGET_FEISHU_WIKI_URL) == (
        "C70TwyJevipDZakMTWYcusTwnhh",
        "tbl5OOyYst8BqZ6x",
        "vewjQVBVeu",
    )


@pytest.mark.parametrize(
    "url",
    [
        (
            "https://example.test/wiki/C70TwyJevipDZakMTWYcusTwnhh"
            "?table=tbl5OOyYst8BqZ6x&view=vewjQVBVeu"
        ),
        (
            "https://qv0zc1dq6qy.feishu.cn/base/C70TwyJevipDZakMTWYcusTwnhh"
            "?table=tbl5OOyYst8BqZ6x&view=vewjQVBVeu"
        ),
        (
            "https://qv0zc1dq6qy.feishu.cn/wiki/C70TwyJevipDZakMTWYcusTwnhh"
            "?table=tbl5OOyYst8BqZ6x"
        ),
        (
            "https://qv0zc1dq6qy.feishu.cn/wiki/C70TwyJevipDZakMTWYcusTwnhh"
            "?table=tbl5OOyYst8BqZ6x&table=tblOther&view=vewjQVBVeu"
        ),
    ],
)
def test_parse_feishu_wiki_url_rejects_ambiguous_or_non_wiki_sources(url: str) -> None:
    with pytest.raises(RuntimeError, match="Feishu Wiki URL"):
        utm_notion.parse_feishu_wiki_url(url)


def test_resolve_bitable_app_token_uses_wiki_node_obj_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_urls: list[str] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return (
                b'{"code":0,"msg":"success","data":{"node":{'
                b'"obj_type":"bitable",'
                b'"obj_token":"XW2DbRbx7aG1URs8KfTcN0nlnhb"}}}'
            )

    def fake_urlopen(request: object, *, timeout: int):
        assert timeout == 30
        requested_urls.append(str(getattr(request, "full_url")))
        return FakeResponse()

    monkeypatch.setattr(utm_notion.urllib.request, "urlopen", fake_urlopen)

    app_token = utm_notion.resolve_bitable_app_token(
        "tenant-token",
        "C70TwyJevipDZakMTWYcusTwnhh",
    )

    assert app_token == "XW2DbRbx7aG1URs8KfTcN0nlnhb"
    assert requested_urls == [
        "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node"
        "?token=C70TwyJevipDZakMTWYcusTwnhh"
    ]


def test_execute_prefers_project_env_for_utm_notion_feishu_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                "UTM_NOTION_FEISHU_APP_TOKEN=bascnNewAppToken123",
                "UTM_NOTION_FEISHU_TABLE_ID=tblNewTable123",
                "UTM_NOTION_FEISHU_VIEW_ID=vewNewView123",
                "FEISHU_APP_ID=cliExampleApp123",
                "FEISHU_APP_SECRET=example-secret",
                "NOTION_TOKEN=example-notion-token",
                "NOTION_ROOT_PAGE_ID=example-notion-root",
                "SUBMISSION_HOST_MACHINE=Test Host",
                "SUBMISSION_VM_IMAGES_DIR=/tmp/test-vm-images",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(utm_notion, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("UTM_NOTION_FEISHU_APP_TOKEN", "bascnOldAppToken123")
    monkeypatch.setenv("UTM_NOTION_FEISHU_TABLE_ID", "tblOldTable123")
    monkeypatch.setenv("UTM_NOTION_FEISHU_VIEW_ID", "vewOldView123")
    monkeypatch.setattr(utm_notion, "get_tenant_access_token", lambda *_: "token")

    captured: dict[str, str] = {}

    class StopAfterClient(RuntimeError):
        pass

    class CapturingClient:
        def __init__(
            self,
            token: str,
            app_token: str,
            table_id: str,
            view_id: str,
        ) -> None:
            captured.update(
                token=token,
                app_token=app_token,
                table_id=table_id,
                view_id=view_id,
            )

        def find_exact_record(self, **_kwargs: str) -> dict[str, object]:
            raise StopAfterClient

    monkeypatch.setattr(utm_notion, "FeishuBitableClient", CapturingClient)

    with pytest.raises(StopAfterClient):
        utm_notion.execute(app_name="PackWise")

    assert captured == {
        "token": "token",
        "app_token": "bascnNewAppToken123",
        "table_id": "tblNewTable123",
        "view_id": "vewNewView123",
    }


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("生活", "LIFESTYLE"),
        ("生活方式", "LIFESTYLE"),
        ("LIFESTYLE", "LIFESTYLE"),
        ("生活方式-LIFESTYLE", "LIFESTYLE"),
        ("图形与设计", "GRAPHICS_AND_DESIGN"),
        ("图形与设计-Graphics & Design", "GRAPHICS_AND_DESIGN"),
        ("图形和设计-Graphics & Design", "GRAPHICS_AND_DESIGN"),
        ("摄影和录像", "PHOTO_AND_VIDEO"),
        ("摄影和录像-Photo & Video", "PHOTO_AND_VIDEO"),
    ],
)
def test_normalize_category_accepts_chinese_enum_and_enum_suffix(source: str, expected: str) -> None:
    assert normalize_category(source) == expected


def test_build_registration_fields_uses_verified_sources_and_fixed_team() -> None:
    account, application = build_registration_fields(stringbed_fields())

    assert account == {
        "邮箱：": "stringbed@example.com",
        "初始密码：": "Abc1D2ef",
        "电话：": "+12025550123",
        "电话短信接收平台：": "https://sms-display.example.test/?code=visible",
        "代理ip:": "192.0.2.10",
        "代理端口:": "1080",
        "代理用户名：": "proxy-user",
        "代理用户密码：": "proxy-password",
        "代码链接：": "https://code.example.com/team/stringbed.git",
        "ABA Routing Number：": "123456789",
        "Account Number：": "9876543210",
    }
    assert application == {
        "应用名: ": "StringBed",
        "团队: ": "灵光",
        "顶级域名: ": "example.com",
        "正式包名: ": "com.example.stringbed",
        "正式域名: ": "app.example.com\nh5.example.com\nim.example.com\nlog.example.com",
        "隐私协议: ": "https://example.com/privacy",
        "用户协议: ": "https://example.com/terms",
        "支持链接: ": "https://example.com/support",
        "应用类型：": "LIFESTYLE",
        "应用描述：": "第一段\n\n第二段",
        "关键词:": "生活,记录",
        **FULL_REVIEW_COPY_PARSED,
    }


def test_application_labels_append_review_copy_after_existing_fields() -> None:
    assert APPLICATION_LABELS[-5:] == REVIEW_COPY_LABELS
    assert APPLICATION_LABELS.index("关键词:") < APPLICATION_LABELS.index("Subtitle：")
    assert APPLICATION_LABELS.index("应用描述：") < APPLICATION_LABELS.index("关键词:")
    assert "关键词:" not in APPLICATION_MULTILINE_LABELS
    assert APPLICATION_MULTILINE_LABELS == {
        "正式域名: ",
        "应用描述：",
        "Description：",
        "App Review Notes：",
    }


def test_application_template_matches_live_sixteen_line_block() -> None:
    lines = APPLICATION_TEMPLATE.split("\n")

    assert len(APPLICATION_LABELS) == 16
    assert len(lines) == 16
    assert not APPLICATION_TEMPLATE.endswith("\n")
    assert lines == [
        label if label != "团队: " else "团队: 灵光" for label in APPLICATION_LABELS
    ]
    for label, line in zip(APPLICATION_LABELS, lines, strict=True):
        assert line.startswith(label)


def test_parse_review_copy_html_reads_textarea_ids_and_unescapes_entities() -> None:
    parsed = parse_review_copy_html(REVIEW_COPY_HTML_FULL)

    assert parsed == FULL_REVIEW_COPY_PARSED
    assert "MUST-NOT-USE-THIS-SUBTITLE" not in parsed.values()
    assert "MUST-NOT-USE-THIS-DESCRIPTION" not in parsed.values()
    assert "GAMES" not in parsed.values()
    assert "doesn't" in parsed["Description："]
    assert "whats_new" not in parsed
    assert "copyright" not in parsed
    assert "Name" not in parsed


def test_parse_review_copy_html_accepts_merged_heading_without_copyright() -> None:
    assert parse_review_copy_html(REVIEW_COPY_HTML_MERGED) == MERGED_REVIEW_COPY_PARSED


def test_parse_review_copy_html_falls_back_to_values_json_for_a_missing_textarea() -> None:
    html = """
    <h1>App Store Connect 复制区</h1>
    <textarea id="subtitle">From textarea</textarea>
    <script>
    const values={
      subtitle: 'From JSON subtitle',
      promotional_text: 'From JSON promo',
      description: 'From JSON description',
      keywords: 'json, keywords',
      review_notes: 'From JSON notes'
    };
    </script>
    """

    assert parse_review_copy_html(html) == {
        "Subtitle：": "From textarea",
        "Promotional Text：": "From JSON promo",
        "Description：": "From JSON description",
        "Keywords：": "json, keywords",
        "App Review Notes：": "From JSON notes",
    }


def test_review_copy_file_token_reads_attachment_list_shape() -> None:
    cell = review_copy_attachment()
    assert review_copy_file_token(cell) == REVIEW_COPY_FILE_TOKEN
    assert review_copy_file_token(None) == ""
    assert review_copy_file_token([]) == ""
    assert review_copy_file_token("not-an-attachment") == ""
    with pytest.raises(RuntimeError, match="exactly one attachment"):
        review_copy_file_token(review_copy_attachment() + review_copy_attachment("other"))


def test_download_review_copy_html_gets_media_by_file_token_not_tmp_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_request(
        url: str,
        *,
        method: str = "GET",
        token: str | None = None,
        json_body: object = None,
        label: str,
    ) -> bytes:
        seen.update(url=url, method=method, token=token, label=label)
        return REVIEW_COPY_HTML_FULL.encode("utf-8")

    monkeypatch.setattr(utm_notion, "_feishu_media_request", fake_request)
    html = REAL_DOWNLOAD_REVIEW_COPY_HTML(
        REVIEW_COPY_FILE_TOKEN, token="tenant-token"
    )

    assert html == REVIEW_COPY_HTML_FULL
    assert seen == {
        "url": (
            "https://open.feishu.cn/open-apis/drive/v1/medias/"
            f"{REVIEW_COPY_FILE_TOKEN}/download"
        ),
        "method": "GET",
        "token": "tenant-token",
        "label": "提审文案 attachment download",
    }
    assert "expired.example.test" not in str(seen["url"])


def test_build_registration_fields_downloads_review_copy_by_file_token() -> None:
    seen: list[str] = []

    def download(file_token: str) -> str:
        seen.append(file_token)
        return REVIEW_COPY_HTML_FULL

    _, application = build_registration_fields(
        stringbed_fields(),
        download_review_copy=download,
    )

    assert seen == [REVIEW_COPY_FILE_TOKEN]
    assert application["应用描述："] == "第一段\n\n第二段"
    assert application["关键词:"] == "生活,记录"
    for label, value in FULL_REVIEW_COPY_PARSED.items():
        assert application[label] == value


def test_build_registration_fields_maps_merged_heading_attachment() -> None:
    fields = stringbed_fields()
    fields["提审文案"] = review_copy_attachment(
        "file-review-copy-merged",
        "FixtureApp-review-copy-synthetic.html",
    )

    _, application = build_registration_fields(fields)

    assert application["应用描述："] == "第一段\n\n第二段"
    assert application["关键词:"] == "生活,记录"
    for label, value in MERGED_REVIEW_COPY_PARSED.items():
        assert application[label] == value


def test_missing_review_copy_attachment_follows_required_field_policy() -> None:
    fields = stringbed_fields()
    fields["提审文案"] = None

    with pytest.raises(RuntimeError, match="提审文案"):
        build_registration_fields(fields)

    _, application = build_registration_fields(fields, fill_missing_with_test=True)
    for label in REVIEW_COPY_LABELS:
        assert application[label] == "test"
    assert application["应用描述："] == "第一段\n\n第二段"
    assert application["关键词:"] == "生活,记录"


def test_missing_review_copy_id_follows_required_field_policy() -> None:
    html = """
    <h1>App Store Connect 复制区</h1>
    <textarea id="subtitle">Only subtitle present</textarea>
    <script>const values={ subtitle: 'Only subtitle present' };</script>
    """
    fields = stringbed_fields()

    with pytest.raises(RuntimeError, match=r"提审文案\.promotional_text"):
        build_registration_fields(fields, download_review_copy=lambda _token: html)

    _, application = build_registration_fields(
        fields,
        fill_missing_with_test=True,
        download_review_copy=lambda _token: html,
    )
    assert application["Subtitle："] == "Only subtitle present"
    assert application["Promotional Text："] == "test"
    assert application["Description："] == "test"
    assert application["Keywords："] == "test"
    assert application["App Review Notes："] == "test"
    assert application["应用描述："] == "第一段\n\n第二段"
    assert application["关键词:"] == "生活,记录"


def test_fill_template_fields_writes_multiline_review_copy_labels() -> None:
    _account, application = build_registration_fields(stringbed_fields())

    application_text = fill_template_fields(
        APPLICATION_TEMPLATE,
        APPLICATION_LABELS,
        application,
        multiline_labels=APPLICATION_MULTILINE_LABELS,
    )

    assert "应用描述：第一段\n\n第二段\n关键词:生活,记录\n" in application_text
    assert application_text.endswith(
        "Subtitle：Daily notes in one glance\n"
        "Promotional Text：Capture, tag, and revisit what matters\n"
        "Description：StringBed keeps short notes and reminders together.\n"
        "\n"
        "Write freely, then find them later. It doesn't keep drafts.\n"
        "Keywords：notes, reminders, tags\n"
        "App Review Notes：This submission uses placeholder review notes\n"
        "for a synthetic fixture only.\n"
        "\n"
        "Please check the demo account."
    )
    assert not application_text.endswith("\n")


def test_application_section_readback_preserves_multiline_fields_without_trailing_newline() -> None:
    _account, application = build_registration_fields(stringbed_fields())
    desired = fill_template_fields(
        APPLICATION_TEMPLATE,
        APPLICATION_LABELS,
        application,
        multiline_labels=APPLICATION_MULTILINE_LABELS,
    )

    assert not desired.endswith("\n")
    verify_registration_readback("", "", desired, desired)
    with pytest.raises(RuntimeError, match="readback mismatch"):
        verify_registration_readback("", "", desired + "\n", desired)

    readback = read_template_fields(
        desired,
        APPLICATION_LABELS,
        multiline_labels=APPLICATION_MULTILINE_LABELS,
    )
    for label, value in application.items():
        assert readback[label] == value
    assert readback["应用描述："] == application["应用描述："]
    assert readback["关键词:"] == "生活,记录"
    assert readback["App Review Notes："] == application["App Review Notes："]
    for label in REVIEW_COPY_LABELS:
        assert label not in readback["关键词:"]
        assert application[label] not in readback["关键词:"]
        assert readback[label] == application[label]
    fields = stringbed_fields()
    fields["账号信息"] = {
        "text": "stringbed@example.comAbc1D2ef🇩🇪德国2025550123",
        "link": "https://sms.example.test/?code=authoritative",
    }

    account, _ = build_registration_fields(fields)

    assert account["电话短信接收平台："] == "https://sms.example.test/?code=authoritative"


@pytest.mark.parametrize(
    "account_cell",
    [
        (
            "stringbed@example.comAbc1D2ef🇩🇪德国2025550123"
            "https://sms-display.example.test/?code=visible"
        ),
        [
            {
                "text": (
                    "stringbed@example.comAbc1D2ef🇩🇪德国2025550123"
                    "https://sms-display.example.test/?code=visible"
                )
            }
        ],
    ],
)
def test_build_registration_fields_accepts_textual_account_cell_with_inline_url(
    account_cell: object,
) -> None:
    fields = stringbed_fields()
    fields["账号信息"] = account_cell

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abc1D2ef"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == (
        "https://sms-display.example.test/?code=visible"
    )


def test_build_registration_fields_accepts_space_separated_international_account() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "stringbed@example.xyz Letters 441234567890 "
        "https://sms-display.example.test/?code=visible"
    )

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.xyz"
    assert account["初始密码："] == "Letters"
    assert account["电话："] == "+441234567890"
    assert account["电话短信接收平台："] == (
        "https://sms-display.example.test/?code=visible"
    )


@pytest.mark.parametrize(
    "account_text",
    [
        (
            "Denmark | Mix3d!Pass | +12025550123 | "
            "stringbed@example.com | "
            "https://sms-display.example.test/?code=visible"
        ),
        (
            "https://sms-display.example.test/?code=visible，"
            "电话：+12025550123；邮箱：stringbed@example.com；"
            "密码：Mix3d!Pass；国家：丹麦"
        ),
    ],
)
def test_build_registration_fields_accepts_arbitrary_account_field_order(
    account_text: str,
) -> None:
    fields = stringbed_fields()
    fields["账号信息"] = account_text

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Mix3d!Pass"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == (
        "https://sms-display.example.test/?code=visible"
    )


def test_build_registration_fields_accepts_unknown_email_suffix_by_structure() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "账号 stringbed@example.technology | +12025550123 | "
        "Abc1D2ef! | https://sms-display.example.test/?code=visible"
    )

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.technology"
    assert account["初始密码："] == "Abc1D2ef!"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == (
        "https://sms-display.example.test/?code=visible"
    )


def test_build_registration_fields_accepts_lixsms_rich_text_account() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = [
        {"text": "2025550123"},
        {"text": "查看短信", "link": "https://lixsms.com/sms?id=synthetic"},
        {"text": "stringbed@example.", "link": "https://lixsms.com/ignored"},
        {"text": "comAbc1D2ef", "link": "https://ignored.example/b"},
    ]

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abc1D2ef"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == (
        "https://lixsms.com/sms?id=synthetic"
    )


def test_build_registration_fields_accepts_lixsms_four_line_account() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "2025550123\r\n"
        "https://lixsms.com/sms?id=synthetic\r\n"
        "stringbed@example.com\r\n"
        "Abc1D2ef"
    )

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abc1D2ef"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == (
        "https://lixsms.com/sms?id=synthetic"
    )


@pytest.mark.parametrize(
    "account_cell",
    [
        [
            {"text": "202555012"},
            {"text": "查看短信", "link": "https://lixsms.com/sms?id=synthetic"},
            {"text": "stringbed@example.", "link": "https://ignored.example/a"},
            {"text": "comAbc1D2ef", "link": "https://ignored.example/b"},
        ],
        [
            {"text": "2025550123"},
            {"text": "查看短信", "link": "https://lixsms.com/sms?id=synthetic"},
            {"text": "first@example.comsecond@example.", "link": "https://ignored.example/a"},
            {"text": "comAbc1D2ef", "link": "https://ignored.example/b"},
        ],
    ],
)
def test_build_registration_fields_rejects_ambiguous_lixsms_account(
    account_cell: object,
) -> None:
    fields = stringbed_fields()
    fields["账号信息"] = account_cell

    with pytest.raises(RuntimeError, match="Lixsms"):
        build_registration_fields(fields)


def test_generic_account_parser_preserves_metadata_words_inside_password() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "stringbed@example.com | Account9Pass | +12025550123 | "
        "https://sms-display.example.test/?code=visible"
    )

    account, _ = build_registration_fields(fields)

    assert account["初始密码："] == "Account9Pass"


def test_generic_account_parser_deduplicates_repeated_email_occurrences() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "stringbed@example.com | Mix3d!Pass | +12025550123 | "
        "STRINGBED@EXAMPLE.COM | "
        "https://sms-display.example.test/?code=visible"
    )

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"


def test_generic_account_parser_rejects_distinct_email_candidates() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "stringbed@example.com | Mix3d!Pass | +12025550123 | "
        "another@example.com | "
        "https://sms-display.example.test/?code=visible"
    )

    with pytest.raises(RuntimeError, match="email"):
        build_registration_fields(fields)


def test_generic_account_parser_deduplicates_repeated_phone_occurrences() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "stringbed@example.com | Mix3d!Pass | +12025550123 | "
        "12025550123 | https://sms-display.example.test/?code=visible"
    )

    account, _ = build_registration_fields(fields)

    assert account["电话："] == "+12025550123"


def test_generic_account_parser_rejects_distinct_phone_candidates() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "stringbed@example.com | Mix3d!Pass | +12025550123 | "
        "+12025550124 | https://sms-display.example.test/?code=visible"
    )

    with pytest.raises(RuntimeError, match="phone"):
        build_registration_fields(fields)


def test_generic_account_parser_deduplicates_repeated_password_occurrences() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "stringbed@example.com | Mix3d!Pass | +12025550123 | "
        "Mix3d!Pass | https://sms-display.example.test/?code=visible"
    )

    account, _ = build_registration_fields(fields)

    assert account["初始密码："] == "Mix3d!Pass"


def test_generic_account_parser_rejects_distinct_password_candidates() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "stringbed@example.com | Mix3d!Pass | +12025550123 | "
        "Other4Pass! | https://sms-display.example.test/?code=visible"
    )

    with pytest.raises(RuntimeError, match="password"):
        build_registration_fields(fields)


def test_generic_account_parser_ignores_phone_like_digits_inside_email() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "1234567890user@example.com | Mix3d!Pass | +12025550123 | "
        "https://sms-display.example.test/?code=visible"
    )

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "1234567890user@example.com"
    assert account["电话："] == "+12025550123"


def test_generic_account_parser_preserves_legal_url_punctuation() -> None:
    fields = stringbed_fields()
    sms_url = "https://sms-display.example.test/path,segment"
    fields["账号信息"] = (
        "stringbed@example.com | Mix3d!Pass | +12025550123 | " + sms_url
    )

    account, _ = build_registration_fields(fields)

    assert account["电话短信接收平台："] == sms_url


def test_build_registration_fields_accepts_labelled_account_info_with_prefix() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = {
        "text": (
            "✅🇩🇪德国MC7账号：stringbed@example.com密码：Abc1D2ef接码："
            "2025550123https://sms-display.example.test/?code=visible"
        ),
        "link": "http://not-a-sms-url.example.test",
    }

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abc1D2ef"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == "https://sms-display.example.test/?code=visible"


@pytest.mark.parametrize(
    "account_text",
    [
        (
            "https://sms-display.example.test/?code=visible "
            "✅🇩🇪德国MC7账号：stringbed@example.com密码：Abc1D2ef接码：2025550123"
        ),
        (
            "✅🇩🇪德国MC7账号：stringbed@example.com密码：Abc1D2ef "
            "https://sms-display.example.test/?code=visible 接码：2025550123"
        ),
    ],
)
def test_build_registration_fields_accepts_unique_inline_sms_url_in_any_position(
    account_text: str,
) -> None:
    fields = stringbed_fields()
    fields["账号信息"] = {
        "text": account_text,
        "link": "http://not-a-sms-url.example.test",
    }

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abc1D2ef"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == (
        "https://sms-display.example.test/?code=visible"
    )


def test_build_registration_fields_accepts_unlabelled_phone_before_url_and_country() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = {
        "text": (
            "stringbed@example.comAbc1D2ef+12025550123----"
            "https://sms-display.example.test/?code=visible 🇩🇰 丹麦"
        ),
        "link": "http://not-a-sms-url.example.test",
    }

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abc1D2ef"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == (
        "https://sms-display.example.test/?code=visible"
    )


def test_build_registration_fields_accepts_api1997_phone_url_email_without_separator() -> None:
    fields = stringbed_fields()
    fixture_url_identifier = "Ab1" + "x" * 31
    assert len(fixture_url_identifier) == 34
    sms_url = f"https://api1997.com/smsrecord?token={fixture_url_identifier}"
    fields["账号信息"] = {
        "text": (
            f"+12025550123----{sms_url}"
            "stringbed@example.comAbc1D2ef 🇩🇰 丹麦"
        ),
        "link": (
            "http://+12025550123----"
            f"{sms_url}stringbed@example.comAbc1D2ef 🇩🇰 丹麦"
        ),
    }

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abc1D2ef"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == sms_url


def test_build_registration_fields_accepts_space_separated_phone_url_email_password_country() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = (
        "+12025550123  https://sms-display.example.test/?code=visible "
        "stringbed@example.com Abcdef1Gh 🇩🇰 丹麦"
    )

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abcdef1Gh"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == (
        "https://sms-display.example.test/?code=visible"
    )


def test_build_registration_fields_accepts_xsd20vip_compact_account_format() -> None:
    fields = stringbed_fields()
    fixture_url_identifier = "PG2" + "c" * 31
    assert len(fixture_url_identifier) == 34
    sms_url = f"https://xsd20vip.com/smsrecord?token={fixture_url_identifier}"
    fields["账号信息"] = {
        "text": (
            f"+12025550123----{sms_url}"
            "haraldurposselt@icloud.comEk161121Denmark 🇩🇰 丹麦"
        ),
        "link": "http://not-authoritative.example.test",
    }

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "haraldurposselt@icloud.com"
    assert account["初始密码："] == "Ek161121"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == sms_url


def test_build_registration_fields_accepts_country_first_multiline_account() -> None:
    fields = stringbed_fields()
    fixture_url_identifier = "Ab1" + "x" * 31
    sms_url = f"https://api1997.com/sms-record?token={fixture_url_identifier}"
    fields["账号信息"] = (
        "英国\n"
        "stringbed@example.com\n"
        "Abc1D2ef!\n"
        "12025550123\n"
        f"{sms_url}"
    )

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abc1D2ef!"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == sms_url


def test_build_registration_fields_accepts_provider_country_email_password_dollar_phone() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = {
        "text": (
            "Outlook 🇭🇷 克罗地亚stringbed@example.comAbc1D2ef$+12025550123----"
            "https://sms-display.example.test/?code=visible"
        ),
        "link": "https://sms.example.test/?code=authoritative",
    }

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abc1D2ef$"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == (
        "https://sms-display.example.test/?code=visible"
    )


def test_build_registration_fields_accepts_provider_email_password_and_plain_phone() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = {
        "text": (
            "Outlook 🇫🇮stringbed@example.comAbcdefg12"
            "2025550123https://sms-display.example.test/?code=visible"
        ),
        "link": "https://sms.example.test/?code=authoritative",
    }

    account, _ = build_registration_fields(fields)

    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abcdefg12"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == (
        "https://sms-display.example.test/?code=visible"
    )


def test_build_registration_fields_uses_pending_domain_when_legacy_domain_fields_are_empty() -> None:
    fields = stringbed_fields()
    fields["顶级域名"] = ""
    fields["正式域名(app/h5/im/log)"] = ""
    fields["待购买域名"] = "example.com"

    _, application = build_registration_fields(fields)

    assert application["顶级域名: "] == "example.com"
    assert application["正式域名: "] == (
        "app.example.com\nh5.example.com\nim.example.com\nlog.example.com"
    )


def test_build_registration_fields_rejects_unverified_email_link() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = {
        "text": "Abc1D2ef🇩🇪德国2025550123https://sms-display.example.test/?code=visible",
        "link": "https://sms.example.test/?code=authoritative",
    }

    with pytest.raises(RuntimeError, match="email"):
        build_registration_fields(fields)


def test_build_registration_fields_remains_strict_when_required_values_are_missing() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = None

    with pytest.raises(RuntimeError, match="账号信息"):
        build_registration_fields(fields)


def test_build_registration_fields_fills_missing_values_with_test_only_when_requested() -> None:
    fields = stringbed_fields()
    fields.update(
        {
            "账号信息": None,
            "代理信息": "",
            "代码 URL": None,
            "ABA Routing Number": "",
            "Account Number": None,
            "正式域名(app/h5/im/log)": "",
            "隐私协议": None,
            "用户协议": "",
            "支持协议": None,
        }
    )

    account, application = build_registration_fields(
        fields,
        fill_missing_with_test=True,
    )

    assert account == {
        "邮箱：": "test",
        "初始密码：": "test",
        "电话：": "test",
        "电话短信接收平台：": "test",
        "代理ip:": "test",
        "代理端口:": "test",
        "代理用户名：": "test",
        "代理用户密码：": "test",
        "代码链接：": "test",
    }
    assert "ABA Routing Number：" not in account
    assert "Account Number：" not in account
    assert application["隐私协议: "] == "test"
    assert application["用户协议: "] == "test"
    assert application["支持链接: "] == "test"
    assert application["应用名: "] == "StringBed"
    assert application["正式域名: "] == "test"
    assert application["应用类型："] == "LIFESTYLE"
    assert application["应用描述："] == "第一段\n\n第二段"
    assert application["关键词:"] == "生活,记录"
    for label, value in FULL_REVIEW_COPY_PARSED.items():
        assert application[label] == value


def test_build_registration_fields_rejects_an_invalid_agreement_url() -> None:
    fields = stringbed_fields()
    fields["隐私协议"] = "not-a-url"

    with pytest.raises(RuntimeError, match="隐私协议"):
        build_registration_fields(fields)

def test_empty_optional_bank_fields_are_omitted_to_preserve_the_template() -> None:
    fields = stringbed_fields()
    fields["ABA Routing Number"] = ""
    fields["Account Number"] = None

    account, _ = build_registration_fields(fields)

    assert "ABA Routing Number：" not in account
    assert "Account Number：" not in account


def test_generated_modified_password_meets_required_character_classes() -> None:
    for _ in range(100):
        password = utm_notion.generate_random_password()
        assert len(password) == 16
        assert any(character.islower() for character in password)
        assert any(character.isupper() for character in password)
        assert any(character.isdigit() for character in password)
        assert password.isalnum()


def test_modified_password_is_generated_only_for_blank_template_field() -> None:
    replacements: dict[str, str] = {}
    generated = utm_notion.ensure_modified_password(ACCOUNT_TEMPLATE, replacements)

    assert generated is True
    assert utm_notion.password_meets_requirements(replacements["修改后的密码："])

    existing = ACCOUNT_TEMPLATE.replace("修改后的密码：", "修改后的密码：Existing9Password")
    replacements = {}
    generated = utm_notion.ensure_modified_password(existing, replacements)

    assert generated is False
    assert "修改后的密码：" not in replacements


def test_fill_template_fields_preserves_labels_spacing_and_mapped_values() -> None:
    account, application = build_registration_fields(stringbed_fields())

    account_text = fill_template_fields(ACCOUNT_TEMPLATE, ACCOUNT_LABELS, account)
    application_text = fill_template_fields(
        APPLICATION_TEMPLATE,
        APPLICATION_LABELS,
        application,
        multiline_labels=APPLICATION_MULTILINE_LABELS,
    )

    assert "邮箱：stringbed@example.com\n" in account_text
    assert "初始密码：Abc1D2ef\n" in account_text
    assert "电话：+12025550123\n" in account_text
    assert "电话短信接收平台：https://sms-display.example.test/?code=visible\n" in account_text
    assert "代码链接：https://code.example.com/team/stringbed.git\n" in account_text
    assert application_text == """应用名: StringBed
团队: 灵光
顶级域名: example.com
正式包名: com.example.stringbed
正式域名: app.example.com
h5.example.com
im.example.com
log.example.com
隐私协议: https://example.com/privacy
用户协议: https://example.com/terms
支持链接: https://example.com/support
应用类型：LIFESTYLE
应用描述：第一段

第二段
关键词:生活,记录
Subtitle：Daily notes in one glance
Promotional Text：Capture, tag, and revisit what matters
Description：StringBed keeps short notes and reminders together.

Write freely, then find them later. It doesn't keep drafts.
Keywords：notes, reminders, tags
App Review Notes：This submission uses placeholder review notes
for a synthetic fixture only.

Please check the demo account."""


class FakeFeishu(FeishuBitableClient):
    def __init__(self, records: list[dict]) -> None:
        super().__init__("token", "app", "table", "view")
        self.records = records
        self.patches: list[tuple[str, dict]] = []

    def _request(self, method: str, path: str, *, query=None, payload=None):
        if method == "GET" and path.endswith("/records"):
            return {"items": self.records, "has_more": False}
        if method == "GET" and "/records/" in path:
            record_id = path.rsplit("/", 1)[1]
            return {"record": next(item for item in self.records if item["record_id"] == record_id)}
        if method == "PUT" and "/records/" in path:
            record_id = path.rsplit("/", 1)[1]
            self.patches.append((record_id, payload))
            record = next(item for item in self.records if item["record_id"] == record_id)
            record["fields"].update(payload["fields"])
            return {"record": record}
        raise AssertionError((method, path, query, payload))


def test_feishu_exact_match_ignores_configured_view_filter() -> None:
    target = {"record_id": "rec-stringbed", "fields": stringbed_fields()}

    class ViewFilteredFeishu(FeishuBitableClient):
        def __init__(self) -> None:
            super().__init__("token", "app", "table", "view")
            self.queries: list[dict[str, object]] = []

        def _request(self, method: str, path: str, *, query=None, payload=None):
            assert method == "GET"
            assert path.endswith("/records")
            assert payload is None
            self.queries.append(dict(query or {}))
            records = [] if query and query.get("view_id") == "view" else [target]
            return {"items": records, "has_more": False}

    client = ViewFilteredFeishu()

    record = client.find_exact_record(app_name="StringBed")

    assert record == target
    assert client.queries == [{"page_size": 500}]


def test_feishu_exact_match_rejects_full_table_duplicates() -> None:
    first = {"record_id": "rec-first", "fields": stringbed_fields()}
    second = {"record_id": "rec-second", "fields": stringbed_fields()}

    class DuplicateViewFeishu(FeishuBitableClient):
        def __init__(self) -> None:
            super().__init__("token", "app", "table", "view")
            self.queries: list[dict[str, object]] = []

        def _request(self, method: str, path: str, *, query=None, payload=None):
            assert method == "GET"
            assert path.endswith("/records")
            assert payload is None
            self.queries.append(dict(query or {}))
            return {"items": [first, second], "has_more": False}

    client = DuplicateViewFeishu()

    with pytest.raises(RuntimeError, match=r"got 2$"):
        client.find_exact_record(app_name="StringBed")
    assert client.queries == [{"page_size": 500}]


def test_feishu_exact_match_rejects_duplicates_hidden_by_configured_view() -> None:
    first = {"record_id": "rec-first", "fields": stringbed_fields()}
    second = {"record_id": "rec-second", "fields": stringbed_fields()}

    class DuplicateTableFeishu(FeishuBitableClient):
        def __init__(self) -> None:
            super().__init__("token", "app", "table", "view")
            self.queries: list[dict[str, object]] = []

        def _request(self, method: str, path: str, *, query=None, payload=None):
            assert method == "GET"
            assert path.endswith("/records")
            assert payload is None
            self.queries.append(dict(query or {}))
            items = [] if query and "view_id" in query else [first, second]
            return {"items": items, "has_more": False}

    client = DuplicateTableFeishu()

    with pytest.raises(RuntimeError, match=r"got 2$"):
        client.find_exact_record(app_name="StringBed")
    assert client.queries == [{"page_size": 500}]


def test_execute_preflights_vm_write_before_binding_and_notion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    record = {"record_id": "rec-stringbed", "fields": stringbed_fields()}

    class ForbiddenClient:
        def __init__(
            self,
            _token: str,
            _app_token: str,
            _table_id: str,
            _view_id: str,
        ) -> None:
            pass

        def find_exact_record(self, **_kwargs: str) -> dict[str, object]:
            return record

        def preflight_vm_write(self, _record: dict[str, object]) -> None:
            events.append("preflight")
            raise RuntimeError("Feishu API HTTP 403: code=91403 msg=Forbidden")

        def ensure_vm(self, _record: dict[str, object], _vm_name: str) -> bool:
            events.append("ensure")
            raise RuntimeError("Feishu API HTTP 403: code=91403 msg=Forbidden")

    def unexpected_bind(*_args: object, **_kwargs: object) -> str:
        events.append("bind")
        return "gvby"

    def unexpected_notion() -> object:
        events.append("notion")
        raise AssertionError("Notion must not be called after Feishu write preflight fails")

    runtime_config = utm_notion.UtmNotionRuntimeConfig(
        feishu_app_id=FIXTURE_APP_IDENTIFIER,
        feishu_app_secret=FIXTURE_APP_CREDENTIAL,
        configured_source=("wiki", TARGET_FEISHU_WIKI_URL, "", ""),
        notion_token=FIXTURE_NOTION_CREDENTIAL,
        notion_root_page_id=FIXTURE_NOTION_ROOT,
        notion_template_title="template",
        host_title="Mac Studio",
        images_dir=tmp_path,
    )
    monkeypatch.setattr(
        utm_notion,
        "load_runtime_config",
        lambda **_kwargs: runtime_config,
    )
    monkeypatch.setattr(utm_notion, "get_tenant_access_token", lambda *_args: "token")
    monkeypatch.setattr(
        utm_notion,
        "resolve_utm_notion_source",
        lambda *_args: ("app", "tbl5OOyYst8BqZ6x", "vewjQVBVeu"),
    )
    monkeypatch.setattr(utm_notion, "FeishuBitableClient", ForbiddenClient)
    monkeypatch.setattr(utm_notion, "_bind_vm", unexpected_bind)
    monkeypatch.setattr(
        utm_notion,
        "notion_api_from_config",
        lambda _config: unexpected_notion(),
    )

    with pytest.raises(RuntimeError, match="91403"):
        utm_notion.execute(app_name="StringBed")

    assert events == ["preflight"]


def test_execute_with_explicit_vm_does_not_require_feishu_record_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    record = {"record_id": "rec-stringbed", "fields": stringbed_fields()}

    class ReadOnlyClient:
        def __init__(self, *_args: str) -> None:
            pass

        def find_exact_record(self, **_kwargs: str) -> dict[str, object]:
            return record

        def preflight_vm_write(self, _record: dict[str, object]) -> None:
            raise AssertionError("explicit VM must not require Feishu write preflight")

        def ensure_vm(self, _record: dict[str, object], _vm_name: str) -> bool:
            raise AssertionError("explicit VM must not require Feishu record update")

    class StopAfterExplicitBinding(RuntimeError):
        pass

    class ReadOnlyNotion:
        def verify_parent(self, _host: str) -> None:
            events.append("notion-verify")

        def create_registration_copy(self, _title: str) -> tuple[str, bool]:
            events.append("notion-create")
            raise StopAfterExplicitBinding

    def bind_exact(*_args: object, **_kwargs: object) -> str:
        events.append("bind")
        return "gvby"

    runtime_config = utm_notion.UtmNotionRuntimeConfig(
        feishu_app_id=FIXTURE_APP_IDENTIFIER,
        feishu_app_secret=FIXTURE_APP_CREDENTIAL,
        configured_source=("wiki", TARGET_FEISHU_WIKI_URL, "", ""),
        notion_token=FIXTURE_NOTION_CREDENTIAL,
        notion_root_page_id=FIXTURE_NOTION_ROOT,
        notion_template_title="template",
        host_title="Mac Studio",
        images_dir=tmp_path,
    )
    monkeypatch.setattr(
        utm_notion,
        "load_runtime_config",
        lambda **_kwargs: runtime_config,
    )
    monkeypatch.setattr(utm_notion, "get_tenant_access_token", lambda *_args: "token")
    monkeypatch.setattr(
        utm_notion,
        "resolve_utm_notion_source",
        lambda *_args: ("app", "tbl5OOyYst8BqZ6x", "vewjQVBVeu"),
    )
    monkeypatch.setattr(utm_notion, "FeishuBitableClient", ReadOnlyClient)
    monkeypatch.setattr(utm_notion, "_bind_vm", bind_exact)
    monkeypatch.setattr(
        utm_notion,
        "notion_api_from_config",
        lambda _config: ReadOnlyNotion(),
    )

    with pytest.raises(StopAfterExplicitBinding):
        utm_notion.execute(app_name="StringBed", vm_name="gvby")

    assert events == ["notion-verify", "bind", "notion-create"]


def test_empty_vm_write_preflight_is_same_value_write_with_independent_readback() -> None:
    fields = stringbed_fields()
    before_digest = utm_notion._fields_digest(fields, omit={"虚拟机"})

    class TrackingFeishu(FakeFeishu):
        def __init__(self, records: list[dict]) -> None:
            super().__init__(records)
            self.request_methods: list[str] = []

        def _request(self, method: str, path: str, *, query=None, payload=None):
            self.request_methods.append(method)
            return super()._request(method, path, query=query, payload=payload)

    client = TrackingFeishu([{"record_id": "rec-stringbed", "fields": fields}])
    record = client.find_exact_record(app_name="StringBed")
    client.request_methods.clear()

    client.preflight_vm_write(record)

    assert client.request_methods == ["GET", "PUT", "GET"]
    assert client.patches == [("rec-stringbed", {"fields": {"虚拟机": None}})]
    assert utm_notion._cell_text(record["fields"]["虚拟机"]) == ""
    assert utm_notion._fields_digest(record["fields"], omit={"虚拟机"}) == before_digest


def test_fields_digest_ignores_only_volatile_attachment_urls() -> None:
    before = {
        "研发截图": [
            {
                "file_token": "file-stable",
                "name": "shot.png",
                "size": 123,
                "type": "image/png",
                "url": "https://example.invalid/first",
                "tmp_url": "https://example.invalid/temp-first",
            }
        ]
    }
    after = {
        "研发截图": [
            {
                "file_token": "file-stable",
                "name": "shot.png",
                "size": 123,
                "type": "image/png",
                "url": "https://example.invalid/second",
                "tmp_url": "https://example.invalid/temp-second",
            }
        ]
    }

    assert utm_notion._fields_digest(before) == utm_notion._fields_digest(after)


def test_feishu_exact_run_match_and_vm_only_update() -> None:
    fields = stringbed_fields()
    client = FakeFeishu([{"record_id": "rec-stringbed", "fields": fields}])

    record = client.find_exact_record(run_id="run-stringbed-20260731")
    client.ensure_vm(record, "abcd")

    assert client.patches == [("rec-stringbed", {"fields": {"虚拟机": "abcd"}})]
    assert record["fields"]["应用名"] == "StringBed"


def test_feishu_does_not_overwrite_a_different_vm() -> None:
    fields = stringbed_fields()
    fields["虚拟机"] = "wxyz"
    client = FakeFeishu([{"record_id": "rec-stringbed", "fields": fields}])

    with pytest.raises(RuntimeError, match="already contains"):
        client.ensure_vm(client.find_exact_record(app_name="StringBed"), "abcd")

    assert client.patches == []


def test_feishu_idempotent_vm_binding_does_not_require_write_permission() -> None:
    fields = stringbed_fields()
    fields["虚拟机"] = "abcd"
    client = FakeFeishu([{"record_id": "rec-stringbed", "fields": fields}])

    changed = client.ensure_vm(client.find_exact_record(app_name="StringBed"), "abcd")

    assert changed is False
    assert client.patches == []


def test_bind_vm_reconciles_a_present_initialized_pool_bundle_before_claim(
    tmp_path: Path,
) -> None:
    database = tmp_path / "inventory.sqlite3"
    images = tmp_path / "images"
    images.mkdir()
    vm_name = reserve_vm_name(database, images, candidate_factory=lambda: "abcd")
    bundle = images / f"{vm_name}.utm"
    bundle.mkdir()
    register_clone(
        database,
        vm_name,
        "12345678-1234-1234-1234-1234567890AB",
        bundle,
        "02:00:00:00:00:01",
        "a" * 64,
    )
    set_available(database, vm_name, True)
    assert get_inventory_record(database, vm_name)["directory_present"] == 0

    claimed = utm_notion._bind_vm({}, "WaxCue", database, images)

    assert claimed == vm_name
    record = get_inventory_record(database, vm_name)
    assert record["directory_present"] == 1
    assert record["application_name"] == "WaxCue"
    assert record["available"] == 0


def test_bind_vm_claims_the_explicit_clone_instead_of_an_older_available_vm(
    tmp_path: Path,
) -> None:
    database = tmp_path / "inventory.sqlite3"
    images = tmp_path / "images"
    images.mkdir()
    for vm_name, suffix in (("abcd", "1"), ("wxyz", "2")):
        bundle = images / f"{vm_name}.utm"
        reserve_vm_name(
            database,
            images,
            candidate_factory=lambda value=vm_name: value,
        )
        bundle.mkdir()
        register_clone(
            database,
            vm_name,
            f"{suffix * 8}-{suffix * 4}-{suffix * 4}-{suffix * 4}-{suffix * 12}",
            bundle,
            f"02:00:00:00:00:0{suffix}",
            suffix * 64,
        )
        set_available(database, vm_name, True)

    claimed = utm_notion._bind_vm(
        {},
        "SowSheet",
        database,
        images,
        expected_vm_name="wxyz",
    )

    assert claimed == "wxyz"
    assert get_inventory_record(database, "abcd")["available"] == 1
    record = get_inventory_record(database, "wxyz")
    assert record["application_name"] == "SowSheet"
    assert record["available"] == 0


def test_bind_vm_allows_only_an_explicit_application_rename(tmp_path: Path) -> None:
    database = tmp_path / "inventory.sqlite3"
    images = tmp_path / "images"
    images.mkdir()
    bundle = images / "rbqi.utm"
    reserve_vm_name(database, images, candidate_factory=lambda: "rbqi")
    bundle.mkdir()
    register_clone(
        database,
        "rbqi",
        "12345678-1234-1234-1234-1234567890AB",
        bundle,
        "02:00:00:00:00:01",
        "a" * 64,
    )
    set_available(database, "rbqi", True)
    scan_inventory(database, images)
    mark_used(database, "rbqi", "RainyDay")

    claimed = utm_notion._bind_vm(
        {"虚拟机": "rbqi"},
        "RainyDay-Kids",
        database,
        images,
        expected_vm_name="rbqi",
        rename_from="RainyDay",
    )

    assert claimed == "rbqi"
    assert get_inventory_record(database, "rbqi")["application_name"] == "RainyDay-Kids"
