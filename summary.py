import os, json
from utils import (
    VIDEO_DIR_LIST,
    AUDIO_DIR,
    DEMUCS_DIR,
    EXCLUDELIST,
    VOCAL_DIR,
    TRANSCRIPT_DIR,
    get_duration,
    msg,
    highlight,
)


def main() -> None:
    # get exclude info
    exclude = {}
    try:
        with open(EXCLUDELIST, "r") as f:
            exclude_list = f.read().splitlines()
            for file in exclude_list:
                base_name = os.path.splitext(file)[0]
                duration = get_duration(os.path.join(AUDIO_DIR, file))
                if duration:
                    exclude[base_name] = duration
    except FileNotFoundError:
        pass

    # print exclude info
    msg("Summary", "Exclude", f"{len(exclude)} excluded")
    top_n = [(k, exclude[k]) for k in sorted(exclude, key=exclude.get, reverse=True)]
    for i in range(min(5, len(top_n))):
        msg(
            "Summary",
            "Exclude",
            f"#{i+1} max duration: {highlight(top_n[i][1], '>', 300)} s:",
            f"{top_n[i][0]}",
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
    diff_va = set(video.keys()) - set(audio.keys()) - set(exclude.keys())
    msg(
        "Summary",
        "Audio",
        f"Found {highlight(len(diff_va), '>', 0)} video without audio",
    )
    for i in range(min(5, len(diff_va))):
        msg("Summary", "Audio", f"Video without audio #{i+1}:", f"{diff_va.pop()}")
    diff_av = (set(audio.keys()) | set(exclude.keys())) - set(video.keys())
    msg(
        "Summary",
        "Audio",
        f"Found {highlight(len(diff_av), '>', 0)} audio without video",
    )
    for i in range(min(5, len(diff_av))):
        msg("Summary", "Audio", f"Audio without video #{i+1}:", f"{diff_av.pop()}")
    diff_duration = {
        _: abs(video[_] - audio[_]) for _ in set(video.keys()) & set(audio.keys())
    }
    top_n = [
        (k, diff_duration[k])
        for k in sorted(diff_duration, key=diff_duration.get, reverse=True)
    ]
    for i in range(min(5, len(top_n))):
        msg(
            "Summary",
            "Audio",
            f"#{i+1} inconsistency {highlight(top_n[i][1], '>', 1)} s:",
            f"{top_n[i][0]}",
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
    msg(
        "Summary",
        "Vocal",
        f"Found {highlight(len(diff_av), '>', 0)} audio without vocal",
    )
    for i in range(min(5, len(diff_av))):
        msg("Summary", "Vocal", f"Audio without vocal #{i+1}:", f"{diff_av.pop()}")
    diff_va = set(vocal.keys()) - set(audio.keys())
    msg(
        "Summary",
        "Vocal",
        f"Found {highlight(len(diff_va), '>', 0)} vocal without audio",
    )
    for i in range(min(5, len(diff_va))):
        msg("Summary", "Vocal", f"Vocal without audio #{i+1}:", f"{diff_va.pop()}")
    diff_duration = {
        _: abs(audio[_] - vocal[_]) for _ in set(audio.keys()) & set(vocal.keys())
    }
    top_n = [
        (k, diff_duration[k])
        for k in sorted(diff_duration, key=diff_duration.get, reverse=True)
    ]
    for i in range(min(5, len(top_n))):
        msg(
            "Summary",
            "Vocal",
            f"#{i+1} inconsistency {highlight(top_n[i][1], '>', 1)} s:",
            f"{top_n[i][0]}",
        )

    # get transcript info
    transcript = {}
    for file in os.listdir(TRANSCRIPT_DIR):
        if file.endswith(".json"):
            base_name = os.path.splitext(file)[0]
            transcript[base_name] = get_duration(os.path.join(TRANSCRIPT_DIR, file))

    # compare vocal and transcript
    diff_vt = set(vocal.keys()) - set(transcript.keys())
    cached = 0
    for file in os.listdir(DEMUCS_DIR):
        if file.endswith("_vocals.wav"):
            cached += get_duration(os.path.join(DEMUCS_DIR, file))
    msg(
        "Summary",
        "Transcript",
        f"Found {highlight(len(diff_vt), '>', 0)} vocal without transcript, total {sum([vocal[k] for k in diff_vt]) / 3600:.1f} h, cached {cached / 3600:.1f} h ",
    )
    for i in range(min(5, len(diff_vt))):
        msg(
            "Summary",
            "Transcript",
            f"Vocal without transcript #{i+1}:",
            f"{diff_vt.pop()}",
        )
    diff_tv = set(transcript.keys()) - set(vocal.keys())
    msg(
        "Summary",
        "Transcript",
        f"Found {highlight(len(diff_tv), '>', 0)} transcript without vocal",
    )
    for i in range(min(5, len(diff_tv))):
        msg(
            "Summary",
            "Transcript",
            f"Transcript without vocal #{i+1}:",
            f"{diff_tv.pop()}",
        )
    diff_duration = {
        _: abs(vocal[_] - transcript[_])
        for _ in set(vocal.keys()) & set(transcript.keys())
    }
    top_n = [
        (k, diff_duration[k])
        for k in sorted(diff_duration, key=diff_duration.get, reverse=True)
    ]
    for i in range(min(5, len(top_n))):
        msg(
            "Summary",
            "Transcript",
            f"#{i+1} inconsistency {highlight(top_n[i][1], '>', 600)} s:",
            f"{top_n[i][0]}",
        )
    total_duration = sum(video.values())
    transcribed_duration = sum(
        video[k] for k in (set(video.keys()) & set(transcript.keys()))
    )
    msg(
        "Summary",
        "Transcript",
        f"Transcribed {transcribed_duration / 3600:.1f} h in total, {(total_duration - transcribed_duration) / 3600:.1f} h remaining",
    )

    # ending message
    msg("Summary", "Done", "-" * 32)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        msg("Summary", "Aborted", "KeyboardInterrupt")
    except Exception as e:
        msg("Summary", type(e).__name__, e, error=True)
        if hasattr(e, "stdout"):
            msg("Summary", "STDOUT", e.stdout.decode(), error=True)
        if hasattr(e, "stderr"):
            msg("Summary", "STDERR", e.stderr.decode(), error=True)
        raise
