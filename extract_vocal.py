import os, subprocess, shutil
from utils import AUDIO_DIR, VOCAL_DIR, TMP_DIR, EXCLUDELIST, get_duration, msg


def extract_vocal(file: str) -> None:
    base_name = os.path.splitext(file)[0]
    bare_name = base_name.split("_part_")[0]
    in_file = os.path.join(AUDIO_DIR, file)
    out_file = os.path.join(VOCAL_DIR, f"{bare_name}.mp3")
    tmp_file = os.path.join(TMP_DIR, "htdemucs", base_name, "vocals.wav")
    duration = get_duration(in_file)
    # skip if audio has not finished writing
    if not duration:
        return
    # skip if vocal already exists
    if os.path.exists(out_file):
        return
    # skip if in exclude list
    if os.path.exists(EXCLUDELIST):
        with open(EXCLUDELIST) as f:
            exclude_list = f.read().splitlines()
        if file in exclude_list:
            return
    # extract vocal to tmp if vocal does not exist
    if not os.path.exists(tmp_file):
        msg("Vocal", "Extracting", f"{base_name}.wav")
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
            msg("Vocal", "Extracted", f"{base_name}.wav")
        # failed, add to exclude list
        else:
            with open(EXCLUDELIST, "a") as f:
                f.write(f"{file}\n")
            msg("Vocal", "Failed Extract", f"{base_name}.wav", error=True)
    # move or merge vocal from tmp dir to vocal dir
    if "_part_" in base_name:
        # skip if it is not the last part
        if round(duration) == 3600:
            return
        # skip if not all parts are present
        part_number = int(base_name.split("_part_")[1])
        part_files = [
            os.path.join(
                TMP_DIR, "htdemucs", f"{base_name[:-2]}{1+i:02d}", "vocals.wav"
            )
            for i in range(part_number)
        ]
        for part_file in part_files:
            if not os.path.exists(part_file):
                return
        # merge vocal
        TMP_FILE = os.path.join(TMP_DIR, "filelist.txt")
        with open(TMP_FILE, "w") as f:
            for part_file in part_files:
                f.write(f"file '{part_file}'\n")
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
                out_file,
            ],
            capture_output=True,
        )
        # succeeded
        if output.returncode == 0:
            # remove tmp dir
            for part_file in part_files:
                shutil.rmtree(os.path.dirname(part_file))
            msg("Vocal", "Merged", f"{bare_name}.mp3")
        # failed
        else:
            msg("Vocal", "Failed Merge", f"{bare_name}.mp3", error=True)
    else:
        output = subprocess.run(
            ["ffmpeg", "-i", tmp_file, "-ab", "320k", "-y", out_file],
            capture_output=True,
        )
        # succeeded
        if output.returncode == 0:
            # remove tmp dir
            shutil.rmtree(os.path.dirname(tmp_file))
            msg("Vocal", "Transcoded", f"{bare_name}.mp3")
        # failed
        else:
            msg("Vocal", "Failed Transcode", f"{bare_name}.mp3", error=True)


if __name__ == "__main__":
    for file in os.listdir(AUDIO_DIR):
        if file.endswith(".m4a"):
            extract_vocal(file)
