import os
import tempfile
import threading
import subprocess
from typing import Optional, Union, Tuple

import customtkinter
from customtkinter import CTkToplevel, CTkLabel, CTkEntry, CTkButton, CTkOptionMenu, CTkProgressBar, CTkFont, CTkCheckBox, CTkRadioButton, CTkTextbox

from app.utils.paths import Paths
from app.src.downloader.downloader import (
    download_video, cancel_current_download,
    DownloadError, DownloadCancelled,
)
from app.src.downloader.platforms import PLATFORMS, detect_platform, get_platform_name
from app.src.downloader.cookie_helper import get_saved_cookie_path, get_cookie_count


class DownloadDialog(CTkToplevel):
    def __init__(
        self,
        master,
        fg_color: Optional[Union[str, Tuple[str, str]]] = None,
        bitmap_path: str = None,
        download_dir: str = None,
        tr: callable = None,
    ):
        super().__init__(fg_color=fg_color)
        self.master = master
        self._tr = tr or (lambda s: s)
        self._download_dir = download_dir or os.path.join(Paths.WORKPLACE, "downloads")
        self._result_path = None
        self._success = False
        self._is_downloading = False
        self._cookiefile_path = None
        self._cookie_method = customtkinter.StringVar(
            value="saved" if get_saved_cookie_path() else "extract"
        )
        os.makedirs(self._download_dir, exist_ok=True)

        self.title(self._tr("Import Video from Web"))
        self.geometry("600x620")
        self.minsize(540, 560)
        self.lift()
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        if bitmap_path and os.path.exists(bitmap_path) and bitmap_path.endswith(".ico"):
            self.after(200, lambda: self.iconbitmap(bitmap=bitmap_path))
        self.transient(self.master)
        self.resizable(True, True)
        self._create_widgets()
        self.grab_set()

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        row = 0
        CTkLabel(self, text=self._tr("Import Video from Web"), font=CTkFont(size=18, weight="bold"))\
            .grid(row=row, column=0, columnspan=3, padx=25, pady=(25, 15))
        row += 1

        url_frame = customtkinter.CTkFrame(self, fg_color="transparent", border_width=1)
        url_frame.grid(row=row, column=0, columnspan=3, padx=25, pady=(0, 10), sticky="ew")
        url_frame.grid_columnconfigure(0, weight=1)
        self._url_entry = CTkEntry(
            url_frame, placeholder_text=self._tr("Paste video link (Douyin / Bilibili / YouTube / etc.)"),
            height=40, font=CTkFont(size=13)
        )
        self._url_entry.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self._url_entry.focus()
        self._url_entry.bind("<KeyRelease>", self._on_url_change)
        self._url_entry.bind("<Return>", lambda e: self._start_download())
        row += 1

        opt_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        opt_frame.grid(row=row, column=0, columnspan=3, padx=25, pady=(4, 8), sticky="ew")
        opt_frame.grid_columnconfigure(0, weight=1)
        opt_frame.grid_columnconfigure(2, weight=1)

        CTkLabel(opt_frame, text=self._tr("Platform:"), font=CTkFont(size=13))\
            .grid(row=0, column=0, padx=(0, 5), pady=4, sticky="w")
        platform_values = [self._tr("Auto Detect")] + [p["name"] for p in list(PLATFORMS.values())[1:]]
        self._platform_menu = CTkOptionMenu(opt_frame, values=platform_values, width=140, height=32)
        self._platform_menu.set(platform_values[0])
        self._platform_menu.grid(row=0, column=1, padx=(0, 20), pady=4, sticky="w")

        CTkLabel(opt_frame, text=self._tr("Quality:"), font=CTkFont(size=13))\
            .grid(row=0, column=2, padx=(0, 5), pady=4, sticky="w")
        quality_values = [
            self._tr("Best Quality (Recommended)"),
            self._tr("HD 1080p"),
            self._tr("HD 720p"),
            self._tr("SD 480p"),
            self._tr("Audio Only MP3"),
        ]
        self._quality_menu = CTkOptionMenu(opt_frame, values=quality_values, width=140, height=32)
        self._quality_menu.set(quality_values[0])
        self._quality_menu.grid(row=0, column=3, padx=(0, 0), pady=4, sticky="w")
        row += 1

        cookie_frame = customtkinter.CTkFrame(self, fg_color="transparent", border_width=1)
        cookie_frame.grid(row=row, column=0, columnspan=3, padx=25, pady=(4, 8), sticky="ew")
        cookie_frame.grid_columnconfigure(1, weight=1)

        self._cookie_var = customtkinter.BooleanVar(value=True)
        self._cookie_check = CTkCheckBox(
            cookie_frame, text=self._tr("Enable Cookies (check when logged in)"),
            variable=self._cookie_var, font=CTkFont(size=12),
            command=self._on_cookie_toggle
        )
        self._cookie_check.grid(row=0, column=0, columnspan=3, padx=12, pady=(8, 2), sticky="w")

        method_frame = customtkinter.CTkFrame(cookie_frame, fg_color="transparent")
        method_frame.grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 4), sticky="ew")
        method_frame.grid_columnconfigure(1, weight=1)

        self._saved_radio = CTkRadioButton(
            method_frame, text=self._tr("Use saved cookies"),
            variable=self._cookie_method, value="saved",
            font=CTkFont(size=12), command=self._on_cookie_method_change
        )
        self._saved_radio.grid(row=0, column=0, padx=(0, 8), pady=2, sticky="w")
        saved_path = get_saved_cookie_path()
        if saved_path:
            with open(saved_path, encoding="utf-8") as f:
                count = sum(1 for l in f if l.strip() and not l.startswith("#"))
            CTkLabel(method_frame, text=f"({count} {self._tr('records')})",
                     font=CTkFont(size=10), text_color=("gray50", "gray50"))\
                .grid(row=0, column=1, padx=(0, 0), pady=2, sticky="w")

        self._extract_radio = CTkRadioButton(
            method_frame, text=self._tr("Extract from browser"),
            variable=self._cookie_method, value="extract",
            font=CTkFont(size=12), command=self._on_cookie_method_change
        )
        self._extract_radio.grid(row=1, column=0, padx=(0, 8), pady=2, sticky="w")

        browser_frame = customtkinter.CTkFrame(method_frame, fg_color="transparent")
        browser_frame.grid(row=1, column=1, columnspan=2, padx=(0, 0), pady=2, sticky="w")

        self._browser_menu = CTkOptionMenu(
            browser_frame, values=["Edge", "Chrome", "Firefox", "Brave", "Opera"],
            width=100, height=26, font=CTkFont(size=12)
        )
        self._browser_menu.set("Edge")
        self._browser_menu.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="w")

        CTkLabel(browser_frame, text=self._tr("(close browser before extracting)"),
                 font=CTkFont(size=10), text_color=("orange", "orange"))\
            .grid(row=0, column=1, padx=(0, 0), pady=0, sticky="w")

        self._manual_radio = CTkRadioButton(
            cookie_frame, text=self._tr("Paste cookies manually"),
            variable=self._cookie_method, value="manual",
            font=CTkFont(size=12), command=self._on_cookie_method_change
        )
        self._manual_radio.grid(row=3, column=0, padx=12, pady=(4, 0), sticky="w")

        manual_hint = CTkLabel(
            cookie_frame,
            text=self._tr("Install Get cookies.txt extension\n"
                          "Log in to the site -> click extension -> check Include HttpOnly -> Export -> Copy all and paste below"),
            font=CTkFont(size=10), text_color=("gray50", "gray50"), justify="left", anchor="w"
        )
        manual_hint.grid(row=4, column=0, columnspan=3, padx=12, pady=(2, 0), sticky="w")

        self._cookie_text = CTkTextbox(
            cookie_frame, height=100, font=CTkFont(size=11),
            border_width=1, wrap="none"
        )
        self._cookie_text.grid(row=5, column=0, columnspan=3, padx=12, pady=(4, 8), sticky="ew")
        self._cookie_text.insert("0.0", "# " + self._tr("Paste cookies here (Ctrl+V)") + "\n")

        extract_btn_frame = customtkinter.CTkFrame(cookie_frame, fg_color="transparent")
        extract_btn_frame.grid(row=6, column=0, columnspan=3, padx=12, pady=(0, 8), sticky="w")

        self._extract_btn = CTkButton(
            extract_btn_frame, text=self._tr("⚡ Extract Cookies from Browser (run as admin)"),
            height=28, font=CTkFont(size=11),
            fg_color="#5B8DEE", hover_color="#4A7AD8",
            command=self._run_cookie_extraction
        )
        self._extract_btn.grid(row=0, column=0, padx=0, pady=0, sticky="w")
        row += 1

        self._status_label = CTkLabel(
            self, text="", anchor="w", wraplength=540, font=CTkFont(size=12),
            text_color=("gray30", "gray70")
        )
        self._status_label.grid(row=row, column=0, columnspan=3, padx=25, pady=(4, 2), sticky="ew")
        row += 1

        self._progress_bar = CTkProgressBar(self, height=18, corner_radius=4)
        self._progress_bar.grid(row=row, column=0, columnspan=3, padx=25, pady=(0, 12), sticky="ew")
        self._progress_bar.set(0)
        row += 1

        self._direct_open_var = customtkinter.BooleanVar(value=False)
        open_check = CTkCheckBox(
            self, text=self._tr("Open video directly after download (no project)"),
            variable=self._direct_open_var,
            font=CTkFont(size=12), command=self._on_direct_open_toggle
        )
        open_check.grid(row=row, column=0, columnspan=3, padx=25, pady=(0, 4), sticky="w")
        row += 1

        btn_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=3, padx=25, pady=(4, 20), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        self._download_btn = CTkButton(
            btn_frame, text=self._tr("Download & Import ▸"), height=38,
            command=self._start_download, fg_color="#3B8ED0", hover_color="#36719F",
            font=CTkFont(size=14)
        )
        self._download_btn.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self._cancel_btn = CTkButton(
            btn_frame, text=self._tr("Cancel"), height=38,
            command=self._on_closing, fg_color="gray60", hover_color="gray45",
            font=CTkFont(size=14)
        )
        self._cancel_btn.grid(row=0, column=1, padx=(8, 0), sticky="ew")

        self._apply_cookie_widgets_state(self._cookie_var.get())

    def _on_direct_open_toggle(self):
        if self._direct_open_var.get():
            self._download_btn.configure(text=self._tr("Direct Download & Open ▸"))
        else:
            self._download_btn.configure(text=self._tr("Download & Import ▸"))

    def _on_cookie_toggle(self):
        self._apply_cookie_widgets_state(self._cookie_var.get())

    def _on_cookie_method_change(self):
        self._apply_cookie_widgets_state(self._cookie_var.get())

    def _apply_cookie_widgets_state(self, enabled):
        method = self._cookie_method.get()
        self._extract_radio.configure(state="normal" if enabled else "disabled")
        self._manual_radio.configure(state="normal" if enabled else "disabled")
        self._saved_radio.configure(state="normal" if enabled else "disabled")
        self._browser_menu.configure(state="normal" if enabled and method == "extract" else "disabled")
        self._cookie_text.configure(state="normal" if enabled and method == "manual" else "disabled")
        self._extract_btn.configure(state="normal" if enabled else "disabled")

    def _platform_key_from_menu(self) -> str:
        selected = self._platform_menu.get()
        for key, info in PLATFORMS.items():
            if info["name"] == selected:
                return key
        if selected == self._tr("Auto Detect"):
            return "auto"
        return "auto"

    def _get_cookiefile_path(self) -> Optional[str]:
        if not self._cookie_var.get():
            return None
        method = self._cookie_method.get()
        if method == "saved":
            path = get_saved_cookie_path()
            if not path:
                self._set_status(self._tr("No saved cookies found. Extract or paste manually."))
                return None
            return path
        if method == "extract":
            return None
        raw = self._cookie_text.get("0.0", "end").strip()
        non_comment_lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
        if len(non_comment_lines) < 1:
            self._set_status(self._tr("Please paste valid cookies (at least one non-comment line)."))
            return None
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="cookies_")
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(raw)
        self._cookiefile_path = path
        return path

    def _cleanup_cookiefile(self):
        if self._cookiefile_path and os.path.exists(self._cookiefile_path):
            try:
                os.remove(self._cookiefile_path)
            except OSError:
                pass
            self._cookiefile_path = None

    def _run_cookie_extraction(self):
        helper = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                              "src", "downloader", "cookie_helper.py")
        self._set_status(self._tr("Extracting Edge cookies as administrator..."))
        threading.Thread(target=self._do_extract, args=(helper,), daemon=True).start()

    def _do_extract(self, helper_path):
        try:
            ps_cmd = f'Start-Process -Verb RunAs -FilePath "python" -ArgumentList @("{helper_path}") -Wait'
            subprocess.run(["powershell", "-Command", ps_cmd], check=True, timeout=60)
            self.after(0, self._check_extract_result)
        except subprocess.TimeoutExpired:
            self.after(0, lambda: self._set_status(self._tr("Extraction timed out")))
        except Exception as e:
            self.after(0, lambda: self._set_status(f"{self._tr('Extraction failed')}: {str(e)[:60]}"))

    def _check_extract_result(self):
        if get_saved_cookie_path():
            self._set_status(self._tr("Cookies extracted! Click Download to use them."))
            self._refresh_saved_cookie_ui()
        else:
            self._set_status(self._tr("No Douyin cookies found. Make sure you are logged in Edge."))

    def _refresh_saved_cookie_ui(self):
        self._cookie_method.set("saved")
        self._apply_cookie_widgets_state(True)

    def _on_url_change(self, event=None):
        url = self._url_entry.get().strip()
        if url:
            detected = detect_platform(url)
            if detected == "auto" or detected == "other":
                self._platform_menu.set(self._tr("Auto Detect"))
            else:
                self._platform_menu.set(PLATFORMS[detected]["name"])

    def _set_status(self, text):
        self.after(0, lambda: self._status_label.configure(text=text))

    def _set_progress(self, value):
        self.after(0, lambda: self._progress_bar.set(value))

    def _set_buttons(self, downloading: bool):
        self._is_downloading = downloading
        if downloading:
            self._download_btn.configure(state="disabled", text=self._tr("Downloading..."))
            self._cancel_btn.configure(text=self._tr("Cancel Download"), command=self._cancel_download)
            self._heartbeat_count = 0
            self._heartbeat()
        else:
            self._download_btn.configure(state="normal", text=self._tr("Download & Import ▸"))
            self._cancel_btn.configure(text=self._tr("Cancel"), command=self._on_closing)

    def _heartbeat(self):
        if not self._is_downloading:
            return
        current = self._status_label.cget("text")
        waiting = self._tr("Getting video info...")
        waited = self._tr("waited")
        if current in (waiting, "") or waited in current:
            self._heartbeat_count += 1
            self._status_label.configure(
                text=f"{waiting} ({waited} {self._heartbeat_count * 3}s)"
            )
        self.after(3000, self._heartbeat)

    def _cancel_download(self):
        self._set_status(self._tr("Cancelling download..."))
        cancel_current_download()
        self._set_buttons(False)
        self._set_progress(0)

    def _start_download(self):
        url = self._url_entry.get().strip()
        if not url:
            self._set_status(self._tr("Please paste a video link first!"))
            return

        platform_key = self._platform_key_from_menu()
        if platform_key == "auto":
            platform_key = detect_platform(url)

        quality_labels = [
            self._tr("Best Quality (Recommended)"),
            self._tr("HD 1080p"),
            self._tr("HD 720p"),
            self._tr("SD 480p"),
            self._tr("Audio Only MP3"),
        ]
        quality_map = {lbl: i for i, lbl in enumerate(quality_labels)}
        quality_key = quality_map.get(self._quality_menu.get(), 0)

        cookies_browser = None
        cookiefile = None
        if self._cookie_var.get():
            method = self._cookie_method.get()
            if method == "extract":
                cookies_browser = self._browser_menu.get().lower()
            else:
                cookiefile = self._get_cookiefile_path()
                if cookiefile is None:
                    return

        self._set_buttons(True)
        self._set_status(self._tr("Preparing..."))
        self._set_progress(0)

        def run_download():
            try:
                filepath = download_video(
                    url=url,
                    output_dir=self._download_dir,
                    platform=platform_key,
                    format_key=quality_key,
                    cookies_browser=cookies_browser,
                    cookiefile=cookiefile,
                    progress_callback=lambda r: self._set_progress(r),
                    status_callback=lambda t: self._set_status(t),
                )
                self._result_path = filepath
                self._success = True
                self.after(0, self._on_download_complete)
            except DownloadCancelled:
                self.after(0, lambda: self._set_status(self._tr("Download cancelled")))
                self.after(0, lambda: self._set_buttons(False))
            except DownloadError as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._on_download_error(m))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._on_download_error(m))

        thread = threading.Thread(target=run_download, daemon=True)
        thread.start()

    def _on_download_complete(self):
        filepath = self._result_path
        if self._direct_open_var.get():
            self._set_status(self._tr("Download successful! Opening..."))
            self._cleanup_cookiefile()
            self.after(400, lambda: (self.grab_release(), self.destroy()))
            return
        self._set_status(self._tr("Download successful! Importing..."))
        self._success = True
        self._cleanup_cookiefile()
        self.grab_release()
        self.destroy()

    def _on_download_error(self, msg):
        self._set_status(f"{self._tr('Failed')}: {msg}")
        self._set_buttons(False)
        self._set_progress(0)
        self._cleanup_cookiefile()
        if any(kw in msg for kw in ["Douyin", "抖音", self._tr("anti-crawl")]):
            self._set_status(msg + "\n\n" + self._tr("Tip: Close this window and use 'Import Local File' to open the downloaded video."))

    def _on_closing(self):
        if self._is_downloading:
            cancel_current_download()
        self._cleanup_cookiefile()
        self._success = False
        self.grab_release()
        self.destroy()

    def get_result(self):
        self.master.wait_window(self)
        return self._result_path if self._success else None

    def is_direct_open(self):
        return self._direct_open_var.get()
