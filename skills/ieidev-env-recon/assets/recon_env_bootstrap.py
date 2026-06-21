"""
环境 / 菜单 / 弹窗实测前置 一键脚本（ieidev-env-recon skill 资产）

用途：登录目标系统、抓全菜单树、对每个目标页和"新增"弹窗做 UI 元素 dump，
      产出 recon/ 目录下的 4 件机器可读产物 + 截图，作为后续 menu_list.md
      （UI 文案权威源）和 PageObject 的源头。

用法：
  1. 复制本文件到测试项目根目录（或独立 recon/ 目录）
  2. 修改 ─── 配置区 ─── 部分（BASE_URL / USER / PWD / TARGET_PAGES）
  3. python3 recon_env_bootstrap.py
  4. 输出落到 ./recon/ 下
  5. Claude 读完 4 类 JSON 后按 ieidev-env-recon/references/menu-list-template.md 渲染 menu_list.md
  6.（可选）回写模式：把生成的 recon/ 与已有用例 .md 一起交给 Claude，按
     ieidev-env-recon/references/case-diff-patch.md 输出 case_diff.md + patches/

依赖：playwright（sync_api）。如未装：pip install playwright && playwright install chromium

约束：
  - 必须 headless（CI 与本地一致）
  - 不依赖任何项目模板文件，独立可跑
  - 字段名 / 按钮名 / 表头一切以本脚本输出为权威，不以 spec 为权威
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

# ─────────────────────────────────────── 配置区（按项目改） ───────────────────────────────────────
BASE_URL = "http://localhost:12580/"
USER = "admin"
PWD = "admin123"
CAPTCHA_FALLBACK = "1234"        # 验证码（如有）默认填值；开发环境通常任意 4 位通过
OUT_DIR = Path("./recon")
SHOTS_DIR = OUT_DIR / "screenshots"

# 目标页面列表（本测试范围要覆盖的子页面）— (短名, 路由, 是否要探弹窗)
TARGET_PAGES: list[tuple[str, str, bool]] = [
    # ("productline", "/pm/productline", True),
    # ("project",     "/pm/project",     True),
    # ("version",     "/pm/version",     True),
    # ("linkchg",     "/pm/linkChangeLog", False),
]

# 选择器策略（vfadmin / RuoYi / Element-Plus 通用；不通用时改这里）
SEL_USERNAME = 'input[placeholder*="账号"], input[placeholder*="用户"], input[name="username"]'
SEL_PASSWORD = 'input[type="password"], input[name="password"]'
SEL_CAPTCHA  = 'input[placeholder*="验证码"]'
SEL_LOGIN_BTN = 'button:has-text("登 录"), button:has-text("登录"), button[type="submit"]'
SEL_SIDEBAR_MENU = '.el-menu--vertical'    # 左侧 sidebar 根


# ─────────────────────────────────────── 工具函数 ───────────────────────────────────────
def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)


def dump_json(name: str, data) -> None:
    (OUT_DIR / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → wrote {OUT_DIR / name}")


def login(page: Page) -> None:
    print("[阶段 0] 登录")
    page.goto(BASE_URL, wait_until="networkidle")
    page.screenshot(path=str(SHOTS_DIR / "01_login.png"), full_page=True)
    page.fill(SEL_USERNAME, USER)
    page.fill(SEL_PASSWORD, PWD)
    cap = page.locator(SEL_CAPTCHA)
    if cap.count() > 0:
        cap.first.fill(CAPTCHA_FALLBACK)
    try:
        page.click(SEL_LOGIN_BTN, timeout=4000)
    except Exception:
        page.keyboard.press("Enter")
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_timeout(1500)
    page.screenshot(path=str(SHOTS_DIR / "02_landing.png"), full_page=True)
    print(f"  ✓ landed at {page.url}")


def expand_and_dump_menu(page: Page) -> dict | list:
    print("[阶段 1] 采集左菜单全树")
    # 多 pass 展开嵌套子菜单
    for _ in range(4):
        try:
            page.evaluate("""
                () => document.querySelectorAll('.el-sub-menu:not(.is-opened) > .el-sub-menu__title')
                     .forEach(el => el.click())
            """)
        except Exception:
            pass
        page.wait_for_timeout(500)
    page.screenshot(path=str(SHOTS_DIR / "03_menu_expanded.png"), full_page=True)
    tree = page.evaluate(r"""
        () => {
          function walk(node) {
            const items = [];
            const children = node.querySelectorAll(':scope > .el-sub-menu, :scope > .el-menu-item, :scope > div');
            children.forEach(child => {
              if (child.classList && child.classList.contains('el-sub-menu')) {
                const title = child.querySelector(':scope > .el-sub-menu__title');
                const sub   = child.querySelector(':scope > .el-menu');
                items.push({type:'submenu', title:(title?title.innerText.trim():''), children: sub?walk(sub):[]});
              } else if (child.classList && child.classList.contains('el-menu-item')) {
                const a = child.closest('a');
                items.push({type:'item', title: child.innerText.trim(), route:(a?a.getAttribute('href'):'')});
              } else {
                // wrapping div with router-link inside (RuoYi pattern)
                const a = child.querySelector(':scope > a');
                if (a) {
                  const li = a.querySelector('.el-menu-item');
                  if (li) {
                    items.push({type:'item', title: li.innerText.trim(), route: a.getAttribute('href') || ''});
                    return;
                  }
                }
                const inner = child.querySelector(':scope > .el-sub-menu');
                if (inner) {
                  const t = inner.querySelector(':scope > .el-sub-menu__title');
                  const s = inner.querySelector(':scope > .el-menu');
                  items.push({type:'submenu', title:(t?t.innerText.trim():''), children: s?walk(s):[]});
                }
              }
            });
            return items;
          }
          const root = document.querySelector('""" + SEL_SIDEBAR_MENU + r"""');
          return root ? walk(root) : {error:'no sidebar root, check SEL_SIDEBAR_MENU'};
        }
    """)
    dump_json("menu_tree.json", tree)
    # 兜底：把 sidebar outerHTML 也 dump 一份，方便 Claude 解析复杂场景
    try:
        sidebar_html = page.evaluate(f"() => {{ const r = document.querySelector('{SEL_SIDEBAR_MENU}'); return r ? r.outerHTML : ''; }}")
        (OUT_DIR / "sidebar.html").write_text(sidebar_html, encoding="utf-8")
    except Exception:
        pass
    return tree


def probe_page(page: Page, name: str, route: str) -> dict:
    print(f"[阶段 2] 探针页面 {name} ({route})")
    page.goto(BASE_URL.rstrip("/") + route, wait_until="networkidle")
    page.wait_for_timeout(2500)
    info = page.evaluate(r"""
        () => {
          const q = (sel) => Array.from(document.querySelectorAll(sel))
                                  .map(e => (e.innerText || e.getAttribute('placeholder') || '').trim())
                                  .filter(Boolean);
          return {
            url:           location.href,
            title:         document.title,
            breadcrumb:    q('.el-breadcrumb__inner'),
            formLabels:    q('.el-form-item__label'),
            placeholders:  Array.from(document.querySelectorAll('input[placeholder], textarea[placeholder]'))
                              .map(e => e.getAttribute('placeholder')).filter(Boolean),
            buttons:       q('button'),
            tableHeaders:  q('.el-table th .cell'),
            tabs:          q('.el-tabs__item'),
            dialogTitles:  q('.el-dialog__title, .el-drawer__title'),
            h1h2:          q('h1, h2, h3, .el-page-header__content')
          };
        }
    """)
    page.screenshot(path=str(SHOTS_DIR / f"pm_{name}.png"), full_page=True)
    dump_json(f"pages_{name}.json", info)
    return info


def probe_dialog(page: Page, name: str, route: str) -> dict | None:
    print(f"[阶段 3] 探针弹窗 {name} (新增按钮)")
    page.goto(BASE_URL.rstrip("/") + route, wait_until="networkidle")
    page.wait_for_timeout(2000)
    try:
        page.click('button:has-text("新增"):not([disabled])', timeout=5000)
        page.wait_for_timeout(1500)
    except Exception as e:
        print(f"  ⚠ 跳过 {name}：未找到可点击的新增按钮（{e}）")
        return None
    info = page.evaluate(r"""
        () => {
          const dlg = document.querySelector('.el-dialog:not([style*="display: none"]), .el-drawer__wrapper:not([style*="display: none"])');
          if (!dlg) return {error:'no open dialog detected'};
          const q = (sel) => Array.from(dlg.querySelectorAll(sel))
                                  .map(e => (e.innerText || e.getAttribute('placeholder') || '').trim())
                                  .filter(Boolean);
          return {
            title:          (dlg.querySelector('.el-dialog__title, .el-drawer__title') || {}).innerText || '',
            formLabels:     q('.el-form-item__label'),
            requiredFields: q('.is-required .el-form-item__label'),
            placeholders:   Array.from(dlg.querySelectorAll('input[placeholder], textarea[placeholder]'))
                              .map(e => e.getAttribute('placeholder')).filter(Boolean),
            buttons:        q('.el-dialog__footer button, .el-drawer__footer button')
          };
        }
    """)
    page.screenshot(path=str(SHOTS_DIR / f"dlg_{name}.png"), full_page=True)
    dump_json(f"dialogs_{name}.json", info)
    return info


# ─────────────────────────────────────── 主流程 ───────────────────────────────────────
def main() -> None:
    if not TARGET_PAGES:
        print("⚠ 未配置 TARGET_PAGES。请编辑本脚本顶部配置区。", file=sys.stderr)
        sys.exit(1)
    ensure_dirs()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = ctx.new_page()
        login(page)
        expand_and_dump_menu(page)
        for name, route, probe_dlg in TARGET_PAGES:
            probe_page(page, name, route)
            if probe_dlg:
                probe_dialog(page, name, route)
        browser.close()
    print("\n✅ 环境实测前置 完成。下一步：")
    print("   1. 读 recon/menu_tree.json + recon/pages_*.json + recon/dialogs_*.json")
    print("   2. 按 ieidev-env-recon/references/menu-list-template.md 渲染 recon/menu_list.md")
    print("   3. 比对 spec 与 menu_list.md §6 差异表，更新测试用例文档头部 + 修正按钮 / 弹窗 / 列名")
    print("   4.（可选）回写模式：把生成的 recon/ 与已有用例 .md 一起交给 Claude，按")
    print("      ieidev-env-recon/references/case-diff-patch.md 输出 case_diff.md + patches/")
    print("   5.（可选）如要继续写 Playwright 脚本 → 切换到 ieidev-team:ieidev-ui-autotest skill 走 STEP 1+")


if __name__ == "__main__":
    main()
