import os, shutil, json, ffmpeg, pickle
import gradio as gr
import pandas as pd
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


MAX_SLICE_NUM = 7


def load_transcript(refresh: bool = False) -> tuple[pd.DataFrame, str]:
    msg("Search", "Loading Transcripts")
    try:
        with open(os.path.join(TMP_DIR, "transcript.pkl"), "rb") as f:
            transcript = pickle.load(f)
            # return transcript, status
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


def trim(vocal: str, start: float, end: float, slice: str):
    # skip if slice already exists
    try:
        if abs(start + get_duration(slice) - end) < 1:
            return False
    except:
        pass
    return (
        ffmpeg.input(vocal)
        .output(slice, ss=start, to=end, acodec="copy")
        .run_async(overwrite_output=True, quiet=True)
    )


def search(
    transcript: pd.DataFrame,
    roomid: str,
    keyword: str,
    options: list[str],
    page: int = 1,
    join: bool = True,
):
    labels = []
    slices = []
    processes = []
    # filter transcript by roomid
    if roomid != "all":
        transcript = transcript[transcript["roomid"] == roomid]
    # filter transcript by keywords, allow multiple keywords separated by space
    for k in keyword.split():
        if "Pinyin" in options:
            transcript = transcript[
                transcript["pinyin"].str.contains(" ".join(lazy_pinyin(k)))
            ]
        else:
            transcript = transcript[transcript["text"].str.contains(k)]
    transcript = transcript.reset_index(drop=True)
    # regulate page number
    total_page = (len(transcript) - 1) // MAX_SLICE_NUM + 1
    page = max(1, min(page, total_page))
    for i in range((page - 1) * MAX_SLICE_NUM, len(transcript)):
        if len(slices) >= MAX_SLICE_NUM:
            break
        row = transcript.iloc[i]
        # trim vocal
        vocal = os.path.join(VOCAL_DIR, f"{row['basename']}.mp3")
        start = row["start"] - 3
        end = row["end"] + 3
        slice = os.path.join(
            SLICE_DIR,
            f"{row['basename']}_{row['start']:.0f}_{row['end']:.0f}_{row['text']}.mp3",
        )
        labels.append(f"# [{row['roomid']}] {row['text']}")
        if "Audio" in options:
            processes.append(trim(vocal, start, end, slice))
            msg("Search", "Trimming", file=slice)
            slices.append(slice)
        elif os.path.exists(slice):
            slices.append(slice)
        else:
            slices.append(None)
    # wait for all processes to finish if join is needed
    if join:
        for i, process in enumerate(processes):
            if not process:
                # already exists, skip
                msg("Search", "Trim Skipped", file=slices[i])
                continue
            return_code = process.wait()
            if return_code != 0:
                msg("Search", "Trim Failed", file=slice, error=True)
                labels[i] = None
                slices[i] = None
            else:
                msg("Search", "Trim Finished", file=slices[i])
        # pad to MAX_SLICE_NUM
        num_audio = len(slices)
        if num_audio < MAX_SLICE_NUM:
            labels += [None] * (MAX_SLICE_NUM - num_audio)
            slices += [None] * (MAX_SLICE_NUM - num_audio)
        # cache for next page
        search(transcript, roomid, keyword, options, page + 1, False)
        return page, total_page, *labels, *slices
    else:
        msg("Search", "Cache Running in Background")


def prev_page(
    transcript: pd.DataFrame, roomid: str, keyword: str, options: list[str], page: int
):
    return search(transcript, roomid, keyword, options, page - 1)


def next_page(
    transcript: pd.DataFrame, roomid: str, keyword: str, options: list[str], page: int
):
    return search(transcript, roomid, keyword, options, page + 1)


def cache_pages(
    transcript: pd.DataFrame, roomid: str, keyword: str, options: list[str]
) -> None:
    if "Audio" not in options:
        options.append("Audio")
    msg("Search", "Caching All Slices", "This may take a while")
    _, total_page, *_ = search(transcript, roomid, keyword, options, 1)
    msg("Search", "Cached", f"Page 1 of {total_page}")
    for page in range(2, total_page + 1):
        search(transcript, roomid, keyword, options, page)
        msg("Search", "Cached", f"Page {page} of {total_page}")


def save_to_favorite(slice: str):
    favorite = os.path.join(FAVORITE_DIR, os.path.basename(slice))
    try:
        shutil.copy(slice, favorite)
    except FileNotFoundError:
        msg("Search", "Not Found", file=slice, error=True)
        return f"Not Found {slice}"
    else:
        msg("Search", "Saved", file=favorite)
        return f"Saved to {favorite}"


if __name__ == "__main__":
    css = "footer {display: none !important;} .gradio-container {min-height: 0px !important;} .gradio-container {min-width: 0px !important;}"
    with gr.Blocks(css=css) as app:
        # load transcripts
        df, init_status = load_transcript()
        transcript = gr.State(df)
        # vocal slices
        labels = []
        slices = []
        favorite = []

        gr.Markdown("""# <center>Auto-Transcribe</center>""")
        with gr.Row():
            with gr.Column():
                refresh = gr.Button(value="Refresh Transcripts")
                cache = gr.Button(value="Cache All Slices")
                status = gr.Textbox(
                    value=init_status, label="Status", interactive=False
                )
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
                keyword = gr.Textbox(value="晚上好", label="Search For")
                submit = gr.Button(value="Search")
            with gr.Column(scale=100):
                for i in range(MAX_SLICE_NUM):
                    labels.append(gr.Markdown())
                    with gr.Row():
                        with gr.Column(scale=100):
                            slices.append(
                                gr.Audio(
                                    type="filepath",
                                    show_label=False,
                                    interactive=False,
                                )
                            )
                        favorite.append(gr.Button(value="Save to Favorites"))
                with gr.Row():
                    backward = gr.Button(value="< Previous")
                    page = gr.Number(value=0, label="Page", precision=0)
                    total_page = gr.Number(
                        value=0, label="Total", precision=0, interactive=False
                    )
                    forward = gr.Button(value="Next >")

        keyword.submit(
            search,
            [transcript, roomid, keyword, options],
            [page, total_page, *labels, *slices],
        )

        submit.click(
            search,
            [transcript, roomid, keyword, options],
            [page, total_page, *labels, *slices],
        )

        page.submit(
            search,
            [transcript, roomid, keyword, options, page],
            [page, total_page, *labels, *slices],
        )

        backward.click(
            prev_page,
            [transcript, roomid, keyword, options, page],
            [page, total_page, *labels, *slices],
        )

        forward.click(
            next_page,
            [transcript, roomid, keyword, options, page],
            [page, total_page, *labels, *slices],
        )

        for i in range(MAX_SLICE_NUM):
            favorite[i].click(save_to_favorite, slices[i], status)

        cache.click(cache_pages, [transcript, roomid, keyword, options])

        refresh.click(refresh_transcript, outputs=[transcript, status])

    app.launch(share=True)
