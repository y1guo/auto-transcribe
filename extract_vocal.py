import os, time, subprocess, torch
from multiprocessing import Process, Manager
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


def skip(file: str) -> bool:
    msg("Demucs", "Checking", file=file, end="\r")
    base_name = os.path.splitext(file)[0]
    # skip if in exclude list
    try:
        with open(EXCLUDELIST) as f:
            exclude_list = f.read().splitlines()
        if file in exclude_list:
            return True
    except FileNotFoundError:
        pass
    # skip if audio is not valid (prerequisite) or either valid vocal or wav already exists (job)
    if not valid(base_name, "audio") or valid(base_name, "vocal") or valid(base_name, "demucs"):
        return True
    return False


def extract_vocal(id: int, file: str) -> None:
    base_name = os.path.splitext(file)[0]
    audio = os.path.join(AUDIO_DIR, file)
    wav = os.path.join(DEMUCS_DIR, f"{base_name}_vocals.wav")
    wav_no_vocal = os.path.join(DEMUCS_DIR, f"{base_name}_no_vocals.wav")
    # extract vocal wav to tmp
    msg(f"Worker{id}", "Extracting", file=audio)
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
                "-d",
                f"cuda:{torch.cuda.device_count() - 1 - id}",
                audio,
            ],
            capture_output=True,
        )
        if output.returncode != 0:
            raise Exception((output.stdout + output.stderr).decode())
    except (Exception, KeyboardInterrupt) as e:
        for f in [wav, wav_no_vocal]:
            try:
                os.remove(f)
            except:
                pass
        if isinstance(e, Exception):
            msg(
                f"Worker{id}",
                "Extract Failed",
                file=audio,
                error=True,
            )
            # problem might be because there's no speech in the audio, exclude the audio if duration is small
            if audio_duration < 300:
                with open(EXCLUDELIST, "a") as f:
                    f.write(f"{file}\n")
                msg(f"Worker{id}", "Excluded", file=audio, error=True)
        raise
    else:
        end_time = time.time()
        speed = get_duration(wav) / (end_time - start_time)
        msg(
            f"Worker{id}",
            "Extracted",
            f"({speed:.0f}X)",
            file=audio,
        )
    finally:
        try:
            os.remove(wav_no_vocal)
        except:
            pass


def work(id: int, last_run: list[float], file: str) -> None:
    try:
        while time.time() - max(last_run) < 0:
            msg(f"Worker{id}", "Waiting", file=file, end="\r")
            time.sleep(1)
        last_run[id] = time.time()
        extract_vocal(id, file)
    except KeyboardInterrupt:
        msg(f"Worker{id}", "Safe to Exit")
    except Exception as e:
        if "RuntimeError: CUDA error: out of memory" in str(e):
            msg(f"Worker{id}", "RuntimeError", "CUDA out of memory", error=True)
        else:
            msg(f"Worker{id}", type(e).__name__, str(e), error=True)
            raise
    finally:
        last_run[id] = 0


def run(file: str) -> None:
    while True:
        for i, p in enumerate(processes):
            if not p or not p.is_alive():
                worker = Process(target=work, args=(i, last_run, file))
                worker.start()
                processes[i] = worker
                return
        time.sleep(0.01)


if __name__ == "__main__":
    msg("Demucs", "Scanning")
    NUM_PROC = torch.cuda.device_count()
    processes: list[Process | None] = [None] * NUM_PROC
    with Manager() as manager:
        last_run = manager.list([0] * NUM_PROC)
        check_tmp = True
        for file in os.listdir(AUDIO_DIR):
            # finish those in the tmp dir first
            if check_tmp:
                bare_names = set()
                for tmp_file in os.listdir(DEMUCS_DIR):
                    if tmp_file.endswith("_vocals.wav") and not tmp_file.endswith("_no_vocals.wav"):
                        bare_name = os.path.basename(tmp_file).split("_vocals.wav")[0].split("_part_")[0]
                        bare_names.add(bare_name)
                for bare_name in bare_names:
                    audio_parts = get_audio_parts(bare_name)
                    for f in audio_parts:
                        if not skip(os.path.basename(f)):
                            run(os.path.basename(f))
                check_tmp = False
            # then those in the audio dir
            if file.endswith(".m4a"):
                if not skip(file):
                    run(file)
                    check_tmp = True
