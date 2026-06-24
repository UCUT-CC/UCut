import os
import shutil
import threading

import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm
from app.src.utils.logger import Logger
from moviepy.editor import VideoFileClip, ImageSequenceClip

from app.src.algorithm.base.lama.lama import LaMa

_cancel_flag = threading.Event()
_stride = 5

def cancel_erase_subtitles():
    _cancel_flag.set()

def reset_cancel():
    _cancel_flag.clear()

def is_cancelled():
    return _cancel_flag.is_set()

class EraseCancelled(Exception):
    pass

def get_single_submask(crop_image, sub_colors, dilate_size=7):
    mask = np.zeros_like(crop_image)
    for color in sub_colors:
        mask[crop_image == color] = 255
    dilate_kernel = np.ones((dilate_size, dilate_size), np.uint8)
    mask = cv2.dilate(mask, dilate_kernel)
    if np.sum(mask) == 0:
        return None
    return mask


def video_optimize_erase_subtitles(input_data):
    _cancel_flag.clear()
    timestamp = input_data["input"]["timestamp"]
    log_path = input_data["input"]["log_path"]
    logger = Logger(log_path, timestamp)

    global _stride
    stride = input_data["input"].get("stride", _stride)

    logger.write_log("interval:0:0:0:0:Model Load")
    lama_config = input_data["config"]["lama"]
    lama = LaMa(lama_config, logger)
    logger.write_log("interval:0:0:0:0:Model Load")

    input_path = input_data["input"]["video_path"]
    top = input_data["input"]["top"]
    down = input_data["input"]["down"]
    dilate = input_data["input"]["dilate"]
    colors = input_data["input"]["colors"]

    temp_dir = input_data["output"]["temp_dir"]
    output_path = input_data["output"]["video_path"]

    os.makedirs(temp_dir, exist_ok=True)

    video = VideoFileClip(input_path)
    vw, vh = video.size
    fps = video.fps
    nframes = int(video.duration * fps)
    top = max(int(top - (down - top) * 0.15), 0)
    down = min(int(down + (down - top) * 0.15), vh)

    logger.write_log(f"follow:2:1:{nframes}:0")
    image_paths = list()
    last_output_frame = None

    for i, frame in enumerate(tqdm(video.iter_frames())):
        if is_cancelled():
            video.close()
            raise EraseCancelled()

        if stride > 1 and i % stride != 0 and last_output_frame is not None:
            reuse = last_output_frame if last_output_frame is not None else frame
            temp_image_path = os.path.join(temp_dir, f"image_{i}.png")
            Image.fromarray(reuse[:, :, ::-1]).save(temp_image_path)
            image_paths.append(temp_image_path)
            if i % 10 == 0:
                logger.write_log(f"follow:2:1:{nframes}:{i + 1}")
            continue

        crop_frame = frame[top:down, :, :]
        crop_frame = cv2.cvtColor(crop_frame, cv2.COLOR_RGB2GRAY)
        crop_mask = get_single_submask(crop_frame, sub_colors=colors, dilate_size=dilate)
        temp_image_path = os.path.join(temp_dir, f"image_{i}.png")
        if crop_mask is not None:
            mask = np.zeros((vh, vw, 3))
            mask[top:down, :, :] = crop_mask[:, :, np.newaxis]
            frame_info = {
                "image": frame,
                "mask": mask
            }
            result = lama.infer(frame_info)
            output_image = result["image"]
            last_output_frame = output_image.copy()
            Image.fromarray(output_image[:, :, ::-1]).save(temp_image_path)
        else:
            last_output_frame = frame.copy() if i == 0 else last_output_frame
            Image.fromarray(frame).save(temp_image_path)
        image_paths.append(temp_image_path)

        progress = nframes if nframes <= 100 else nframes
        logger.write_log(f"follow:2:1:{progress}:{min(i + 1, progress)}")

    logger.write_log(f"follow:2:1:{nframes}:{nframes}")
    logger.write_log(f"interval:2:2:1:0")
    output_video = ImageSequenceClip(image_paths, fps=fps)

    output_video = output_video.set_audio(video.audio)
    output_video.write_videofile(output_path)
    shutil.rmtree(temp_dir)
    video.close()
    logger.write_log(f"interval:2:2:1:1")
