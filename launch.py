import os, json, ffmpeg, pickle, time, torch, torchaudio
import gradio as gr
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from multiprocessing import Process, Pool
from pypinyin import lazy_pinyin
from utils import (
    TRANSCRIPT_DIR,
    VOCAL_DIR,
    SLICE_DIR,
    FAVORITE_DIR,
    TMP_DIR,
    msg,
    get_duration,
)


MAX_SLICE_NUM = 6


def load_transcript(refresh: bool = False) -> tuple[pd.DataFrame, str]:
    msg("Search", "Loading Transcripts")
    transcript = pd.DataFrame()
    try:
        if refresh:
            raise FileNotFoundError
        with open(os.path.join(TMP_DIR, "transcript.pkl"), "rb") as f:
            transcript: pd.DataFrame = pickle.load(f)
    except FileNotFoundError:
        tmp = {k: [] for k in ["roomid", "basename", "start", "end", "text", "pinyin"]}
        for file in sorted(os.listdir(TRANSCRIPT_DIR)):
            if file.endswith(".json"):
                with open(os.path.join(TRANSCRIPT_DIR, file)) as f:
                    base_name = os.path.splitext(file)[0]
                    roomid = base_name.split("_")[0]
                    for segment in json.load(f)["segments"]:
                        tmp["roomid"].append(roomid)
                        tmp["basename"].append(base_name)
                        tmp["start"].append(segment["start"])
                        tmp["end"].append(segment["end"])
                        tmp["text"].append(segment["text"])
                        tmp["pinyin"].append(" ".join(lazy_pinyin(segment["text"])))
        transcript = pd.DataFrame(tmp)
        with open(os.path.join(TMP_DIR, "transcript.pkl"), "wb") as f:
            pickle.dump(transcript, f)
    finally:
        status = f"Loaded {len(transcript)} transcripts"
        msg("Search", "Loading Transcripts Finished")
        return transcript, status


def refresh_transcript() -> tuple[pd.DataFrame, str]:
    return load_transcript(refresh=True)


def trim(vocal: str, start: float, end: float, slice: str, bitrate: str):
    # skip if slice already exists
    try:
        if abs(start + get_duration(slice) - end) < 1:
            return
    except:
        pass
    return (
        ffmpeg.input(vocal)
        .output(slice, ss=start, to=end, ab=bitrate)
        .run_async(overwrite_output=True, quiet=True)
        # ffmpeg.input(vocal, ss=start, to=end)
        # .output(slice, ab=bitrate)
        # .run_async(overwrite_output=True, quiet=True)
    )


def get_waveplot(waveform: np.ndarray, sample_rate: int, file: str):
    msg("Search", "Get Waveplot", file=file)
    time_axis = []
    samples = []
    for i in range(0, len(waveform), 100):
        time_axis.append(i / sample_rate)
        samples.append(waveform[i : i + 100].max())
        time_axis.append((i + 50) / sample_rate)
        samples.append(waveform[i : i + 100].min())
    fig = plt.figure(figsize=(20, 1), facecolor="black")
    plt.plot(time_axis, samples, color="white")
    plt.xlim(min(time_axis), max(time_axis))
    amp = max(abs(min(samples)), abs(max(samples)))
    plt.ylim(-amp, amp)
    plt.axis("off")
    return fig


def load_slice(base_name: str, start: float, end: float, text: str) -> tuple[np.ndarray, int, Figure]:
    vocal = os.path.join(VOCAL_DIR, f"{base_name}.mp3")
    slice = os.path.join(SLICE_DIR, f"{base_name}_{start:.0f}_{end:.0f}.mp3")
    wav = os.path.join(TMP_DIR, f"{base_name}_{start:.0f}_{end:.0f}.wav")
    waveform = torch.zeros((1, 44100))
    sample_rate = 44100

    exists = False
    try:
        if abs(start + get_duration(slice) - end) < 1:
            exists = True
    except:
        raise

    try:
        if exists:
            # load existing slice if it's valid
            msg("Search", "Loading", file=slice)
            ffmpeg.input(slice).output(wav).run(overwrite_output=True, quiet=True)
            waveform, sample_rate = torchaudio.load(wav)  # type: ignore
            os.remove(wav)
        else:
            # else trim vocal
            msg("Search", "Trimming", file=slice)
            ffmpeg.input(vocal).output(wav, ss=start, to=end).run(overwrite_output=True, quiet=True)
            waveform, sample_rate = torchaudio.load(vocal)  # type: ignore
            os.remove(wav)
            torchaudio.save(slice, waveform, sample_rate)  # type: ignore
    except Exception as e:
        msg("Search", type(e).__name__, str(e), file=slice)

    arr = np.array(waveform.numpy().T * 2**16, dtype=np.int16)
    assert len(arr.shape) == 2
    return arr, sample_rate, get_waveplot(arr.mean(axis=1), sample_rate, slice)


