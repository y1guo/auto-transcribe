import os, json, whisper, opencc, torch, time
import multiprocessing as mp
from utils import VOCAL_DIR, TRANSCRIPT_DIR, get_duration, msg


class Worker:
    def __init__(self, gpu_id: int, queue: mp.Queue) -> None:
        self.gpu_id = gpu_id
        self.queue = queue
        self.model = None
        self.converter = opencc.OpenCC("t2s.json")

    def __call__(self) -> None:
        while True:
            in_file, out_file = self.queue.get()
            msg(f" GPU {self.gpu_id} ", "Transcribing", file=os.path.basename(in_file))
            start_time = time.time()
            try:
                self.transcribe(in_file, out_file)
            except Exception as e:
                msg(
                    f" GPU {self.gpu_id} ",
                    "Transcribe Failed",
                    e,
                    file=os.path.basename(in_file),
                    error=True,
                )
            end_time = time.time()
            speed = round(get_duration(in_file) / (end_time - start_time))
            msg(
                f" GPU {self.gpu_id} ",
                "Transcribed",
                f"({speed}X)",
                file=os.path.basename(in_file),
            )

    def transcribe(self, in_file: str, out_file: str) -> None:
        # load model
        if not self.model:
            self.model = whisper.load_model("large-v2", device=f"cuda:{self.gpu_id}")
        # transcribe
        result = self.model.transcribe(in_file, language="zh")
        # convert to simplified chinese
        result["text"] = self.converter.convert(result["text"])
        for segment in result["segments"]:
            segment["text"] = self.converter.convert(segment["text"])
        # save result to json file with utf-8 encoding, pretty print
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)


class Watcher:
    def __init__(self, queue: mp.Queue):
        self.queue = queue
        self.vocals = set()

    def __call__(self):
        while True:
            # detect new vocal files
            for file in os.listdir(VOCAL_DIR):
                if file.endswith(".mp3"):
                    self.check(file)
            time.sleep(10)

    def check(self, file: str) -> None:
        base_name = os.path.splitext(file)[0]
        in_file = os.path.join(VOCAL_DIR, file)
        out_file = os.path.join(TRANSCRIPT_DIR, f"{base_name}.json")
        # add to queue if transcript does not exist nor in queue
        if not os.path.exists(out_file) and not base_name in self.vocals:
            self.vocals.add(base_name)
            self.queue.put((in_file, out_file))
            msg("Watcher", "Queued", file=os.path.basename(in_file))


if __name__ == "__main__":
    msg("Transcribe", "Starting")
    # init processes
    queue = mp.Queue()
    processes = []
    for i in range(torch.cuda.device_count() - 1, -1, -1):
        processes.append(mp.Process(target=Worker(i, queue)))
    processes.append(mp.Process(target=Watcher(queue)))
    # start processes
    for p in processes:
        p.start()
    # wait for processes to finish
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        for p in processes:
            p.terminate()
        msg("Transcribe", "Safe to Exit")
