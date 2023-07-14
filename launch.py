import os, json, ffmpeg, pickle
import gradio as gr
import pandas as pd
from pypinyin import lazy_pinyin
from utils import (
    TRANSCRIPT_DIR,
    VOCAL_DIR,
    FAVORITE_DIR,
    TMP_DIR,
    SLICE_DIR,
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
                        tmp["text"].append(segment["text"].lower())
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


def search(
    transcript: pd.DataFrame,
    roomid: str,
    date_from: int,
    date_to: int,
    keyword: str,
    options: list[str],
    margin: float,
    page: int = 1,
):
    labels: list[str | None] = [None] * MAX_SLICE_NUM
    info: list[tuple | None] = [None] * MAX_SLICE_NUM
    slices: list[str | None] = [None] * MAX_SLICE_NUM
    waveplots: list[str | None] = [None] * MAX_SLICE_NUM
    # filter transcript by roomid
    if roomid != "all":
        transcript = transcript[transcript["roomid"] == roomid]

    # filter transcript by date
    def date_filter(base_name: str) -> bool:
        date = int(base_name.split("_")[1])
        return date_from <= date <= date_to

    transcript = transcript[transcript["basename"].apply(date_filter)]
    # filter transcript by keywords, allow multiple keywords separated by space
    if "Exact Match" in options:  # exact match
        if "Pinyin" in options:
            transcript = transcript[
                transcript["pinyin"] == " ".join(lazy_pinyin(keyword))
            ]
        else:
            transcript = transcript[transcript["text"] == keyword.lower()]
    elif "Ends With" in options:  # ends with
        if "Pinyin" in options:
            transcript = transcript[
                transcript["pinyin"].str.endswith(" ".join(lazy_pinyin(keyword)))
            ]
        else:
            transcript = transcript[transcript["text"].str.endswith(keyword.lower())]
    else:
        for k in keyword.split():
            if "Pinyin" in options:
                transcript = transcript[
                    transcript["pinyin"].str.contains(" ".join(lazy_pinyin(k)))
                ]
            else:
                transcript = transcript[transcript["text"].str.contains(k.lower())]
    # reset index
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
        labels[i] = f"# [{base_name.split('_')[0]}] {date} {text}"
        info[i] = (base_name, start, end, text)
        slice, waveplot = load_slice(base_name, start, end)
        slices[i] = slice
        waveplots[i] = waveplot
        i += 1

    return page, total_page, *labels, *info, *slices, *waveplots


def prev_page(
    transcript: pd.DataFrame,
    roomid: str,
    date_from: int,
    date_to: int,
    keyword: str,
    options: list[str],
    margin: float,
    page: int,
):
    return search(
        transcript, roomid, date_from, date_to, keyword, options, margin, page - 1
    )


def next_page(
    transcript: pd.DataFrame,
    roomid: str,
    date_from: int,
    date_to: int,
    keyword: str,
    options: list[str],
    margin: float,
    page: int,
):
    return search(
        transcript, roomid, date_from, date_to, keyword, options, margin, page + 1
    )


def save_to_favorite(info: tuple[str, float, float, str]) -> str:
    base_name, start, end, text = info
    vocal = os.path.join(VOCAL_DIR, f"{base_name}.mp3")
    favorite = os.path.join(
        FAVORITE_DIR, f"{base_name}_{start:.0f}_{end:.0f}_{text}.mp3"
    )
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

        # gr.Markdown("""# <center>Auto-Transcribe</center>""")
        with gr.Row():
            with gr.Column():
                refresh = gr.Button(value="Refresh Transcripts")
                status = gr.Textbox(
                    value=init_status, label="Status", interactive=False
                )
                roomid = gr.Dropdown(
                    choices=["all"] + sorted(df["roomid"].unique().tolist()),
                    label="Room ID",
                    value="all",
                )
                options = gr.CheckboxGroup(
                    choices=["Audio", "Pinyin", "Exact Match", "Ends With"],
                    value=["Audio"],
                    label="Options",
                )
                margin = gr.Number(
                    value=2,
                    label="Audio Margin (seconds)",
                )
                date_from = gr.Number(value=20220101, label="Date From", precision=0)
                date_to = gr.Number(value=20770101, label="Date To", precision=0)
                keyword = gr.Textbox(value="晚上好", label="Search For")
                submit = gr.Button(value="Search")
            with gr.Column(scale=100):
                for i in range(MAX_SLICE_NUM):
                    labels.append(gr.Markdown())
                    with gr.Row():
                        with gr.Column(scale=100):
                            info.append(gr.State(None))
                            audios.append(gr.Audio(show_label=False, interactive=False))
                            waveplots.append(
                                gr.Image(show_label=False, interactive=False)
                            )
                        favorite.append(
                            gr.Button(value="Save to Favorites").style(size="sm")
                        )
                with gr.Row():
                    backward = gr.Button(value="< Previous")
                    page = gr.Number(value=0, label="Page", precision=0)
                    total_page = gr.Number(
                        value=0, label="Total", precision=0, interactive=False
                    )
                    forward = gr.Button(value="Next >")

        keyword.submit(
            search,
            [transcript, roomid, date_from, date_to, keyword, options, margin],
            [page, total_page, *labels, *info, *audios, *waveplots],
        )

        submit.click(
            search,
            [transcript, roomid, date_from, date_to, keyword, options, margin],
            [page, total_page, *labels, *info, *audios, *waveplots],
        )

        page.submit(
            search,
            [transcript, roomid, date_from, date_to, keyword, options, margin, page],
            [page, total_page, *labels, *info, *audios, *waveplots],
        )

        backward.click(
            prev_page,
            [transcript, roomid, date_from, date_to, keyword, options, margin, page],
            [page, total_page, *labels, *info, *audios, *waveplots],
        )

        forward.click(
            next_page,
            [transcript, roomid, date_from, date_to, keyword, options, margin, page],
            [page, total_page, *labels, *info, *audios, *waveplots],
        )

        for i in range(MAX_SLICE_NUM):
            favorite[i].click(save_to_favorite, info[i], status)

        refresh.click(refresh_transcript, outputs=[transcript, status])

    app.launch(share=False)
