import os
import sys

COOKIE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "workplace", "saved_cookies.txt"
)
TARGET_DOMAINS = ("douyin", "xiaohongshu", "bilibili", "kuaishou", "iesdouyin", "weixin")


def _extract_from_browser(loader, domain_filter=None):
    try:
        cj = loader()
        if domain_filter:
            return [c for c in cj if any(d in c.domain for d in domain_filter)]
        return list(cj)
    except Exception:
        return []


def try_extract_cookies():
    try:
        import browser_cookie3
    except ImportError:
        return None

    all_cookies = []
    all_cookies.extend(_extract_from_browser(browser_cookie3.chrome, TARGET_DOMAINS))
    all_cookies.extend(_extract_from_browser(browser_cookie3.edge, TARGET_DOMAINS))

    if not all_cookies:
        return None

    seen = set()
    os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
    with open(COOKIE_FILE, "w", encoding="utf-8", newline="") as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# Auto-extracted by UCut\n")
        for c in all_cookies:
            key = (c.domain, c.name, c.path)
            if key in seen:
                continue
            seen.add(key)
            if not c.name:
                continue
            domain_flag = "TRUE" if c.domain.startswith('.') else "FALSE"
            secure = "TRUE" if c.secure else "FALSE"
            expires = str(int(c.expires)) if c.expires else "0"
            f.write(f"{c.domain}\t{domain_flag}\t{c.path or '/'}\t{secure}\t{expires}\t{c.name}\t{c.value}\n")

    return COOKIE_FILE


def get_saved_cookie_path() -> str:
    if os.path.exists(COOKIE_FILE):
        return COOKIE_FILE
    return None


def get_cookie_count() -> int:
    path = get_saved_cookie_path()
    if not path:
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for l in f if l.strip() and not l.startswith("#"))


if __name__ == "__main__":
    print("正在从 Chrome/Edge 浏览器提取 cookies...")
    path = try_extract_cookies()
    if path:
        cnt = get_cookie_count()
        print(f"提取成功！共 {cnt} 条 cookie 记录")
        print(f"保存到：{path}")
    else:
        print("提取失败。请确保：")
        print("1. 已在 Chrome 或 Edge 中登录抖音")
        print("2. 以管理员身份运行此脚本")
        print("或者手动安装 Get cookies.txt 扩展导出 cookies")
        sys.exit(1)
