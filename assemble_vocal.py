import os, time, ffmpeg, torchaudio
from utils import (
    VOCAL_DIR,
    TMP_DIR,
    DEMUCS_DIR,
    get_duration,
    msg,
    valid,
    get_audio_parts,
)


def assemble_vocal(file: str) -> None:
    base_name = file.split("_vocals.wav")[0]
    bare_name = base_name.split("_part_")[0]
    vocal = os.path.join(VOCAL_DIR, f"{bare_name}.mp3")
    audio_parts = get_audio_parts(bare_name)
    wav_parts = [
        os.path.join(
            DEMUCS_DIR,
            f"{os.path.splitext(os.path.basename(f))[0]}_vocals.wav",
        )
        for f in audio_parts
    ]
    # skip if any of the wav parts is not valid (prerequisite) or valid vocal already exists (job)
    if not all(
        valid(os.path.splitext(os.path.basename(f))[0], "demucs") for f in audio_parts
    ) or valid(base_name, "vocal"):
        return
    # start assembling
    msg(
        "Vocal",
        "Assembling",
        file=vocal,
    )
    start_time = time.time()
    # assemble from wav in tmp dir to mp3 in vocal dir
    TMP_FILE = os.path.join(TMP_DIR, "filelist.txt")
    with open(TMP_FILE, "w") as f:
        for wav_part in wav_parts:
            mp3_part = wav_part[:-4] + ".mp3"
            wav, sr = torchaudio.load(wav_part)  # type: ignore
            torchaudio.save(mp3_part, wav, sr, compression=-1.5)  # type: ignore
            f.write(f"file '{mp3_part}'\n")
    time.sleep(1)
    # concat mp3 parts
    try:
        ffmpeg.input(TMP_FILE, format="concat", safe=0).output(
            vocal, acodec="copy"
        ).run(overwrite_output=True, quiet=True)
    except (Exception, KeyboardInterrupt) as e:
        try:
            os.remove(vocal)
        except:
            pass
        if isinstance(e, Exception):
            msg(
                "Vocal",
                "Assemble Failed",
                file=vocal,
                error=True,
            )
        raise
    end_time = time.time()
    speed = get_duration(vocal) / (end_time - start_time)
    msg("Vocal", "Assembled", f"({speed:.0f}X)", file=vocal)


if __name__ == "__main__":
    try:
        msg("Vocal", "Scanning")
        for file in os.listdir(DEMUCS_DIR):
            if (
                os.path.exists(os.path.join(DEMUCS_DIR, file))
                and file.endswith("_vocals.wav")
                and not file.endswith("_no_vocals.wav")
            ):
                assemble_vocal(file)
    except KeyboardInterrupt:
        msg("Vocal", "Safe to Exit")
    except Exception as e:
        msg("Vocal", type(e).__name__, str(e), error=True)
        raise
