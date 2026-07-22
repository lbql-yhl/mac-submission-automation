#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.notion_api import NotionAPI


class FakeNotionAPI(NotionAPI):
    def __init__(self) -> None:
        super().__init__("test-token", "root-page")
        self.created = False
        self.code = "\n"
        self.toggle_code = ""
        self.create_payload = {}
        self.patch_payloads: list[dict] = []
        self.toggle_patch_payloads: list[dict] = []

    def _request(self, method: str, path: str, payload=None, query=None):
        if method == "GET" and path == "/pages/root-page":
            return {
                "object": "page",
                "id": "root-page",
                "properties": {
                    "title": {
                        "type": "title",
                        "title": [{"type": "text", "plain_text": "海淋", "text": {"content": "海淋"}}],
                    }
                },
            }
        if method == "GET" and path == "/blocks/root-page/children":
            results = [child_page("template-page", "模板")]
            if self.created:
                results.append(child_page("new-page", "Demo-abcd"))
            return {"results": results, "has_more": False}
        if method == "POST" and path == "/pages":
            self.create_payload = payload
            self.created = True
            return {"object": "page", "id": "new-page"}
        if method == "GET" and path == "/blocks/new-page/children":
            return {
                "results": [
                    heading("account-heading", "账号信息"),
                    code_block("account-code", self.code),
                    heading("update-heading", "更新信息"),
                    toggle("refund-toggle", "退款回调及p8"),
                    heading("config-heading", "配置信息"),
                ],
                "has_more": False,
            }
        if method == "GET" and path == "/blocks/refund-toggle/children":
            return {
                "results": [code_block("refund-code", self.toggle_code)],
                "has_more": False,
            }
        if method == "PATCH" and path == "/blocks/account-code":
            self.patch_payloads.append(payload)
            self.code = "".join(item["text"]["content"] for item in payload["code"]["rich_text"])
            return code_block("account-code", self.code)
        if method == "PATCH" and path == "/blocks/refund-code":
            self.toggle_patch_payloads.append(payload)
            self.toggle_code = "".join(
                item["text"]["content"] for item in payload["code"]["rich_text"]
            )
            return code_block("refund-code", self.toggle_code)
        raise AssertionError(f"unexpected request: {method} {path}")


def child_page(block_id: str, title: str) -> dict:
    return {"object": "block", "id": block_id, "type": "child_page", "child_page": {"title": title}}


def heading(block_id: str, text: str) -> dict:
    return {
        "object": "block",
        "id": block_id,
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "plain_text": text, "text": {"content": text}}]},
    }


def code_block(block_id: str, text: str) -> dict:
    return {
        "object": "block",
        "id": block_id,
        "type": "code",
        "code": {
            "language": "plain text",
            "caption": [],
            "rich_text": [{"type": "text", "plain_text": text, "text": {"content": text}}] if text else [],
        },
    }


def toggle(block_id: str, text: str) -> dict:
    return {
        "object": "block",
        "id": block_id,
        "type": "toggle",
        "has_children": True,
        "toggle": {"rich_text": [{"type": "text", "plain_text": text, "text": {"content": text}}]},
    }


def main() -> None:
    api = FakeNotionAPI()
    account = "用户名：\n\nAPP_ID：\n\n代码链接：" + "x" * 2100

    assert api.verify_parent("海淋") == "海淋"
    page_id = api.create_registration("Demo-abcd", account)

    assert page_id == "new-page"
    assert api.create_payload == {
        "parent": {"type": "page_id", "page_id": "root-page"},
        "properties": {"title": {"type": "title", "title": [{"type": "text", "text": {"content": "Demo-abcd"}}]}},
        "template": {"type": "template_id", "template_id": "template-page", "timezone": "Asia/Shanghai"},
    }
    assert api.code == account
    assert len(api.patch_payloads[0]["code"]["rich_text"]) == 2

    api.set_field("Demo-abcd", "账号信息", "APP_ID：", "123456")

    assert api.code == account.replace("APP_ID：", "APP_ID：123456", 1)

    refund = "issuer id: issuer\nkey id:key\np8文件内容：\n\n-----BEGIN PRIVATE KEY-----\n" + "x" * 2100
    assert api.read_toggle_code("Demo-abcd", "更新信息", "退款回调及p8") == ""
    assert api.write_toggle_code("Demo-abcd", "更新信息", "退款回调及p8", refund) is True
    assert api.read_toggle_code("Demo-abcd", "更新信息", "退款回调及p8") == refund
    assert len(api.toggle_patch_payloads[0]["code"]["rich_text"]) == 2
    assert api.write_toggle_code("Demo-abcd", "更新信息", "退款回调及p8", refund) is False
    assert len(api.toggle_patch_payloads) == 1

    try:
        api.write_toggle_code("Demo-abcd", "更新信息", "退款回调及p8", "different")
    except RuntimeError as error:
        assert "Refusing to replace non-empty Notion toggle" in str(error)
    else:
        raise AssertionError("non-empty toggle replacement should be refused")

    assert api.write_toggle_code(
        "Demo-abcd", "更新信息", "退款回调及p8", "different", replace_existing=True
    ) is True
    assert api.read_toggle_code("Demo-abcd", "更新信息", "退款回调及p8") == "different"


if __name__ == "__main__":
    main()
