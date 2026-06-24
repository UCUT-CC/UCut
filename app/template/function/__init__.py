import importlib

_MODULES = [
    "video_cut_audio",
    "video_cut_face",
    "video_generate_audio",
    "video_generate_broadcast",
    "video_generate_captions",
    "video_generate_color",
    "video_generate_language",
    "video_optimize_background",
    "video_optimize_erase_subtitles",
    "video_optimize_fluency",
    "video_optimize_resolution",
    "video_optimize_remove_target",
    "video_optimize_local_processing",
]

def __getattr__(name):
    if name.startswith("alg_") and name[4:] in _MODULES:
        mod = importlib.import_module(f"app.template.function.{name[4:]}")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
