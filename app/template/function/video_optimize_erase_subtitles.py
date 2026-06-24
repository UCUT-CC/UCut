import os
import copy
import shutil
import threading

from tqdm import tqdm
from PIL import Image

from moviepy.editor import VideoFileClip
from customtkinter import CTkButton, CTkScrollableFrame, CTkLabel, CTkProgressBar, CTkFont

from app.tailorwidgets.tailor_modal import TLRModal
from app.tailorwidgets.tailor_message_box import TLRMessageBox
from app.tailorwidgets.tailor_line_dialog import TLRLineDialog
from app.tailorwidgets.default.filetypes import VIDEO_EXTENSION

from app.utils.paths import Paths
from app.src.utils.timer import Timer
from app.config.config import Config
from app.src.utils.logger import Logger

from app.src.algorithm.video_optimize_erase_subtitles.video_optimize_erase_subtitles import video_optimize_erase_subtitles, cancel_erase_subtitles, reset_cancel, EraseCancelled


def alg_video_optimize_erase_subtitles(work):
    work._clear_right_frame()
    video_path = work.video.path
    if not os.path.exists(video_path) or os.path.splitext(video_path)[1] not in VIDEO_EXTENSION:
        message_box = TLRMessageBox(work.master,
                                    icon="warning",
                                    title=work.translate("Warning"),
                                    message=work.translate("Please import the video file you want to process first."),
                                    button_text=[work.translate("OK")],
                                    bitmap_path=os.path.join(Paths.STATIC, work.appimages.ICON_ICO_256))
        work.dialog_show(message_box)
        return

    timestamp = Timer.get_timestamp()
    operation_file = os.path.join(work.app.project_path, "files", timestamp)
    os.makedirs(operation_file, exist_ok=True)
    log_path = os.path.join(operation_file, f"{timestamp}.log")
    operation_temp_file = os.path.join(operation_file, "temp")
    os.makedirs(operation_temp_file, exist_ok=True)
    show_temp_file = os.path.join(operation_file, "show_temp")
    os.makedirs(show_temp_file, exist_ok=True)

    video_name = f"{Config.OUTPUT_VIDEO_NAME}{os.path.splitext(work.video.path)[1]}"
    pre_last_video_name = f"pre_{Config.OUTPUT_VIDEO_NAME}{os.path.splitext(work.video.path)[1]}"
    output_video_path = os.path.join(work.app.project_path, Config.PROJECT_VIDEOS, video_name)
    pre_last_video_path = os.path.join(work.app.project_path, Config.PROJECT_VIDEOS, pre_last_video_name)
    if os.path.exists(output_video_path):
        if os.path.exists(pre_last_video_path):
            os.remove(pre_last_video_path)
        os.rename(output_video_path, pre_last_video_path)
        work.video.path = pre_last_video_path
    else:
        pre_last_video_path = work.video.path

    work._right_frame.grid_columnconfigure(0, weight=10)
    work._right_frame.grid_columnconfigure(1, weight=1)

    right_scroll = CTkScrollableFrame(work._right_frame,
                                      fg_color=work._apply_appearance_mode(work._fg_color),
                                      bg_color=work._border_color,
                                      corner_radius=0)
    right_scroll._scrollbar.configure(width=0)
    right_scroll.grid_columnconfigure(0, weight=1)
    right_scroll.grid(row=0, column=0, padx=5, pady=(10, 0), sticky="nsew")
    logger = Logger(log_path, timestamp)

    def _video_optimize_erase_subtitles():
        video = VideoFileClip(work.video.path)
        fps = video.fps
        duration = video.duration
        nframes = int(duration * fps)
        video.close()

        def _get_image_representation_modal():
            video = VideoFileClip(work.video.path)
            logger.write_log(f"follow:1:1:{nframes}:0")
            max_images_num = 50
            interval = int(5 * fps)
            save_count = 0
            for i, frame in enumerate(tqdm(video.iter_frames())):
                if i % interval == 0:
                    temp_image_path = os.path.join(show_temp_file, f"{i:08d}.png")
                    Image.fromarray(frame).save(temp_image_path)
                    save_count += 1
                if save_count >= max_images_num:
                    break
                logger.write_log(f"follow:1:1:{nframes}:{i + 1}")
            logger.write_log(f"follow:1:1:{nframes}:{nframes}")
            video.close()

        TLRModal(work,
                 _get_image_representation_modal,
                 fg_color=(Config.MODAL_LIGHT, Config.MODAL_DARK),
                 logger=logger,
                 translate_func=work.translate,
                 rate=nframes * 1.5,
                 error_message=work.translate("An error occurred, please try again!"),
                 messagebox_ok_button=work.translate("OK"),
                 messagebox_title=work.translate("Warning"),
                 bitmap_path=os.path.join(Paths.STATIC, work.appimages.ICON_ICO_256))

        sorted_images = [
            p for p in os.listdir(show_temp_file)
        ]
        points = [
            (work.translate("Subtitle Color"), 1),
        ]
        lines = [
            (work.translate("Subtitle Range"), 2),
        ]
        line_dialog = TLRLineDialog(
            master=work,
            images=sorted_images,
            image_root_path=show_temp_file,
            lines=lines,
            points=points,
            point_color=Config.ICON_BLUE_RGB,
            line_color=Config.ICON_PINK_RGB,
            zoom_color=Config.ICON_BLUE_RGB,
            title=work.translate("Video Optimize Erase Subtitles"),
            previous_text=work.translate("Previous"),
            next_text=work.translate("Next"),
            point_text=work.translate("Please click on the internal scope of the subtitles:"),
            line_text=work.translate("Please indicate the range of subtitles:"),
            slider_text=work.translate("Expansion scope:"),
            ok_button_text=work.translate("OK"),
            cancel_button_text=work.translate("Cancel"),

            messagebox_ok_button=work.translate("OK"),
            messagebox_title=work.translate("Warning"),
            line_prompt_warning=work.translate("Please enter the top and bottom of the subtitles first!"),
            prompt_warning=work.translate("Please enter the top, bottom, and subtitle color prompts!"),
            bitmap_path=os.path.join(Paths.STATIC, work.appimages.ICON_ICO_256),
            remove_radius=3
        )
        work.dialog_show(line_dialog)
        prompt = line_dialog.get_prompt()
        if prompt is None or len(prompt) <= 0:
            return

        top = int(prompt["lines"][0]["data"][0][1])
        down = int(prompt["lines"][1]["data"][0][1])
        dilate = int(prompt["dilate"])
        prompt_points = prompt["points"]
        subtitles_colors = list()
        for frame_id, val in prompt_points.items():
            frame_name = sorted_images[frame_id]
            frame_path = os.path.join(show_temp_file, frame_name)
            gray_frame = Image.open(frame_path).convert("L")
            for point in val:
                xy = point["data"][0]
                color = gray_frame.getpixel(xy)
                subtitles_colors.append(color)

        def _run_erase(progress_bar, progress_label, status_label, cancel_btn):
            reset_cancel()
            temp_dir = os.path.join(operation_file, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            input_data = {
                "config": {
                    "lama": {
                        "model": "damo/cv_fft_inpainting_lama",
                        "device": "gpu" if work.device == "cuda" else work.device,
                    },
                },
                "input": {
                    "timestamp": timestamp,
                    "log_path": log_path,
                    "video_path": pre_last_video_path,
                    "top": top,
                    "down": down,
                    "dilate": dilate,
                    "colors": subtitles_colors,
                },
                "output": {
                    "temp_dir": temp_dir,
                    "video_path": output_video_path
                }
            }
            try:
                video_optimize_erase_subtitles(input_data)
                work.after(0, lambda: _on_success(progress_bar, progress_label, status_label, cancel_btn))
            except EraseCancelled:
                work.after(0, lambda: _on_cancelled(progress_bar, progress_label, status_label, cancel_btn))
            except Exception as e:
                work.after(0, lambda: _on_error(str(e), progress_bar, progress_label, status_label, cancel_btn))

        def _poll_log(progress_bar, progress_label, status_label, cancel_btn, thread, done_flag=None):
            if done_flag is None:
                done_flag = [False]
            if thread.is_alive():
                try:
                    with open(log_path, "r") as f:
                        lines = f.readlines()
                    for line in lines:
                        if "follow:2:1:" in line:
                            pipe_parts = line.strip().split("|")
                            msg = pipe_parts[-1]
                            parts = msg.split(":")
                            if parts[0] == "follow" and len(parts) >= 5:
                                try:
                                    total = int(parts[3])
                                    current = int(parts[4])
                                    if total > 0:
                                        pct = min(current / total, 1.0)
                                        progress_bar.set(pct)
                                        progress_label.configure(text=f"{current}/{total}")
                                except (ValueError, IndexError):
                                    pass
                        elif "interval:2:2:1:0" in line:
                            status_label.configure(text="正在合成视频...")
                except (FileNotFoundError, IOError):
                    pass
                work.after(200, lambda: _poll_log(progress_bar, progress_label, status_label, cancel_btn, thread, done_flag))
            elif not done_flag[0]:
                done_flag[0] = True

        status_frame = CTkFrame(work._right_frame, fg_color="transparent")
        status_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)

        status_label = CTkLabel(status_frame, text="正在处理中...", font=CTkFont(size=12))
        status_label.grid(row=0, column=0, columnspan=2, pady=(0, 4), sticky="w")

        progress_label = CTkLabel(status_frame, text="0/0", font=CTkFont(size=11),
                                  text_color=("gray50", "gray50"))
        progress_label.grid(row=1, column=0, pady=(0, 4), sticky="w")

        progress_bar = CTkProgressBar(status_frame, height=16, corner_radius=4)
        progress_bar.grid(row=2, column=0, padx=(0, 8), pady=(0, 4), sticky="ew")
        progress_bar.set(0)

        cancel_btn = CTkButton(status_frame, text="取消处理", height=32,
                               fg_color="#D9534F", hover_color="#C9302C",
                               font=CTkFont(size=12),
                               command=lambda: _do_cancel(cancel_btn, status_label))
        cancel_btn.grid(row=2, column=1, padx=4, pady=(0, 4), sticky="e")

        thread = threading.Thread(target=_run_erase,
                                  args=(progress_bar, progress_label, status_label, cancel_btn),
                                  daemon=True)
        thread.start()
        work.after(200, lambda: _poll_log(progress_bar, progress_label, status_label, cancel_btn, thread))

    def _do_cancel(cancel_btn, status_label):
        cancel_erase_subtitles()
        cancel_btn.configure(state="disabled", text="正在取消...")
        status_label.configure(text="正在取消...")

    def _on_success(progress_bar, progress_label, status_label, cancel_btn):
        progress_bar.set(1.0)
        progress_label.configure(text="完成")
        status_label.configure(text="处理完成！")
        cancel_btn.configure(state="disabled", text="完成")
        _finish_up()

    def _on_cancelled(progress_bar, progress_label, status_label, cancel_btn):
        status_label.configure(text="已取消")
        cancel_btn.configure(state="disabled", text="已取消")
        _cleanup_temp()

    def _on_error(msg, progress_bar, progress_label, status_label, cancel_btn):
        status_label.configure(text=f"失败: {msg}")
        cancel_btn.configure(state="disabled", text="失败")
        _cleanup_temp()

    def _cleanup_temp():
        if os.path.exists(operation_temp_file):
            shutil.rmtree(operation_temp_file, ignore_errors=True)
        if os.path.exists(show_temp_file):
            shutil.rmtree(show_temp_file, ignore_errors=True)

    def _finish_up():
        work.video.path = output_video_path
        update_video = copy.deepcopy(work.video)
        update_video.path = update_video.path.replace(work.app.project_path, "", 1)
        work.video_controller.update([update_video])
        work._video_frame.set_video_path(work.video.path)
        work._clear_right_frame()
        if os.path.exists(pre_last_video_path):
            os.remove(pre_last_video_path)
        _cleanup_temp()

    optimize_erase_button = CTkButton(
        master=work._right_frame,
        border_width=0,
        text=work.translate("Erase Subtitles"),
        command=_video_optimize_erase_subtitles,
        anchor="center"
    )
    optimize_erase_button.grid(row=0, column=0, pady=(10, 10), sticky="s")
