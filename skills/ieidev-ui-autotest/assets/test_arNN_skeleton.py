"""
需求 AR-XXX-NN  <模块名>
覆盖用例 TC-XXX-NN-NNN ~ TC-XXX-NN-NNN

本模块覆盖：
- 基本流：<列出主要场景>
- 异常流：<列出主要场景>
- 备选流：<列出主要场景>

⚠ UI 差异（如有）：
- 测试用例文档说『xxx按钮』，实际 UI 为『yyy』
- TC-NNN 涉及的『zzz 区域』当前 UI 未提供，将 skip 并记录
"""
from __future__ import annotations

import time
import pytest

from pages.base_page import BasePage
# TODO: 改成你的业务 PageObject
from pages.example_page import ExampleListPage as _ListPage
from pages.example_page import ExampleFormPage as _FormPage
from utils.logger import get_logger, step
from utils.screenshot import capture
from tests._helpers import (
    assert_save_blocked,
    assert_field_truncated_to,       # 截断型异常流（合法 UX 截断后保存成功）
    assert_input_number_regulated,   # input-number 规整型异常流（blur 规整后保存成功）
)

# TODO: logger 名建议用模块号（arNN）
logger = get_logger("arNN")


# ============================================================
# 用例数据生成
# ============================================================
def unique_name(prefix: str = "AutoTest") -> str:
    """毫秒级时间戳后缀，同一秒连跑也不冲突。

    强烈建议**所有新增类用例**用本函数构造名称——配合 per-test cleanup
    可以做到"零脏数据残留"。
    """
    return f"{prefix}-{int(time.time() * 1000) % 10_000_000}"


def open_add_form(page) -> _FormPage:
    """快捷封装：列表 → 点击新增 → 返回表单 PageObject。"""
    lp = _ListPage(page, logger)
    lp.open()
    lp.click_new()
    return _FormPage(page, logger)


# ============================================================
#  TC-NNN  基本流：新增 + 列表断言（典型 happy path）
# ============================================================
@pytest.mark.arNN          # TODO: 改成你的模块标签
@pytest.mark.basic
@pytest.mark.p1
@pytest.mark.smoke         # 可选：标记为冒烟集
def test_tcNNN_add_full_fields(logged_page):
    """TC-NNN：新增并填写所有字段，保存成功，列表可见。"""
    logger.info("TC-NNN 开始")
    form = open_add_form(logged_page)
    name = unique_name("TCNNN")

    step(logger, 1, "基础信息 Tab：填名称、选下拉")
    form.tab_basic()
    form.fill_name(name)
    # 必填下拉随便选第一项；下拉空时 select_first_dropdown 会抛 TimeoutError
    try:
        form.select_first_dropdown("产品线")    # TODO: 改成你的下拉字段名
    except TimeoutError:
        pytest.skip("产品线下拉空，无法继续")

    step(logger, 2, "保存并断言成功")
    form.save()
    capture(logged_page, "TC-NNN", "saved")
    BasePage(logged_page, logger).assert_save_success("TC-NNN 创建")

    step(logger, 3, "回列表 → 按名称搜索 → 行可见")
    lp = _ListPage(logged_page, logger)
    lp.open()
    lp.search_by_name(name)
    lp.row_by_name(name).wait_for(state="visible", timeout=6000)


# ============================================================
#  TC-NNN  基本流：仅必填项
# ============================================================
@pytest.mark.arNN
@pytest.mark.basic
@pytest.mark.p1
def test_tcNNN_add_required_only(logged_page):
    """TC-NNN：仅填必填项，保存成功。"""
    form = open_add_form(logged_page)
    form.tab_basic()
    form.fill_name(unique_name("TCNNN"))
    try:
        form.select_first_dropdown("产品线")
    except TimeoutError:
        pytest.skip("产品线下拉空")
    form.save()
    BasePage(logged_page, logger).assert_save_success("TC-NNN 仅必填")


# ============================================================
#  TC-NNN  异常流：必填为空 → 字段错误
# ============================================================
@pytest.mark.arNN
@pytest.mark.exception
@pytest.mark.p1
def test_tcNNN_add_name_empty(logged_page):
    """TC-NNN：名称为空保存，应触发必填校验。"""
    form = open_add_form(logged_page)
    form.tab_basic()
    # 故意不填 name；其它必填可正常选择
    try:
        form.select_first_dropdown("产品线")
    except TimeoutError:
        pytest.skip("产品线下拉空")
    form.save()
    capture(logged_page, "TC-NNN", "name_empty")
    assert_save_blocked(logged_page, "名称", reason="名称为空应阻止保存")


# ============================================================
#  TC-NNN  异常流：超长输入 → 应被阻止
# ============================================================
@pytest.mark.arNN
@pytest.mark.exception
@pytest.mark.p2
def test_tcNNN_overview_overlong(logged_page):
    """TC-NNN：项目概述与目标超过 1000 字符应阻止保存。"""
    form = open_add_form(logged_page)
    form.tab_basic()
    form.fill_name(unique_name("TCNNN"))
    try:
        form.select_first_dropdown("产品线")
    except TimeoutError:
        pytest.skip("产品线下拉空")

    step(logger, 1, "故意填超长项目概述（1001 字符）")
    form.fill_overview("X" * 1001)              # TODO: 改成你的字段名

    step(logger, 2, "保存 → 断言被阻止")
    form.save()
    capture(logged_page, "TC-NNN", "overlong")
    assert_save_blocked(
        logged_page,
        "项目概述与目标",                         # TODO: 改成你的字段名
        reason="1001字符应阻止保存",
    )


