import os, time, ffmpeg
from utils import (
    VIDEO_DIR_LIST,
    TMP_DIR,
    get_duration,
    msg,
    valid,
    get_audio_parts,
)


def extract_audio(video: str) -> None:
    base_name = os.path.splitext(os.path.basename(video))[0]
    bare_name = base_name
    cache_audio = os.path.join(TMP_DIR, f"{bare_name}.m4a")
    # skip if video is not valid (prerequisite)
    try:
        audio_parts = get_audio_parts(bare_name)
    except Exception as e:
        msg("Audio", "get_audio_parts()", repr(e), file=video, error=True)
        return
    # skip if all valid audio parts already exists (job)
    if all(
        valid(os.path.splitext(os.path.basename(f))[0], "audio") for f in audio_parts
    ):
        return
    # extract cache
    try:
        msg("Audio", "Caching", file=cache_audio)
        start_time = time.time()
        ffmpeg.input(video).audio.output(cache_audio, acodec="copy").run(
            overwrite_output=True, quiet=True
        )
    except (Exception, KeyboardInterrupt) as e:
        try:
            os.remove(cache_audio)
        except:
            pass
        if isinstance(e, Exception):
            msg(
                "Audio",
                "Cache Failed",
                file=cache_audio,
                error=True,
            )
        raise
    else:
        end_time = time.time()
        speed = get_duration(cache_audio) / (end_time - start_time)
        msg("Audio", "Cached", f"({speed:.0f}X)", file=cache_audio)
    # extract audio
    if len(audio_parts) > 1:
        ss = 0
        for audio in audio_parts:
            start_time = time.time()
            try:
                ffmpeg.input(cache_audio).output(
                    audio,
                    ss=ss,
                    to=ss + audio_parts[audio],
                    acodec="copy",
                ).run(overwrite_output=True, quiet=True)
            except (Exception, KeyboardInterrupt) as e:
                try:
                    os.remove(audio)
                except:
                    pass
                if isinstance(e, Exception):
                    msg(
                        "Audio",
                        "Extract Failed",
                        file=audio,
                        error=True,
                    )
                raise
            ss += audio_parts[audio]
            end_time = time.time()
            speed = get_duration(audio) / (end_time - start_time)
            msg(
                "Audio",
                "Extracted",
                f"({speed:.0f}X)",
                file=audio,
            )
    else:
        audio = list(audio_parts.keys())[0]
        try:
            os.rename(cache_audio, audio)
        except Exception:
            msg(
                "Audio",
                "Extract Failed",
                file=audio,
                error=True,
            )
            raise
        msg("Audio", "Extracted", file=audio)


if __name__ == "__main__":
    try:
        msg("Audio", "Scanning")
        for dir in VIDEO_DIR_LIST:
            for file in os.listdir(dir):
                if file.endswith(".mp4") or file.endswith(".flv"):
                    extract_audio(os.path.join(dir, file))
    except KeyboardInterrupt:
        msg("Audio", "Safe to Exit")
    except Exception as e:
        msg("Audio", type(e).__name__, e, error=True)
        if hasattr(e, "stdout"):
            msg("Audio", "STDOUT", e.stdout.decode(), error=True)
        if hasattr(e, "stderr"):
            msg("Audio", "STDERR", e.stderr.decode(), error=True)
        raise
