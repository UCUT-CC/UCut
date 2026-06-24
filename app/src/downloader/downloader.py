import os
import re
import time
import threading
import yt_dlp

from app.src.downloader.platforms import detect_platform, get_platform_name, get_format_options


class DownloadError(Exception):
    pass


class DownloadCancelled(Exception):
    pass


_cancel_flag = threading.Event()


def cancel_current_download():
    _cancel_flag.set()


def reset_cancel():
    _cancel_flag.clear()


def is_cancelled():
    return _cancel_flag.is_set()


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def find_downloaded_file(output_dir: str, video_id: str) -> str:
    candidates = []
    for f in os.listdir(output_dir):
        if f.startswith(video_id) and not f.endswith(".part"):
            filepath = os.path.join(output_dir, f)
            if os.path.isfile(filepath):
                candidates.append(filepath)
    if candidates:
        return max(candidates, key=os.path.getsize)
    for f in os.listdir(output_dir):
        if not f.endswith(".part") and not os.path.isdir(os.path.join(output_dir, f)):
            filepath = os.path.join(output_dir, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in (".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".mp3", ".wav", ".m4a", ".aac"):
                return filepath
    return None


def _get_ffmpeg_path():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _get_platform_headers(detected: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if detected == "bilibili":
        headers["Origin"] = "https://www.bilibili.com"
        headers["Referer"] = "https://www.bilibili.com/"
    return headers


def download_video(
    url: str,
    output_dir: str,
    platform: str = "auto",
    format_key: int = 0,
    cookies_browser: str = None,
    cookiefile: str = None,
    progress_callback=None,
    status_callback=None,
):
    reset_cancel()
    detected = detect_platform(url)
    fmt_opts = get_format_options()
    if format_key >= len(fmt_opts):
        format_key = 0
    fmt = fmt_opts[format_key]["format"]

    def progress_hook(d):
        if is_cancelled():
            raise DownloadCancelled("用户取消下载")
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed", 0)
            if speed:
                speed_str = f"{speed / 1024 / 1024:.1f}MB/s"
            else:
                speed_str = ""
            if total > 0:
                pct = downloaded / total * 100
                if status_callback:
                    status_callback(f"下载中... {pct:.1f}% ({speed_str})")
            if progress_callback and total > 0:
                progress_callback(downloaded / total)
        elif d["status"] == "finished":
            if status_callback:
                status_callback("下载完成，正在处理...")
            if progress_callback:
                progress_callback(1.0)

    video_id = f"tailor_dl_{int(time.time())}"
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")

    ydl_opts = {
        "format": fmt,
        "outtmpl": output_template,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "ignoreerrors": False,
        "noplaylist": True,
        "socket_timeout": 15,
        "nocheckcertificate": True,
        "http_headers": _get_platform_headers(detected),
    }

    ffmpeg_path = _get_ffmpeg_path()
    if ffmpeg_path:
        ydl_opts["ffmpeg_location"] = ffmpeg_path

    if detected == "douyin":
        try:
            import curl_cffi
            from yt_dlp.networking.impersonate import ImpersonateTarget
            ydl_opts["impersonate"] = ImpersonateTarget(client="chrome", version="131")
        except ImportError:
            pass

    if cookies_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_browser,)
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    if format_key == 4:
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }]

    try:
        if status_callback:
            status_callback(f"正在连接 {get_platform_name(detected)}...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if is_cancelled():
                raise DownloadCancelled("用户取消下载")

            if status_callback:
                status_callback("正在获取视频信息...")

            info = ydl.extract_info(url, download=True)

            if info is None:
                raise DownloadError("无法获取视频信息，链接可能无效")

            title = info.get("title", "video")
            extracted_id = info.get("id", video_id)

        if is_cancelled():
            raise DownloadCancelled("用户取消下载")

        if status_callback:
            status_callback(f"下载完成: {title}")

        found = find_downloaded_file(output_dir, video_id)
        if not found:
            found = find_downloaded_file(output_dir, extracted_id)

        if not found:
            raise DownloadError("无法找到下载的文件")

        safe_title = sanitize_filename(title)
        ext = os.path.splitext(found)[1]
        new_name = f"{safe_title}{ext}"
        new_path = os.path.join(output_dir, new_name)

        if found != new_path:
            if os.path.exists(new_path):
                base = safe_title
                idx = 1
                while os.path.exists(os.path.join(output_dir, f"{base}_{idx}{ext}")):
                    idx += 1
                new_name = f"{base}_{idx}{ext}"
                new_path = os.path.join(output_dir, new_name)
            os.rename(found, new_path)

        temp_pattern = re.compile(rf"^{re.escape(video_id)}\..+\.part$")
        for f in os.listdir(output_dir):
            if temp_pattern.match(f) or f.endswith(".part"):
                try:
                    os.remove(os.path.join(output_dir, f))
                except:
                    pass

        if status_callback:
            status_callback(f"视频已保存: {new_name}")
        return new_path

    except DownloadCancelled:
        raise
    except DownloadError:
        raise
    except Exception as e:
        err_str = str(e)
        if "HTTP Error" in err_str:
            raise DownloadError(f"服务器返回错误，链接可能已失效或被屏蔽")
        if "Connection" in err_str or "timeout" in err_str.lower():
            raise DownloadError("网络连接超时，请检查网络或使用代理")
        if "Video unavailable" in err_str:
            raise DownloadError("该视频不可访问（可能已删除或需要登录）")
        if "cookies" in err_str.lower() or "cookie" in err_str.lower():
            if "could not find" in err_str.lower() or "could not copy" in err_str.lower():
                raise DownloadError('无法读取浏览器 Cookies。请先关闭浏览器再试，或选择【手动粘贴 Cookies】方式')
            if "fresh cookies" in err_str.lower():
                raise DownloadError(
                    "抖音 API 需要额外的验证（反爬保护）。已提取到您的登录 Cookie，但抖音要求客户端生成签名。\n"
                    "请尝试以下方法：\n"
                    "1. 在浏览器中打开视频，手动下载（或使用手机分享）\n"
                    "2. 尝试其他平台（B站/快手等）的链接\n"
                    "3. 使用抖音电脑客户端下载\n"
                    "4. 您可以在浏览器中播放视频，右键另存为"
                )
            raise DownloadError(f"Cookies 错误: {err_str[:150]}")
        if "sign in" in err_str.lower() or "login" in err_str.lower():
            raise DownloadError("需要登录，请确保已启用 Cookies 并登录抖音")
        raise DownloadError(f"下载失败: {err_str[:100]}")
