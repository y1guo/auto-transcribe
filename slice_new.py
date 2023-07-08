import os, torch, torchaudio, pickle, time
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from multiprocessing import Process, Manager
from utils import (
    VOCAL_DIR,
    SLICE_DIR,
    TMP_DIR,
    msg,
    get_duration,
)


def load_slice(
    base_name: str, start: float, end: float
) -> tuple[str | None, str | None]:
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


class Worker:
    def __init__(self, state):
        self.state = state

    def __call__(self):
        plt.figure(figsize=(20, 1), facecolor="black", dpi=48)
        while True:
            wav = self.state["wav"]
            sr = self.state["sr"]
            path = self.state["path"]
            if path == "stop":
                break
            elif path:
                msg("Cache", "Saving", file=path)
                # save audio
                torchaudio.save(path, wav, sr)  # type: ignore
                # save waveplot
                time_axis = []
                samples = []
                wav = wav.numpy().T
                for i in range(0, len(wav), 100):
                    time_axis.append(i / sr)
                    samples.append(wav[i : i + 100].max())
                    time_axis.append((i + 50) / sr)
                    samples.append(wav[i : i + 100].min())
                plt.clf()
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
                plt.savefig(path.replace(".mp3", ".jpg"))
                # signal that we are done
                self.state["path"] = None
        plt.close()


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
    with Manager() as manager:
        states = [
            manager.dict({"wav": None, "sr": None, "path": None})
            for _ in range(num_proc)
        ]
        processes = [Process(target=Worker(state)) for state in states]
        for process in processes:
            process.start()
        # loop over all vocal files
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
                slice = os.path.join(
                    slice_dir, f"{base_name}_{start:.0f}_{end:.0f}.mp3"
                )
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
            for start, end, slice in rows:
                wav = waveform[:, int(start * sample_rate) : int(end * sample_rate)]
                # debug start
                if wav.nelement() == 0:
                    print("empty waveform:", slice)
                # debug end
                finished = False
                while not finished:
                    for state in states:
                        if not state["path"]:
                            state["wav"] = wav
                            state["sr"] = sample_rate
                            state["path"] = slice
                            finished = True
                            break
        # signal workers to stop
        for state in states:
            state["path"] = "stop"
        for process in processes:
            process.join()
    msg("Cache", "Done")


if __name__ == "__main__":
    transcript = pd.DataFrame()
    with open(os.path.join(TMP_DIR, "transcript.pkl"), "rb") as f:
        transcript: pd.DataFrame = pickle.load(f)
    cache_all_slices(transcript[transcript["roomid"] == "92613"], 2)
    cache_all_slices(transcript[transcript["roomid"] == "47867"], 2)
    cache_all_slices(transcript, 2)
