#!/usr/bin/env python3
"""独立处理 macOS “Enter Mac Password” 弹窗。"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any, List, Optional

from find_system_settings_general import (
    AX,
    LOGIN_CONTINUE_TEXT,
    OPERATION_TIMEOUT_SECONDS,
    TEXT_FIELD_ROLES,
    WORKFLOW_RENDER_ATTEMPTS,
    WORKFLOW_RENDER_INTERVAL_SECONDS,
    activate,
    copy_attribute,
    current_search_roots,
    describe_element,
    element_contains_text,
    find_enabled_pressable_text_candidate,
    get_running_system_settings,
    launch_system_settings,
    set_login_field,
    tree_contains_text,
)


MAC_PASSWORD_PROMPT_TEXT = "Enter Mac Password"
MAC_PASSWORD_VALUE = "1234"


def find_mac_password_field(roots: List[Any]) -> Optional[Any]:
    """查找安全弹窗中的密码框，排除背景搜索框和禁用控件。"""
    fallback: Optional[Any] = None
    unique_candidates: List[Any] = []
    for element, _ in _iter_tree(roots):
        info = describe_element(element)
        if info["role"] not in TEXT_FIELD_ROLES:
            continue
        if info["enabled"] is False or info["subrole"] == "AXSearchField":
            continue
        unique_candidates.append(element)
        if info["role"] == "AXSecureTextField":
            return element
        if element_contains_text(info, "Password"):
            fallback = element
    if fallback is not None:
        return fallback
    if len(unique_candidates) == 1:
        return unique_candidates[0]
    return None


def _iter_tree(roots: List[Any]):
    """通过通用 AX 遍历器读取当前弹窗的控件。"""
    from find_system_settings_general import iter_accessibility_tree

    return iter_accessibility_tree(roots)


def handle_mac_password_prompt(pid: int) -> Optional[int]:
    """若弹窗存在则输入 1234 并点击该弹窗的 Continue。"""
    roots = current_search_roots(pid, auto_handle_mac_password=False)
    if not tree_contains_text(roots, MAC_PASSWORD_PROMPT_TEXT):
        return None

    password_field = find_mac_password_field(roots)
    if password_field is None:
        print("检测到 Enter Mac Password，但未找到密码输入框。", file=sys.stderr)
        return 5
    password_error = set_login_field(password_field, MAC_PASSWORD_VALUE)
    if password_error != AX.kAXErrorSuccess:
        print("写入 Mac 密码失败，AXError={}".format(password_error), file=sys.stderr)
        return 4

    continue_candidate = None
    for attempt in range(WORKFLOW_RENDER_ATTEMPTS):
        continue_candidate = find_enabled_pressable_text_candidate(
            current_search_roots(pid), LOGIN_CONTINUE_TEXT
        )
        if continue_candidate is not None:
            break
        if attempt < WORKFLOW_RENDER_ATTEMPTS - 1:
            time.sleep(WORKFLOW_RENDER_INTERVAL_SECONDS)
    if continue_candidate is None:
        print(
            "Enter Mac Password 弹窗未找到可用的 Continue 按钮（超时：{}秒）。".format(
                OPERATION_TIMEOUT_SECONDS
            ),
            file=sys.stderr,
        )
        return 5
    error = activate(continue_candidate)
    if error != AX.kAXErrorSuccess:
        print("提交 Mac 密码失败，AXError={}".format(error), file=sys.stderr)
        return 4
    print("已自动填写 Mac 密码并点击 Continue。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Handle Enter Mac Password")
    parser.parse_args()
    trusted = AX.AXIsProcessTrustedWithOptions(
        {AX.kAXTrustedCheckOptionPrompt: True}
    )
    if not trusted:
        print("当前进程没有辅助功能权限。", file=sys.stderr)
        return 1
    launch_system_settings()
    time.sleep(2)
    pid = get_running_system_settings().processIdentifier()
    result = handle_mac_password_prompt(pid)
    if result is None:
        print("当前没有检测到 Enter Mac Password 弹窗。", file=sys.stderr)
        return 5
    return result


if __name__ == "__main__":
    raise SystemExit(main())
