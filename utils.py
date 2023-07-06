import os, json, time, ffmpeg
from colorama import Fore
from math import ceil


# load config
with open("config.json") as f:
    config = json.load(f)
VIDEO_DIR_LIST = config["video_dir_list"]
OUT_DIR = config["out_dir"]
PART_DURATION = config["part_duration"]
# work directories
AUDIO_DIR = os.path.join(OUT_DIR, "audio")
VOCAL_DIR = os.path.join(OUT_DIR, "vocal")
TMP_DIR = os.path.join(OUT_DIR, "tmp")
DEMUCS_DIR = os.path.join(TMP_DIR, "htdemucs")
TRANSCRIPT_DIR = os.path.join(OUT_DIR, "transcript")
SLICE_DIR = os.path.join(TMP_DIR, "slice")
FAVORITE_DIR = os.path.join(OUT_DIR, "favorite")
for dir in [AUDIO_DIR, VOCAL_DIR, TMP_DIR, TRANSCRIPT_DIR, SLICE_DIR, FAVORITE_DIR]:
    if not os.path.exists(dir):
        os.mkdir(dir)
# other global variables
EXCLUDELIST = os.path.join(AUDIO_DIR, "exclude.txt")


# utility functions


def get_duration(file: str) -> float:
    if file.endswith(".json"):
        with open(file) as f:
            data = json.load(f)
            segments = data["segments"]
            if segments:
                duration = segments[-1]["end"] - segments[0]["start"]
            else:
                duration = 0
    else:
        output = ffmpeg.probe(file)
        duration = float(output["format"]["duration"])
    return duration


def msg(
    sender: str,
    action: str,
    message: str = "",
    file: str = "",
    error: bool = False,
    end: str = "\n",
) -> None:
    # clear line
    print(" " * os.get_terminal_size().columns, end="\r", flush=True)
    # print message
    color = Fore.RED if error else Fore.GREEN
    print(
        f'{color}[{time.strftime("%m-%d %H:%M:%S", time.localtime())} {sender:>7}] '
        f"{Fore.YELLOW}{action:<12} "
        f"{Fore.RESET}{message} "
        f"{Fore.CYAN}{os.path.basename(file)}{Fore.RESET}",
        end=end,
        flush=True,
    )


def highlight(value: int | float, operand: str, threshold: float) -> str:
    condition = value > threshold if operand == ">" else value < threshold
    if condition:
        color = Fore.RED
    else:
        color = Fore.GREEN
    msg = f"{value:.2f}" if isinstance(value, float) else str(value)
    return f"{color}{msg}{Fore.RESET}"


def get_video(bare_name: str) -> str:
    """find the video path by bare name"""
    for dir in VIDEO_DIR_LIST:
        for file in os.listdir(dir):
            if file in [f"{bare_name}.mp4", f"{bare_name}.flv"]:
                video = os.path.join(dir, file)
                return video
    raise Exception(f"Can't find video for bare name: {bare_name}")


def get_audio_parts(bare_name: str) -> dict[str, float]:
    """Find the audio part files by bare name. Note that it returns the designed filenames and durations,
    not the actual files and durations.

    Returns
    -------
    dict[str, float]
        {audio_part_path: duration}
    """
    video = get_video(bare_name)
    video_duration = get_duration(video)
    num_part = ceil(video_duration / PART_DURATION)
    if num_part == 1:
        audio_parts = {os.path.join(AUDIO_DIR, f"{bare_name}.m4a"): video_duration}
    else:
        audio_parts = {
            os.path.join(AUDIO_DIR, f"{bare_name}_part_{1+i:02d}.m4a"): PART_DURATION for i in range(num_part - 1)
        } | {os.path.join(AUDIO_DIR, f"{bare_name}_part_{num_part:02d}.m4a"): video_duration % PART_DURATION}
    return audio_parts


def valid(base_name: str, target: str) -> bool:
    """Whether the job at the given target has been done correctly. If valid, it will also clean up the temporary
    files.

    Parameters
    ----------
    base_name : str
        The base name of the file to be checked.
    target : str
        The target file to be checked. Can be one of
        "audio", "demucs", "vocal", "transcript".

    Returns
    -------
    bool
        True if the job has been done correctly, False otherwise.
    """
    bare_name = base_name.split("_vocal")[0].split("_part_")[0]
    audio = os.path.join(AUDIO_DIR, f"{base_name}.m4a")
    wav = os.path.join(DEMUCS_DIR, f"{base_name}_vocals.wav")
    vocal = os.path.join(VOCAL_DIR, f"{bare_name}.mp3")
    transcript = os.path.join(TRANSCRIPT_DIR, f"{bare_name}.json")
    VALIDLIST = os.path.join(TMP_DIR, f"valid_{target}.txt")
    # check if already validated, and clean up temporary files
    try:
        with open(VALIDLIST) as f:
            valid_list = f.read().splitlines()
            if target in ["audio"] and base_name in valid_list:
                # clean up temporary files
                if target == "audio":
                    for file in os.listdir(TMP_DIR):
                        if file.startswith(bare_name):
                            try:
                                os.remove(os.path.join(TMP_DIR, file))
                            except:
                                pass
                return True
            if target in ["vocal", "transcript"] and bare_name in valid_list:
                # clean up temporary files
                if target == "vocal":
                    for file in os.listdir(DEMUCS_DIR):
                        if file.startswith(bare_name):
                            try:
                                os.remove(os.path.join(DEMUCS_DIR, file))
                            except:
                                pass
                return True
    except FileNotFoundError:
        pass
    # case-wise parameters
    if target in ["audio", "demucs"]:
        # audio and demucs compare to part duration
        audio_parts = get_audio_parts(bare_name)
        if target == "audio":
            file = audio
            compare = audio_parts[audio]
            threshold = 1
            sender = "Audio"
        else:
            file = wav
            compare = audio_parts[audio]
            threshold = 1
            sender = "Demucs"
    else:
        # vocal and transcript compare to video duration
        video = get_video(bare_name)
        video_duration = get_duration(video)
        if target == "vocal":
            file = vocal
            compare = video_duration
            threshold = 1
            sender = "Vocal"
        else:
            file = transcript
            compare = video_duration
            threshold = 600
            sender = "Transcribe"
    # validate
    try:
        duration = get_duration(file)
    except:
        return False
    diff = abs(duration - compare)
    if diff > threshold:
        # msg(
        #     sender,
        #     "Duration Mismatch",
        #     f"diff {Fore.RED}{diff:.2f}{Fore.RESET} s",
        #     file=file,
        #     error=True,
        # )
        return False
    # additional check for transcript
    if target == "transcript":
        # check if the last segment exceeds the video duration
        with open(file) as f:
            data = json.load(f)
            segments = data["segments"]
            max_time = 0
            if segments:
                max_time = segments[-1]["end"]
            msg("DEBUG", "max_time", str(max_time) + "   " + str(compare), file=file)
            if max_time > compare + 2:
                return False
        # check if the vocal file is modified after transcription
        if os.path.getmtime(vocal) > os.path.getmtime(file):
            return False
    # add to valid list
    with open(VALIDLIST, "a") as f:
        if target in ["audio"]:
            f.write(base_name + "\n")
        elif target in ["vocal", "transcript"]:
            f.write(bare_name + "\n")

    return True
