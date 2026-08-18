from __future__ import annotations

import json

import pytest

from scripts import utm_notion
from services import utm_notion_source


WIKI_URL = (
    "https://example.feishu.cn/wiki/ExampleWikiNode123"
    "?table=tblExample123&view=vewExample123"
)


@pytest.fixture(autouse=True)
def isolate_source_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in utm_notion_source.SOURCE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize(
    "configured",
    [
        {},
        {"UTM_NOTION_FEISHU_APP_TOKEN": "app-only"},
        {
            "UTM_NOTION_FEISHU_WIKI_URL": WIKI_URL,
            "UTM_NOTION_FEISHU_APP_TOKEN": "mixed-app",
            "UTM_NOTION_FEISHU_TABLE_ID": "mixed-table",
            "UTM_NOTION_FEISHU_VIEW_ID": "mixed-view",
        },
    ],
)
def test_execute_rejects_missing_partial_or_mixed_source_before_network(
    configured: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(utm_notion, "load_dotenv", lambda *_args, **_kwargs: None)
    for key, value in configured.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        utm_notion,
        "get_tenant_access_token",
        lambda *_args: pytest.fail("configuration must fail before tenant-token network"),
    )
    monkeypatch.setattr(
        utm_notion_source.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("configuration must fail before Wiki network"),
    )

    with pytest.raises(RuntimeError) as captured:
        utm_notion.execute(app_name="PackWise")

    message = str(captured.value)
    assert "UTM_NOTION_FEISHU" in message
    assert all(value not in message for value in configured.values())


def test_complete_direct_source_needs_no_wiki_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UTM_NOTION_FEISHU_APP_TOKEN", "direct-app")
    monkeypatch.setenv("UTM_NOTION_FEISHU_TABLE_ID", "direct-table")
    monkeypatch.setenv("UTM_NOTION_FEISHU_VIEW_ID", "direct-view")
    monkeypatch.setattr(
        utm_notion.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("direct source must not use Wiki network"),
    )

    configured = utm_notion_source.configured_feishu_source()

    assert utm_notion_source.resolve_feishu_source("tenant-token", configured) == (
        "direct-app",
        "direct-table",
        "direct-view",
    )


def test_wiki_source_resolves_base_token_after_local_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "code": 0,
                    "data": {
                        "node": {
                            "obj_type": "bitable",
                            "obj_token": "ResolvedBaseToken123",
                        }
                    },
                }
            ).encode()

    monkeypatch.setenv("UTM_NOTION_FEISHU_WIKI_URL", WIKI_URL)
    monkeypatch.setattr(
        utm_notion_source.urllib.request,
        "urlopen",
        lambda _request, *, timeout: FakeResponse(),
    )

    configured = utm_notion_source.configured_feishu_source()

    assert utm_notion_source.resolve_feishu_source("tenant-token", configured) == (
        "ResolvedBaseToken123",
        "tblExample123",
        "vewExample123",
    )


def test_source_has_no_fixed_bitable_identifier_defaults() -> None:
    assert not hasattr(utm_notion, "DEFAULT_APP_TOKEN")
    assert not hasattr(utm_notion, "DEFAULT_TABLE_ID")
    assert not hasattr(utm_notion, "DEFAULT_VIEW_ID")