# ============================================================
#  TC-NNN  异常流变体：maxlength 自动截断（合法 UX，保存应成功）
# ============================================================
#  ⚠ 写这类用例前先按 STANDARDS §6.3 跑 tools/probe_overlong.py
#    - actual_len == limit && maxlength == limit → 用本变体（截断后保存成功）
#    - actual_len == limit+1 && maxlength is None → 改用 assert_save_blocked
@pytest.mark.arNN
@pytest.mark.exception
@pytest.mark.p2
def test_tcNNN_overview_truncated_to_max(logged_page):
    """TC-NNN：项目概述 1001 字符前端自动截断到 1000，截断后保存成功。"""
    form = open_add_form(logged_page)
    form.tab_basic()
    form.fill_name(unique_name("TCNNN"))

    step(logger, 1, "故意填超长项目概述（1001 字符）")
    form.fill_overview("X" * 1001)               # TODO: 改成你的字段名

    step(logger, 2, "断言前端自动截断到 1000（合法 UX）")
    assert_field_truncated_to(
        logged_page, "项目概述与目标", 1000, type_hint="textarea",
    )

    step(logger, 3, "保存 → 截断后值合法应成功")
    form.save()
    BasePage(logged_page, logger).assert_save_success("TC-NNN 截断后保存")


# ============================================================
#  TC-NNN  异常流变体：input-number 规整（合法 UX，保存应成功）
# ============================================================
#  ⚠ 同上：先用 probe_overlong 实测 raw=-1 后 blur 是否被规整
@pytest.mark.arNN
@pytest.mark.exception
@pytest.mark.p2
def test_tcNNN_vuln_count_regulated(logged_page):
    """TC-NNN：新增漏洞数 -1 blur 规整为 0，规整后保存成功。"""
    form = open_add_form(logged_page)
    form.tab_basic()
    form.fill_name(unique_name("TCNNN"))

    step(logger, 1, "断言 -1 被 blur 规整为 0（合法 UX）")
    assert_input_number_regulated(
        logged_page, "新增漏洞数",                 # TODO: 改成你的字段名
        raw_input=-1, expected_after_blur=0,
    )

    step(logger, 2, "保存 → 规整后值合法应成功")
    form.save()
    BasePage(logged_page, logger).assert_save_success("TC-NNN 规整后保存")


# ============================================================
#  TC-NNN  备选流：编辑现有项 + 行内删除（取消确认 / 确认）
# ============================================================
@pytest.mark.arNN
@pytest.mark.alternative
@pytest.mark.p2
def test_tcNNN_edit_then_delete(logged_page):
    """TC-NNN：先新增一条，编辑其字段，再行内删除（先取消再确认）。"""
    # 准备数据
    form = open_add_form(logged_page)
    name = unique_name("TCNNN")
    form.tab_basic(); form.fill_name(name)
    try:
        form.select_first_dropdown("产品线")
    except TimeoutError:
        pytest.skip("产品线下拉空")
    form.save()
    BasePage(logged_page, logger).assert_save_success("TC-NNN 准备数据")

    # 编辑
    step(logger, 1, "回列表 → 行内编辑 → 改简称 → 保存")
    lp = _ListPage(logged_page, logger)
    lp.open()
    lp.search_by_name(name)
    lp.open_edit_by_name(name)
    form_edit = _FormPage(logged_page, logger)
    form_edit.fill_short_name(f"{name}_改")     # TODO: 改成你的字段方法名
    form_edit.save()
    BasePage(logged_page, logger).assert_save_success("TC-NNN 编辑保存")

    # 行内删除：先取消
    step(logger, 2, "行内删除 → 取消 → 行仍在")
    lp.open()
    lp.search_by_name(name)
    lp.delete_by_name(name, confirm=False)
    assert lp.row_by_name(name).count() == 1, "取消后行不应消失"

    # 行内删除：确认
    step(logger, 3, "行内删除 → 确认 → 行消失")
    lp.delete_by_name(name, confirm=True)
    BasePage(logged_page, logger).assert_save_success("TC-NNN 删除成功")
    assert lp.row_by_name(name).count() == 0, "确认后行应消失"


# ============================================================
#  TC-NNN  接口级用例（如有，否则删本块）
# ============================================================
# from utils.api import post, is_endpoint_alive
#
# ENDPOINT = "/api/your/endpoint"
#
# pytestmark = pytest.mark.skipif(
#     not is_endpoint_alive(ENDPOINT),
#     reason=f"接口 {ENDPOINT} 不可达"
# )
#
# @pytest.mark.arNN
# @pytest.mark.api
# @pytest.mark.p1
# def test_tcNNN_push_basic():
#     """TC-NNN：合法数据推送应返回 200。"""
#     r = post(ENDPOINT, json={"id": "v1", "name": "..."})
#     assert r.status_code == 200, f"接口失败 {r.status_code}: {r.text[:200]}"


# ============================================================
#  接入提醒（接入新模块时勾一遍）
# ============================================================
# - [ ] 文件名 test_arNN_<module>.py
# - [ ] 模块顶部 docstring 写明覆盖范围 + UI 差异
# - [ ] 函数名 test_tcNNN_<slug>，三位编号
# - [ ] 每条 docstring 第一行是用例标题
# - [ ] 至少 3 个标签（模块 + 流类型 + 优先级）
# - [ ] 异常流用 assert_save_blocked，不用裸 assert
# - [ ] 新增类用例名称用 unique_name(prefix)
# - [ ] UI 暂未提供 → pytest.skip，不用 assert
# - [ ] 关键步骤用 step(logger, N, ...)
# - [ ] tests/conftest.py 已为新资源类型 register_cleanup
# - [ ] 跑过 tools/recon_elements.py 对照字段名
