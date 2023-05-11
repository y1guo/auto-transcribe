import os, subprocess, shutil
from utils import AUDIO_DIR, VOCAL_DIR, TMP_DIR, EXCLUDELIST, get_duration, msg


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
    # skip if vocal already exists and is not broken
    if os.path.exists(out_file) and get_duration(out_file):
        return
    # skip if in exclude list
    if os.path.exists(EXCLUDELIST):
        with open(EXCLUDELIST) as f:
            exclude_list = f.read().splitlines()
        if file in exclude_list:
            return
    # extract vocal to tmp if vocal does not exist or is broken
    if not os.path.exists(tmp_wav) or not get_duration(tmp_wav):
        msg("Vocal", "Extracting", os.path.join(base_name, "vocals.wav"))
        output = subprocess.run(
            [
                "demucs",
                "--two-stems",
                "vocals",
                "--shifts",
                "5",
                "-o",
                TMP_DIR,
                in_file,
            ],
            capture_output=True,
        )
        # succeeded
        if output.returncode == 0:
            msg("Vocal", "Extracted", os.path.join(base_name, "vocals.wav"))
        # failed, add to exclude list
        else:
            with open(EXCLUDELIST, "a") as f:
                f.write(f"{file}\n")
            msg(
                "Vocal",
                "Failed Extract",
                os.path.join(base_name, "vocals.wav"),
                error=True,
            )
    # move or merge vocal from tmp dir to vocal dir
    if "_part_" in base_name:
        # skip if it is not the last part
        if round(duration) == 3600:
            return
        # skip if not all parts are present and not broken
        part_number = int(base_name.split("_part_")[1])
        part_files = [
            os.path.join(
                TMP_DIR, "htdemucs", f"{base_name[:-2]}{1+i:02d}", "vocals.wav"
            )
            for i in range(part_number)
        ]
        for part_file in part_files:
            if not os.path.exists(part_file) or not get_duration(part_file):
                return
        # merge vocal
        TMP_FILE = os.path.join(TMP_DIR, "filelist.txt")
        with open(TMP_FILE, "w") as f:
            for part_file in part_files:
                f.write(f"file '{part_file}'\n")
        msg(
            "Vocal",
            "Merging",
            os.path.basename(out_file),
        )
        output = subprocess.run(
            [
                "ffmpeg",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                TMP_FILE,
                "-ab",
                "320k",
                "-y",
                tmp_mp3,
            ],
            capture_output=True,
        )
        os.rename(tmp_mp3, out_file)
        # succeeded
        if output.returncode == 0:
            # remove tmp dir
            for part_file in part_files:
                shutil.rmtree(os.path.dirname(part_file))
            msg("Vocal", "Merged", os.path.basename(out_file))
        # failed
        else:
            msg("Vocal", "Failed Merge", os.path.basename(out_file), error=True)
    else:
        msg(
            "Vocal",
            "Transcoding",
            os.path.basename(out_file),
        )
        output = subprocess.run(
            ["ffmpeg", "-i", tmp_wav, "-ab", "320k", "-y", tmp_mp3],
            capture_output=True,
        )
        os.rename(tmp_mp3, out_file)
        # succeeded
        if output.returncode == 0:
            # remove tmp dir
            shutil.rmtree(os.path.dirname(tmp_wav))
            msg("Vocal", "Transcoded", os.path.basename(out_file))
        # failed
        else:
            msg("Vocal", "Failed Transcode", os.path.basename(out_file), error=True)


if __name__ == "__main__":
    for file in os.listdir(AUDIO_DIR):
        if file.endswith(".m4a"):
            extract_vocal(file)
