import os, json
from colorama import Fore
from utils import AUDIO_DIR, EXCLUDELIST, VOCAL_DIR, TRANSCRIPT_DIR, get_duration, msg


def highlight(value: int | float, operand: str, threshold: float) -> str:
    condition = value > threshold if operand == ">" else value < threshold
    if condition:
        color = Fore.RED
    else:
        color = Fore.GREEN
    msg = f"{value:.2f}" if isinstance(value, float) else str(value)
    return f"{color}{msg}{Fore.RESET}"


if __name__ == "__main__":
    # get exclude info
    exclude = {}
    with open(EXCLUDELIST, "r") as f:
        exclude_list = f.read().splitlines()
        for file in exclude_list:
            base_name = os.path.splitext(file)[0]
            exclude[base_name] = get_duration(os.path.join(AUDIO_DIR, file))

    # print exclude info
    msg(
        "Validate",
        "Audio",
        f"Found {len(exclude)} excluded files. Maximum duration: {highlight(max(exclude.values()), '>', 30)} s",
    )

    # get audio info
    audio = {}
    for file in os.listdir(AUDIO_DIR):
        base_name = os.path.splitext(file)[0]
        if file.endswith(".m4a") and base_name not in exclude:
            bare_name = base_name.split("_part_")[0]
            audio[bare_name] = get_duration(os.path.join(AUDIO_DIR, file))

    # get vocal info
    vocal = {}
    for file in os.listdir(VOCAL_DIR):
        if file.endswith(".mp3"):
            base_name = os.path.splitext(file)[0]
            vocal[base_name] = get_duration(os.path.join(VOCAL_DIR, file))

    # compare audio and vocal
    diff_av = set(audio.keys()) - set(vocal.keys())
    diff_va = set(vocal.keys()) - set(audio.keys())
    msg(
        "Validate",
        "Vocal",
        f"Found {highlight(len(diff_av), '>', 0)} audio without vocal, {highlight(len(diff_va), '>', 0)} vocal without audio",
    )
    diff_duration = {
        _: abs(audio[_] - vocal[_]) for _ in set(audio.keys()) & set(vocal.keys())
    }
    msg(
        "Validate",
        "Vocal",
        f"Maximum duration difference: {highlight(max(diff_duration.values()), '>', 1)} s: {Fore.CYAN}{max(diff_duration, key=diff_duration.get)}",
    )

    # get transcript info
    transcript = {}
    for file in os.listdir(TRANSCRIPT_DIR):
        if file.endswith(".json"):
            base_name = os.path.splitext(file)[0]
            with open(os.path.join(TRANSCRIPT_DIR, file), "r") as f:
                transcript[base_name] = len(json.load(f)["text"])

    # compare vocal and transcript
    diff_vt = set(vocal.keys()) - set(transcript.keys())
    diff_tv = set(transcript.keys()) - set(vocal.keys())
    msg(
        "Validate",
        "Transcript",
        f"Found {highlight(len(diff_vt), '>', 0)} vocal without transcript, {highlight(len(diff_tv), '>', 0)} transcript without vocal",
    )
    msg(
        "Validate",
        "Transcript",
        f"Minimum transcript length: {highlight(min(transcript.values()), '<', 1)} characters: {Fore.CYAN}{min(transcript, key=transcript.get)}",
    )
