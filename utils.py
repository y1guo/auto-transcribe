import os, json, time, subprocess
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
    output = subprocess.run(
        [
            "ffprobe",
            "-i",
            file,
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
        ],
        capture_output=True,
    )
    # print stderr
    if output.returncode == 0:
        duration = float(output.stdout)
        return duration


def msg(sender: str, action: str, message: str, error: bool = False) -> None:
    if error:
        color = Fore.RED
    else:
        color = Fore.GREEN
    print(
        f'{color}[{time.strftime("%m-%d %H:%M:%S", time.localtime())} {sender}]',
        f"{Fore.YELLOW}{action:<16}",
        f"{Fore.RESET}{message}",
    )
