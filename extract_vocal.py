import os, time, subprocess
from utils import (
    AUDIO_DIR,
    TMP_DIR,
    DEMUCS_DIR,
    EXCLUDELIST,
    get_duration,
    msg,
    valid,
    get_audio_parts,
)


def extract_vocal(file: str) -> None:
    base_name = os.path.splitext(file)[0]
    audio = os.path.join(AUDIO_DIR, file)
    wav = os.path.join(DEMUCS_DIR, f"{base_name}_vocals.wav")
    wav_no_vocal = os.path.join(DEMUCS_DIR, f"{base_name}_no_vocals.wav")
    # skip if in exclude list
    try:
        with open(EXCLUDELIST) as f:
            exclude_list = f.read().splitlines()
        if file in exclude_list:
            return
    except FileNotFoundError:
        pass
    # skip if audio is not valid (prerequisite) or either valid vocal or wav already exists (job)
    if (
        not valid(base_name, "audio")
        or valid(base_name, "vocal")
        or valid(base_name, "demucs")
    ):
        return
    # extract vocal wav to tmp
    msg("Demucs", "Extracting", file=audio)
    audio_duration = get_duration(audio)
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
                "--filename",
                "{track}_{stem}.{ext}",
                audio,
            ],
            capture_output=True,
        )
        if output.returncode != 0:
            raise Exception((output.stdout + output.stderr).decode())
        os.remove(wav_no_vocal)
    except (Exception, KeyboardInterrupt) as e:
        for f in [wav, wav_no_vocal]:
            try:
                os.remove(f)
            except:
                pass
        if isinstance(e, Exception):
            msg(
                "Demucs",
                "Extract Failed",
                file=audio,
                error=True,
            )
            # problem might be because there's no speech in the audio, exclude the audio if duration is small
            if audio_duration < 300:
                with open(EXCLUDELIST, "a") as f:
                    f.write(f"{file}\n")
                msg("Demucs", "Excluded", file=audio, error=True)
        raise
    end_time = time.time()
    speed = get_duration(wav) / (end_time - start_time)
    msg(
        "Demucs",
        "Extracted",
        f"({speed:.0f}X)",
        file=audio,
    )
    # continue to extract the rest parts if there are any
    audio_parts = get_audio_parts(bare_name)
    for f in audio_parts:
        extract_vocal(os.path.basename(f))


if __name__ == "__main__":
    try:
        msg("Demucs", "Scanning")
        # finish those in the tmp dir first
        for tmp_file in os.listdir(DEMUCS_DIR):
            if tmp_file.endswith("_vocals.wav"):
                bare_name = (
                    os.path.basename(tmp_file)
                    .split("_vocals.wav")[0]
                    .split("_part_")[0]
                )
                audio_parts = get_audio_parts(bare_name)
                for f in audio_parts:
                    extract_vocal(os.path.basename(f))
        for file in os.listdir(AUDIO_DIR):
            # then those in the audio dir
            if file.endswith(".m4a"):
                extract_vocal(file)
    except KeyboardInterrupt:
        msg("Demucs", "Safe to Exit")
    except Exception as e:
        if "RuntimeError: CUDA error: out of memory" in str(e):
            msg("Demucs", "RuntimeError", "CUDA out of memory", error=True)
        else:
            msg("Demucs", type(e).__name__, e, error=True)
            if hasattr(e, "stdout"):
                msg("Demucs", "STDOUT", e.stdout.decode(), error=True)
            if hasattr(e, "stderr"):
                msg("Demucs", "STDERR", e.stderr.decode(), error=True)
            raise
