import os, json, time, ffmpeg
from colorama import Fore


# load config

with open("config.json") as f:
    config = json.load(f)

VIDEO_DIR_LIST = config["video_dir_list"]
OUT_DIR = config["out_dir"]
PART_DURATION = config["part_duration"]

AUDIO_DIR = os.path.join(OUT_DIR, "audio")
VOCAL_DIR = os.path.join(OUT_DIR, "vocal")
TMP_DIR = os.path.join(OUT_DIR, "tmp")
TRANSCRIPT_DIR = os.path.join(OUT_DIR, "transcript")
for dir in [AUDIO_DIR, VOCAL_DIR, TMP_DIR, TRANSCRIPT_DIR]:
    if not os.path.exists(dir):
        os.mkdir(dir)

EXCLUDELIST = os.path.join(AUDIO_DIR, "exclude.txt")


# utility functions


def get_duration(file: str) -> float | None:
    output = ffmpeg.probe(file)
    if output["streams"]:
        duration = float(output["format"]["duration"])
        return duration


def msg(
    sender: str, action: str, message: str = "", file: str = "", error: bool = False
) -> None:
    color = Fore.RED if error else Fore.GREEN
    print(
        f'{color}[{time.strftime("%m-%d %H:%M:%S", time.localtime())} {sender}]',
        f"{Fore.YELLOW}{action:<12}",
        f"{Fore.RESET}{message}",
        f"{Fore.CYAN}{file}",
    )


def get_video_file(bare_name: str) -> str:
    """find the video by bare name"""
    for dir in VIDEO_DIR_LIST:
        for file in os.listdir(dir):
            if file.startswith(bare_name):
                video_file = os.path.join(dir, file)
                return video_file
