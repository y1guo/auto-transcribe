import os, ffmpeg, time, torch, torchaudio, pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from multiprocessing import Process
from utils import (
    VOCAL_DIR,
    SLICE_DIR,
    TMP_DIR,
    msg,
    get_duration,
)


def get_waveplot(waveform: np.ndarray, sample_rate: int, file: str = ""):
    if file:
        msg("Search", "Get Waveplot", file=file)
    time_axis = []
    samples = []
    for i in range(0, len(waveform), 100):
        time_axis.append(i / sample_rate)
        samples.append(waveform[i : i + 100].max())
        time_axis.append((i + 50) / sample_rate)
        samples.append(waveform[i : i + 100].min())
    fig = plt.figure(figsize=(20, 1), facecolor="black", dpi=48)
    if samples:
        plt.plot(time_axis, samples, color="white")
        plt.xlim(min(time_axis), max(time_axis))
        amp = max(abs(min(samples)), abs(max(samples))) + 1e-9
        plt.ylim(-amp, amp)
    else:
        plt.plot([0, 1], [0, 0], color="white")
        plt.xlim(0, 1)
        plt.ylim(-1, 1)
    plt.axis("off")
    return fig


def load_slice(base_name: str, start: float, end: float) -> tuple[str | None, str | None]:
    slice = os.path.join(SLICE_DIR, base_name, f"{base_name}_{start:.0f}_{end:.0f}.mp3")
    waveplot = slice.replace(".mp3", ".jpg")
    # check if slice exists and valid
    try:
        if abs(start + get_duration(slice) - end) < 2:
            pass
        else:
            slice = "placeholder_slice.mp3"
    except:
        slice = "placeholder_slice.mp3"
    # check if waveplot exists
    try:
        if os.path.exists(waveplot):
            pass
        else:
            waveplot = "placeholder_waveplot.jpg"
    except:
        waveplot = "placeholder_waveplot.jpg"
    # print message
    if slice:
        msg("Search", "Slice Loaded", file=slice)
    if waveplot:
        msg("Search", "Plot Loaded", file=waveplot)

    return slice, waveplot


def cache_all_slices(transcript: pd.DataFrame, margin: float) -> None:
    def save_slice(waveform: torch.Tensor, sample_rate: int, path: str) -> None:
        msg("Cache", "Saving", file=path)
        torchaudio.save(path, waveform, sample_rate)  # type: ignore
        try:
            fig = get_waveplot(waveform.numpy().T, sample_rate)
            fig.savefig(path.replace(".mp3", ".jpg"))
        except ValueError:
            print("waveform:", waveform)
            raise

    msg("Search", "Caching All Slices", "This may take a long long while")
    num_proc = torch.multiprocessing.cpu_count()
    # num_proc = 1
    processes: list[Process | None] = [None] * num_proc
    skip_list = []
    VALIDLIST = os.path.join(TMP_DIR, "valid_slices.txt")
    try:
        with open(VALIDLIST) as f:
            skip_list = f.read().splitlines()
    except:
        pass
    for base_name in transcript["basename"].unique():
        vocal = os.path.join(VOCAL_DIR, f"{base_name}.mp3")
        slice_dir = os.path.join(SLICE_DIR, base_name)
        if not os.path.exists(slice_dir):
            os.makedirs(slice_dir)
        # skip if already cached
        msg("Cache", "Checking", file=vocal)
        # check valid list
        if base_name in skip_list:
            continue
        # else check cached slices
        rows = []
        for _, row in transcript[transcript["basename"] == base_name].iterrows():
            start = max(row["start"] - margin, 0)
            end = row["end"] + margin
            slice = os.path.join(slice_dir, f"{base_name}_{start:.0f}_{end:.0f}.mp3")
            if not os.path.exists(slice) or not os.path.exists(slice.replace(".mp3", ".jpg")):
                rows.append((start, end, slice))
        if not rows:
            with open(VALIDLIST, "a") as f:
                f.write(base_name + "\n")
            continue
        # load mp3
        msg("Cache", "Loading", file=vocal)
        waveform, sample_rate = torchaudio.load(vocal)  # type: ignore
        # save slices
        for start, end, slice in rows:
            # debug start
            if waveform[:, int(start * sample_rate) : int(end * sample_rate)].nelement() == 0:
                print("empty waveform:", slice)
            # debug end
            done = False
            while True:
                for i, p in enumerate(processes):
                    if not p or not p.is_alive():
                        p = Process(
                            target=save_slice,
                            args=(waveform[:, int(start * sample_rate) : int(end * sample_rate)], sample_rate, slice),
                        )
                        p.start()
                        processes[i] = p
                        done = True
                        break
                if done:
                    break
                time.sleep(0.01)
    msg("Cache", "Done")


if __name__ == "__main__":
    with open(os.path.join(TMP_DIR, "transcript.pkl"), "rb") as f:
        transcript: pd.DataFrame = pickle.load(f)
        cache_all_slices(transcript, 2)
