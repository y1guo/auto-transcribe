import os, json, whisper, opencc, torch, time
from multiprocessing import Process, Manager
from utils import VOCAL_DIR, TRANSCRIPT_DIR, get_duration, msg, valid


NUM_GPU = torch.cuda.device_count()


class Worker:
    def __init__(self, gpu_id: int, current_task: list[tuple[str, str]]) -> None:
        self.gpu_id = gpu_id
        self.current_task = current_task
        self.model = None
        self.converter = opencc.OpenCC("t2s.json")

    def __call__(self) -> None:
        try:
            self.main()
        except Exception as e:
            msg(f" GPU {self.gpu_id} ", "Crashed", repr(e), error=True)
        except KeyboardInterrupt:
            pass

    def main(self) -> None:
        while True:
            task = self.current_task[self.gpu_id]
            if task:
                vocal, transcript = task
                msg(f" GPU {self.gpu_id} ", "Xscribing", file=vocal)
                start_time = time.time()
                try:
                    self.transcribe(vocal, transcript)
                except (Exception, KeyboardInterrupt) as e:
                    try:
                        os.remove(transcript)
                    except:
                        pass
                    if not isinstance(e, KeyboardInterrupt):
                        msg(
                            f" GPU {self.gpu_id} ",
                            "Xscribe Crashed",
                            file=vocal,
                            error=True,
                        )
                    raise
                end_time = time.time()
                speed = get_duration(vocal) / (end_time - start_time)
                msg(
                    f" GPU {self.gpu_id} ",
                    "Xscribed",
                    f"({speed:.0f}X)",
                    file=vocal,
                )
                self.current_task[self.gpu_id] = None
            time.sleep(5)

    def transcribe(self, vocal: str, transcript: str) -> None:
        # transcribe
        if not self.model:
            msg(f" GPU {self.gpu_id} ", "Loading Model")
            self.model = whisper.load_model("large-v2", device=f"cuda:{self.gpu_id}")
            msg(f" GPU {self.gpu_id} ", "Model Loaded")
        result = self.model.transcribe(vocal, language="zh", verbose=None)
        # convert to simplified chinese
        result["text"] = self.converter.convert(result["text"])
        for segment in result["segments"]:
            segment["text"] = self.converter.convert(segment["text"])
        # save result to json file with utf-8 encoding, pretty print
        with open(transcript, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)


class Watcher:
    def __init__(self, current_task: list[tuple[str, str]]) -> None:
        self.current_task = current_task

    def __call__(self):
        try:
            self.main()
        except Exception as e:
            msg("Watcher", "Crashed", repr(e), error=True)
        except KeyboardInterrupt:
            pass

    def main(self) -> None:
        while True:
            # set new tasks to idle workers
            for id in range(len(self.current_task)):
                if not self.current_task[id]:
                    self.current_task[id] = self.new_task()
            time.sleep(5)

    def new_task(self) -> tuple[str, str] | None:
        for file in os.listdir(VOCAL_DIR):
            if file.endswith(".mp3"):
                base_name = os.path.splitext(file)[0]
                vocal = os.path.join(VOCAL_DIR, file)
                transcript = os.path.join(TRANSCRIPT_DIR, f"{base_name}.json")
                task = (vocal, transcript)
                # return task if vocal is valid (prerequisite) and valid transcript not exist (job) and not being worked on (job)
                if (
                    valid(base_name, "vocal")
                    and not valid(base_name, "transcript")
                    and task not in self.current_task
                ):
                    return task


def main() -> None:
    msg("Xscribe", "Starting")
    with Manager() as manager:
        # init processes
        current_task = manager.list([None] * NUM_GPU)
        watcher = Process(target=Watcher(current_task))
        watcher.start()
        workers = []
        for i in range(NUM_GPU):
            current_task[i] = None
            worker = Process(target=Worker(NUM_GPU - 1 - i, current_task))
            worker.start()
            workers.append(worker)
        # wait for processes to finish
        while True:
            if not watcher.is_alive():
                msg("Xscribe", "Restarting", "Watcher")
                watcher = Process(target=Watcher(current_task))
                watcher.start()
            for i in range(NUM_GPU):
                if not workers[i].is_alive():
                    msg("Xscribe", "Restarting", f"GPU {NUM_GPU - 1 - i}")
                    workers[i] = Process(target=Worker(NUM_GPU - 1 - i, current_task))
                    workers[i].start()
            time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        msg("Xscribe", "Crashed", repr(e), error=True)
    except KeyboardInterrupt:
        msg("Xscribe", "Safe to Exit")
