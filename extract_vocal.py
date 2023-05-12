import os, shutil, time, ffmpeg, subprocess
from utils import (
    AUDIO_DIR,
    VOCAL_DIR,
    TMP_DIR,
    EXCLUDELIST,
    PART_DURATION,
    get_duration,
    msg,
    get_video_file,
)


def extract_vocal(file: str) -> None:
    base_name = os.path.splitext(file)[0]
    bare_name = base_name.split("_part_")[0]
    in_file = os.path.join(AUDIO_DIR, file)
    out_file = os.path.join(VOCAL_DIR, f"{bare_name}.mp3")
    tmp_mp3 = os.path.join(TMP_DIR, os.path.basename(out_file))
    tmp_wav = os.path.join(TMP_DIR, "htdemucs", base_name, "vocals.wav")
    duration = get_duration(in_file)
    # skip if audio has not finished writing
    if not duration:
        return
    # expected output duration
    tot_duration = get_duration(get_video_file(bare_name))
    # part info
    if "_part_" in base_name:
        num_part = int(tot_duration // PART_DURATION) + 1
        part_number = int(base_name.split("_part_")[1])
        part_files = [
            os.path.join(
                TMP_DIR, "htdemucs", f"{base_name[:-2]}{1+i:02d}", "vocals.wav"
            )
            for i in range(num_part)
        ]
        part_durations = [PART_DURATION] * (num_part - 1) + [
            tot_duration % PART_DURATION
        ]
    # skip if vocal already exists and is not broken
    if os.path.exists(out_file) and abs(get_duration(out_file) - tot_duration) < 1:
        # clear tmp file
        if "_part_" in base_name:
            for part_file in part_files:
                try:
                    shutil.rmtree(os.path.dirname(part_file))
                except OSError:
                    pass
        else:
            try:
                shutil.rmtree(os.path.dirname(tmp_wav))
            except OSError:
                pass
        return
    # skip if in exclude list
    try:
        with open(EXCLUDELIST) as f:
            exclude_list = f.read().splitlines()
        if file in exclude_list:
            return
    except FileNotFoundError:
        pass
    # extract vocal to tmp if vocal does not exist or is broken
    if not os.path.exists(tmp_wav) or abs(get_duration(tmp_wav) - duration) > 1:
        msg("Vocal", "Extracting", file=os.path.join(base_name, "vocals.wav"))
        start_time = time.time()
        try:
            output = subprocess.run(
                [
                    "demucs",
                    "--two-stems",
                    "vocals",
                    "--shifts",
                    "2",
                    "-o",
                    TMP_DIR,
                    in_file,
                ],
                capture_output=True,
            )
            if output.returncode != 0:
                raise Exception(output.stderr.decode())
        except (Exception, KeyboardInterrupt) as e:
            try:
                shutil.rmtree(os.path.dirname(tmp_wav))
            except OSError:
                pass
            if isinstance(e, KeyboardInterrupt):
                msg("Vocal", "Safe to Exit")
            else:
                with open(EXCLUDELIST, "a") as f:
                    f.write(f"{file}\n")
                msg(
                    "Vocal",
                    "Extract Failed",
                    e,
                    file=os.path.join(base_name, "vocals.wav"),
                    error=True,
                )
            raise KeyboardInterrupt
        end_time = time.time()
        speed = round(duration / (end_time - start_time))
        msg(
            "Vocal",
            "Extracted",
            f"({speed}X)",
            file=os.path.join(base_name, "vocals.wav"),
        )
    # move or merge vocal from tmp dir to vocal dir
    if "_part_" in base_name:
        # skip if it is not the last part
        if part_number != num_part:
            return
        # skip if not all parts are present and not broken
        for part_file, part_duration in zip(part_files, part_durations):
            if (
                not os.path.exists(part_file)
                or abs(get_duration(part_file) - part_duration) > 1
            ):
                return
        # merge vocal
        TMP_FILE = os.path.join(TMP_DIR, "filelist.txt")
        with open(TMP_FILE, "w") as f:
            for part_file in part_files:
                f.write(f"file '{part_file}'\n")
        msg(
            "Vocal",
            "Merging",
            file=os.path.basename(out_file),
        )
        start_time = time.time()
        # output = subprocess.run(
        #     [
        #         "ffmpeg",
        #         "-f",
        #         "concat",
        #         "-safe",
        #         "0",
        #         "-i",
        #         TMP_FILE,
        #         "-ab",
        #         "320k",
        #         "-y",
        #         tmp_mp3,
        #     ],
        #     capture_output=True,
        # )
        try:
            ffmpeg.input(TMP_FILE, format="concat", safe=0).output(
                tmp_mp3, ab="320k"
            ).run(overwrite_output=True, quiet=True)
            os.rename(tmp_mp3, out_file)
        except (Exception, KeyboardInterrupt) as e:
            try:
                os.remove(tmp_mp3)
            except OSError:
                pass
            if isinstance(e, KeyboardInterrupt):
                msg("Vocal", "Safe to Exit")
            else:
                msg(
                    "Vocal",
                    "Merge Failed",
                    e,
                    file=os.path.basename(out_file),
                    error=True,
                )
            raise KeyboardInterrupt
        end_time = time.time()
        speed = round(get_duration(out_file) / (end_time - start_time))
        msg("Vocal", "Merged", f"({speed}X)", file=os.path.basename(out_file))
    else:
        msg(
            "Vocal",
            "Transcoding",
            file=os.path.basename(out_file),
        )
        start_time = time.time()
        # output = subprocess.run(
        #     ["ffmpeg", "-i", tmp_wav, "-ab", "320k", "-y", tmp_mp3],
        #     capture_output=True,
        # )
        try:
            ffmpeg.input(tmp_wav).output(tmp_mp3, ab="320k").run(
                overwrite_output=True, quiet=True
            )
            os.rename(tmp_mp3, out_file)
        except (Exception, KeyboardInterrupt) as e:
            try:
                os.remove(tmp_mp3)
            except OSError:
                pass
            if isinstance(e, KeyboardInterrupt):
                msg("Vocal", "Safe to Exit")
            else:
                msg(
                    "Vocal",
                    "Transcode Failed",
                    e,
                    file=os.path.basename(out_file),
                    error=True,
                )
            raise KeyboardInterrupt
        end_time = time.time()
        speed = round(duration / (end_time - start_time))
        msg("Vocal", "Transcoded", f"({speed}X)", file=os.path.basename(out_file))


if __name__ == "__main__":
    try:
        msg("Vocal", "Starting")
        for file in os.listdir(AUDIO_DIR):
            if file.endswith(".m4a"):
                extract_vocal(file)
    except KeyboardInterrupt:
        pass
