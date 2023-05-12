# Extract audio from video files in the directory list.
# If the audio is longer than 1 hour, split it into 1 hour parts.
# Audio files that are already in the directory are skipped.

import os, time, ffmpeg
from utils import VIDEO_DIR_LIST, AUDIO_DIR, PART_DURATION, TMP_DIR, get_duration, msg


def extract_audio(dir: str, file: str) -> None:
    base_name = os.path.splitext(file)[0]
    in_file = os.path.join(dir, file)
    cache_file = os.path.join(TMP_DIR, f"{base_name}.m4a")
    duration = get_duration(in_file)
    # skip if video has not finished writing
    if not duration:
        return
    # skip if audio already exists and is not broken
    is_parted = duration > PART_DURATION
    if is_parted:
        num_part = int(duration // PART_DURATION) + 1
        part_files = [
            os.path.join(AUDIO_DIR, f"{base_name}_part_{1+i:02d}.m4a")
            for i in range(num_part)
        ]
        if all(os.path.exists(f) and get_duration(f) for f in part_files):
            # audio already exists, clear cache if it exists, and return
            try:
                os.remove(cache_file)
            except OSError:
                pass
            return
    else:
        out_file = os.path.join(AUDIO_DIR, f"{base_name}.m4a")
        if os.path.exists(out_file) and get_duration(out_file):
            return
    # cache the audio track if it does not exist or is broken
    if not os.path.exists(cache_file) or abs(get_duration(cache_file) - duration) > 1:
        msg("Audio", "Caching", file=os.path.basename(cache_file))
        start_time = time.time()
        try:
            ffmpeg.input(in_file).audio.output(cache_file, acodec="copy").run(
                overwrite_output=True, quiet=True
            )
        except (Exception, KeyboardInterrupt) as e:
            try:
                os.remove(cache_file)
            except OSError:
                pass
            if isinstance(e, KeyboardInterrupt):
                msg("Audio", "Safe to Exit")
            else:
                msg(
                    "Audio",
                    "Cache Failed",
                    e,
                    file=os.path.basename(cache_file),
                    error=True,
                )
            raise KeyboardInterrupt
        end_time = time.time()
        speed = round(duration / (end_time - start_time))
        msg("Audio", "Cached", f"({speed}X)", file=os.path.basename(cache_file))
    # extract audio
    if is_parted:
        for i, out_file in enumerate(part_files):
            # extract audio if it does not exist or is broken
            if not os.path.exists(out_file) or not get_duration(out_file):
                # extract audio from cache
                tmp_file = os.path.join(TMP_DIR, os.path.basename(out_file))
                start_time = time.time()
                try:
                    ffmpeg.input(cache_file).output(
                        tmp_file,
                        ss=i * PART_DURATION,
                        t=PART_DURATION,
                        acodec="copy",
                    ).run(overwrite_output=True, quiet=True)
                    os.rename(tmp_file, out_file)
                except (Exception, KeyboardInterrupt) as e:
                    try:
                        os.remove(tmp_file)
                    except OSError:
                        pass
                    if isinstance(e, KeyboardInterrupt):
                        msg("Audio", "Safe to Exit")
                    else:
                        msg(
                            "Audio",
                            "Extract Failed",
                            e,
                            file=os.path.basename(out_file),
                            error=True,
                        )
                    raise KeyboardInterrupt
                end_time = time.time()
                speed = round(get_duration(out_file) / (end_time - start_time))
                msg(
                    "Audio",
                    "Extracted",
                    f"({speed}X)",
                    file=os.path.basename(out_file),
                )
    else:
        try:
            os.rename(cache_file, out_file)
        except (Exception, KeyboardInterrupt) as e:
            if isinstance(e, KeyboardInterrupt):
                msg("Audio", "Safe to Exit")
            else:
                msg(
                    "Audio",
                    "Extract Failed",
                    e,
                    file=os.path.basename(out_file),
                    error=True,
                )
            raise KeyboardInterrupt
        msg("Audio", "Extracted", file=os.path.basename(out_file))


if __name__ == "__main__":
    try:
        msg("Audio", "Starting")
        for video_dir in VIDEO_DIR_LIST:
            for file in os.listdir(video_dir):
                if file.endswith(".mp4") or file.endswith(".flv"):
                    extract_audio(video_dir, file)
    except KeyboardInterrupt:
        pass
