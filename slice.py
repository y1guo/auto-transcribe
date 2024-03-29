import os, torch, torchaudio, pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from multiprocessing import Pool
from utils import (
    VOCAL_DIR,
    SLICE_DIR,
    TMP_DIR,
    msg,
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


def save_slice(waveform: torch.Tensor, sample_rate: int, path: str) -> None:
    msg("Cache", "Saving", file=path)
    torchaudio.save(path, waveform, sample_rate, compression=-9.5)  # type: ignore
    fig = get_waveplot(waveform.numpy().T, sample_rate)
    fig.savefig(path.replace(".mp3", ".jpg"))
    plt.close(fig)


def cache_all_slices(transcript: pd.DataFrame, margin: float) -> None:
    msg("Search", "Caching All Slices", "This may take a long long while")
    num_proc = torch.multiprocessing.cpu_count()
    # num_proc = 1
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
            if not os.path.exists(slice) or not os.path.exists(
                slice.replace(".mp3", ".jpg")
            ):
                rows.append((start, end, slice))
        if not rows:
            with open(VALIDLIST, "a") as f:
                f.write(base_name + "\n")
            continue
        # load mp3
        msg("Cache", "Loading", file=vocal)
        waveform, sample_rate = torchaudio.load(vocal)  # type: ignore
        # save slices
        args = []
        for start, end, slice in rows:
            # sanity check
            start_frame = int(start * sample_rate)
            end_frame = int(end * sample_rate)
            if start_frame > waveform.shape[1]:
                msg(
                    "Slice",
                    "Warning",
                    f"Skipping start = {start:.0f} > duration",
                    file=slice,
                )
                continue
            if end_frame > waveform.shape[1]:
                end_frame = waveform.shape[1]
            # debug start
            if waveform[:, start_frame : end_frame + 1].nelement() == 0:
                print("empty waveform:", slice)
            # debug end
            args.append(
                (
                    waveform[:, start_frame : end_frame + 1],
                    sample_rate,
                    slice,
                )
            )
        with Pool(num_proc) as p:
            p.starmap(save_slice, args)
    msg("Cache", "Done")


if __name__ == "__main__":
    with open(os.path.join(TMP_DIR, "transcript.pkl"), "rb") as f:
        transcript: pd.DataFrame = pickle.load(f)
        cache_all_slices(transcript, 2)