def search(
    transcript: pd.DataFrame,
    roomid: str,
    keyword: str,
    options: list[str],
    margin: float,
    page: int = 1,
    join: bool = True,
):
    labels: list[str | None] = [None] * MAX_SLICE_NUM
    info: list[tuple | None] = [None] * MAX_SLICE_NUM
    slices: list[tuple | None] = [None] * MAX_SLICE_NUM
    waveplots: list[Figure | None] = [None] * MAX_SLICE_NUM
    # filter transcript by roomid
    if roomid != "all":
        transcript = transcript[transcript["roomid"] == roomid]
    # filter transcript by keywords, allow multiple keywords separated by space, use "" for exact match
    if (
        keyword.startswith('"')
        and keyword.endswith('"')
        or keyword.startswith("'")
        and keyword.endswith("'")
        or keyword.startswith("“")
        and keyword.endswith("”")
        or keyword.startswith("‘")
        and keyword.endswith("’")
    ):
        transcript = transcript[transcript["text"] == keyword[1:-1]]
    else:
        for k in keyword.split():
            if "Pinyin" in options:
                transcript = transcript[transcript["pinyin"].str.contains(" ".join(lazy_pinyin(k)))]
            else:
                transcript = transcript[transcript["text"].str.contains(k)]
    transcript = transcript.reset_index(drop=True)
    # regulate page number
    total_page = (len(transcript) - 1) // MAX_SLICE_NUM + 1
    page = max(1, min(page, total_page))
    i = 0
    for j in range((page - 1) * MAX_SLICE_NUM, len(transcript)):
        if i == MAX_SLICE_NUM:
            break
        row = transcript.iloc[j]
        base_name: str = row["basename"]
        start: float = max(row["start"] - margin, 0)
        end: float = row["end"] + margin
        text: str = row["text"]
        s = base_name.split("_")[1]
        date = s[:4] + "/" + s[4:6] + "/" + s[6:8]
        labels[i] = f"# [{roomid}] {date} {text}"
        slice_file = os.path.join(SLICE_DIR, f"{base_name}_{start:.0f}_{end:.0f}.mp3")
        if "Audio" in options or os.path.exists(slice_file):
            info[i] = (base_name, start, end, text)
        i += 1
    # wait for all processes to finish if join is needed
    if join:
        args = [item for item in info if item is not None]
        with Pool(len(args)) as pool:
            res = pool.starmap(load_slice, args)
            i = 0
            for j in range(len(info)):
                if info[j] is not None:
                    wave_arr, sample_rate, waveplot = res[i]
                    slices[j] = (sample_rate, wave_arr)
                    waveplots[j] = waveplot
                    i += 1
        # cache for next page
        search(transcript, roomid, keyword, options, margin, page + 1, False)
    else:
        msg("Search", "Cache Running in Background")
    return page, total_page, *labels, *info, *slices, *waveplots


def prev_page(
    transcript: pd.DataFrame,
    roomid: str,
    keyword: str,
    options: list[str],
    margin: float,
    page: int,
):
    return search(transcript, roomid, keyword, options, margin, page - 1)


def next_page(
    transcript: pd.DataFrame,
    roomid: str,
    keyword: str,
    options: list[str],
    margin: float,
    page: int,
):
    return search(transcript, roomid, keyword, options, margin, page + 1)


