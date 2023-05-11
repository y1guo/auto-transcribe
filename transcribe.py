import os, json, whisper, opencc, multiprocessing, torch
from utils import VOCAL_DIR, TRANSCRIPT_DIR, msg


def transcribe(in_file: str, out_file: str) -> None:
    msg("Transcribe", "Transcribing", os.path.basename(in_file))
    # get device id
    cpu_name = multiprocessing.current_process().name
    cpu_id = int(cpu_name.split("-")[1]) - 1
    try:
        # load model
        model = whisper.load_model("large-v2", device=f"cuda:{cpu_id}")
        # transcribe
        result = model.transcribe(in_file, language="zh")
        # convert to simplified chinese
        converter = opencc.OpenCC("t2s.json")
        result["text"] = converter.convert(result["text"])
        for segment in result["segments"]:
            segment["text"] = converter.convert(segment["text"])
        # save result to json file with utf-8 encoding, pretty print
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        # print success
        msg("Transcribe", "Saved", os.path.basename(out_file))
    except Exception as e:
        # print error
        msg("Transcribe", "Error", repr(e), error=True)
        msg("Transcribe", "Failed", os.path.basename(in_file), error=True)


if __name__ == "__main__":
    # detect new vocal files
    vocal_list = []
    for file in os.listdir(VOCAL_DIR):
        if file.endswith(".mp3"):
            base_name = os.path.splitext(file)[0]
            in_file = os.path.join(VOCAL_DIR, file)
            out_file = os.path.join(TRANSCRIPT_DIR, f"{base_name}.json")
            # add to list if transcript does not exist
            if not os.path.exists(out_file):
                vocal_list.append((in_file, out_file))
    # transcribe new vocal files
    pool = multiprocessing.Pool(torch.cuda.device_count())
    pool.starmap(transcribe, vocal_list)
