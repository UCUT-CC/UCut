import re

PLATFORMS = {
    "auto": {"name": "自动检测", "regex": None},
    "douyin": {"name": "抖音", "regex": r"(douyin\.com|iesdouyin\.com)"},
    "xiaohongshu": {"name": "小红书", "regex": r"(xiaohongshu\.com|xhslink\.com)"},
    "wechat": {"name": "微信视频号", "regex": r"(weixin\.qq\.com)"},
    "haokan": {"name": "好看视频", "regex": r"(haokan\.baidu\.com)"},
    "bilibili": {"name": "B站", "regex": r"(bilibili\.com|b23\.tv)"},
    "kuaishou": {"name": "快手", "regex": r"(kuaishou\.com)"},
}

def detect_platform(url: str) -> str:
    for key, info in PLATFORMS.items():
        if key == "auto":
            continue
        if info["regex"] and re.search(info["regex"], url, re.IGNORECASE):
            return key
    return "other"

def get_platform_name(key: str) -> str:
    info = PLATFORMS.get(key)
    return info["name"] if info else "其他"

def get_format_options():
    return [
        {"label": "最佳质量（推荐）", "format": "bestvideo+bestaudio/best"},
        {"label": "高清 1080p", "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]"},
        {"label": "高清 720p", "format": "bestvideo[height<=720]+bestaudio/best[height<=720]"},
        {"label": "标清 480p", "format": "bestvideo[height<=480]+bestaudio/best[height<=480]"},
        {"label": "仅音频 MP3", "format": "bestaudio/best"},
    ]
