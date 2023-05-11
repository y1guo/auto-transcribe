import os, json
from colorama import Fore
from utils import (
    VIDEO_DIR_LIST,
    AUDIO_DIR,
    EXCLUDELIST,
    VOCAL_DIR,
    TRANSCRIPT_DIR,
    get_duration,
    msg,
)


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
            duration = get_duration(os.path.join(AUDIO_DIR, file))
            if duration:
                exclude[base_name] = duration

    # print exclude info
    msg(
        "Validate",
        "Audio",
        f"Found {len(exclude)} excluded files. Maximum duration: {highlight(max(exclude.values()), '>', 30)} s",
    )

    # get video info
    video = {}
    for dir in VIDEO_DIR_LIST:
        for file in os.listdir(dir):
            if file.endswith(".mp4") or file.endswith(".flv"):
                base_name = os.path.splitext(file)[0]
                duration = get_duration(os.path.join(dir, file))
                if duration:
                    video[base_name] = duration

    # get audio info
    audio = {}
    for file in os.listdir(AUDIO_DIR):
        base_name = os.path.splitext(file)[0]
        if file.endswith(".m4a") and base_name not in exclude:
            bare_name = base_name.split("_part_")[0]
            duration = get_duration(os.path.join(AUDIO_DIR, file))
            if duration:
                if bare_name in audio:
                    audio[bare_name] += duration
                else:
                    audio[bare_name] = duration

    # compare video and audio
    diff_va = set(video.keys()) - set(audio.keys())
    diff_av = set(audio.keys()) - set(video.keys())
    msg(
        "Validate",
        "Audio",
        f"Found {highlight(len(diff_va), '>', 0)} video without audio, {highlight(len(diff_av), '>', 0)} audio without video",
    )
    diff_duration = {
        _: abs(video[_] - audio[_]) for _ in set(video.keys()) & set(audio.keys())
    }
    top_two = [
        (k, diff_duration[k])
        for k in sorted(diff_duration, key=diff_duration.get, reverse=True)
    ][:2]
    msg(
        "Validate",
        "Audio",
        f"Maximum duration difference: {highlight(top_two[0][1], '>', 1)} s: {Fore.CYAN}{top_two[0][0]}",
    )
    msg(
        "Validate",
        "Audio",
        f"2nd max duration difference: {highlight(top_two[1][1], '>', 1)} s: {Fore.CYAN}{top_two[1][0]}",
    )

    # get vocal info
    vocal = {}
    for file in os.listdir(VOCAL_DIR):
        if file.endswith(".mp3"):
            base_name = os.path.splitext(file)[0]
            duration = get_duration(os.path.join(VOCAL_DIR, file))
            if duration:
                vocal[base_name] = duration

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
    top_two = [
        (k, diff_duration[k])
        for k in sorted(diff_duration, key=diff_duration.get, reverse=True)
    ][:2]
    msg(
        "Validate",
        "Vocal",
        f"Maximum duration difference: {highlight(top_two[0][1], '>', 1)} s: {Fore.CYAN}{top_two[0][0]}",
    )
    msg(
        "Validate",
        "Vocal",
        f"2nd max duration difference: {highlight(top_two[1][1], '>', 1)} s: {Fore.CYAN}{top_two[1][0]}",
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
    # msg(
    #     "Validate",
    #     "Transcript",
    #     f"Minimum transcript length: {highlight(min(transcript.values()), '<', 1)} characters: {Fore.CYAN}{min(transcript, key=transcript.get)}",
    # )

    # ending message
    msg("Validate", "Sleep", "")