def cache_all_slices(transcript: pd.DataFrame, margin: float) -> None:
    def save_slice(waveform: torch.Tensor, sample_rate: int, path: str) -> None:
        msg("Cache", "Saving", file=path)
        torchaudio.save(path, waveform, sample_rate)  # type: ignore

    msg("Search", "Caching All Slices", "This may take a long long while")
    num_proc = torch.multiprocessing.cpu_count()
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
            slice = os.path.join(SLICE_DIR, f"{base_name}_{start:.0f}_{end:.0f}.mp3")
            if not os.path.exists(slice):
                rows.append((start, end, slice))
        if not rows:
            with open(VALIDLIST, "a") as f:
                f.write(base_name + "\n")
            continue
        # convert mp3 to wav
        wav = os.path.join(TMP_DIR, f"{base_name}.wav")
        try:
            if abs(get_duration(vocal) - get_duration(wav)) < 1:
                pass
            else:
                raise Exception
        except:
            msg("Cache", "mp3 to wav", file=vocal)
            ffmpeg.input(vocal).output(wav).run(quiet=True, overwrite_output=True)
        finally:
            msg("Cache", "Loading", file=wav)
            waveform, sample_rate = torchaudio.load(wav)  # type: ignore
        # save slices
        for start, end, slice in rows:
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
        try:
            os.remove(wav)
        except:
            pass


def save_to_favorite(info: tuple[str, float, float, str]) -> str:
    base_name, start, end, text = info
    vocal = os.path.join(VOCAL_DIR, f"{base_name}.mp3")
    favorite = os.path.join(FAVORITE_DIR, f"{base_name}_{start:.0f}_{end:.0f}_{text}.mp3")
    try:
        trim(vocal, start, end, favorite, "320k")
    except FileNotFoundError:
        msg("Search", "Not Found", file=vocal, error=True)
        return f"Not Found {vocal}"
    else:
        msg("Search", "Saved", file=favorite)
        return f"Saved to {favorite}"


if __name__ == "__main__":
    css = "footer {display: none !important;} .gradio-container {min-height: 0px !important;} .gradio-container {min-width: 0px !important;}"
    with gr.Blocks(
        css=css,
        theme=gr.themes.Default(spacing_size=gr.themes.sizes.spacing_sm),
    ) as app:
        # load transcripts
        df, init_status = load_transcript()
        transcript = gr.State(df)
        # vocal slices
        labels = []
        info = []
        audios = []
        waveplots = []
        favorite = []

        gr.Markdown("""# <center>Auto-Transcribe</center>""")
        with gr.Row():
            with gr.Column():
                refresh = gr.Button(value="Refresh Transcripts")
                cache = gr.Button(value="Cache All Slices")
                status = gr.Textbox(value=init_status, label="Status", interactive=False)
                roomid = gr.Dropdown(
                    choices=["all"] + sorted(df["roomid"].unique().tolist()),
                    label="Room ID",
                    value="all",
                )
                options = gr.CheckboxGroup(
                    choices=["Audio", "Pinyin"],
                    value=["Audio"],
                    label="Options",
                )
                margin = gr.Number(
                    value=1,
                    label="Audio Margin (seconds)",
                )
                keyword = gr.Textbox(value="晚上好", label="Search For")
                submit = gr.Button(value="Search")
            with gr.Column(scale=100):
                for i in range(MAX_SLICE_NUM):
                    labels.append(gr.Markdown())
                    with gr.Row():
                        with gr.Column(scale=100):
                            info.append(gr.State(None))
                            audios.append(
                                gr.Audio(
                                    show_label=False,
                                    interactive=False,
                                )
                            )
                            waveplots.append(gr.Plot(show_label=False))
                        favorite.append(gr.Button(value="Save to Favorites").style(size="sm"))
                with gr.Row():
                    backward = gr.Button(value="< Previous")
                    page = gr.Number(value=0, label="Page", precision=0)
                    total_page = gr.Number(value=0, label="Total", precision=0, interactive=False)
                    forward = gr.Button(value="Next >")

        keyword.submit(
            search,
            [transcript, roomid, keyword, options, margin],
            [page, total_page, *labels, *info, *audios, *waveplots],
        )

        submit.click(
            search,
            [transcript, roomid, keyword, options, margin],
            [page, total_page, *labels, *info, *audios, *waveplots],
        )

        page.submit(
            search,
            [transcript, roomid, keyword, options, margin, page],
            [page, total_page, *labels, *info, *audios, *waveplots],
        )

        backward.click(
            prev_page,
            [transcript, roomid, keyword, options, margin, page],
            [page, total_page, *labels, *info, *audios, *waveplots],
        )

        forward.click(
            next_page,
            [transcript, roomid, keyword, options, margin, page],
            [page, total_page, *labels, *info, *audios, *waveplots],
        )

        for i in range(MAX_SLICE_NUM):
            favorite[i].click(save_to_favorite, info[i], status)

        cache.click(cache_all_slices, [transcript, margin])

        refresh.click(refresh_transcript, outputs=[transcript, status])

    app.launch(share=False)
