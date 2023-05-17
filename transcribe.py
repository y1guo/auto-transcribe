import os, sys, json, whisper, opencc, torch, time
from multiprocessing import Process, Manager
from io import StringIO
from utils import VOCAL_DIR, TRANSCRIPT_DIR, TMP_DIR, get_duration, msg, valid


NUM_GPU = torch.cuda.device_count()


class TqdmOut(StringIO):
    def __init__(self, state) -> None:
        super().__init__()
        self.state = state

    def write(self, s: str) -> None:
        super().write(s)
        line = self.getvalue().split("\r")[-1]
        try:
            s2d = lambda s: sum(
                int(n) * 60**i for i, n in enumerate(reversed(s.split(":")))
            )
            d2s = lambda d: ":".join(
                [f"{int(d // 60**i % 60):02d}" for i in range(2, -1, -1)]
            )
            percentage = line.split("%")[0]
            finished = int(line.split("/")[0].split(" ")[-1]) // 100
            total = int(line.split("/")[1].split(" ")[0]) // 100
            elapsed = s2d(line.split("[")[1].split("<")[0])
            speed = finished / elapsed
            eta = (total - finished) / speed
            self.state[
                "progress"
            ] = f"[{percentage:>3}% {speed:3.1f}X {d2s(elapsed)} <- {d2s(eta)}]"
        except Exception as e:
            self.state["progress"] = "n/a"


class Worker:
    def __init__(
        self,
        gpu_id: int,
        state: dict,
    ) -> None:
        self.gpu_id = gpu_id
        self.state = state
        self.model = None
        self.converter = opencc.OpenCC("t2s.json")

    def __call__(self) -> None:
        try:
            self.main()
        except Exception as e:
            msg(f" GPU {self.gpu_id} ", "Crashed", repr(e), error=True)
            raise
        except KeyboardInterrupt:
            pass

    def main(self) -> None:
        while True:
            if self.state["task"]:
                vocal, transcript = self.state["task"]
                msg(f" GPU {self.gpu_id} ", "Xscribing", file=vocal)
                start_time = time.time()
                try:
                    self.transcribe(vocal, transcript)
                except (Exception, KeyboardInterrupt) as e:
                    try:
                        os.remove(transcript)
                    except:
                        pass
                    if isinstance(e, Exception):
                        msg(
                            f" GPU {self.gpu_id} ",
                            "transcribe() Crashed",
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
                self.state["task"] = None
                self.state["progress"] = "n/a"
            time.sleep(5)

    def transcribe(self, vocal: str, transcript: str) -> None:
        # transcribe
        if not self.model:
            msg(f" GPU {self.gpu_id} ", "Loading Model")
            self.model = whisper.load_model("large-v2", device=f"cuda:{self.gpu_id}")
            msg(f" GPU {self.gpu_id} ", "Model Loaded")
        # redirect tqdm progress bar to state
        with TqdmOut(self.state) as tqdm_out:
            sys.stderr = tqdm_out
            result = self.model.transcribe(vocal, language="zh", verbose=False)
            sys.stderr = sys.__stderr__
        # convert to simplified chinese
        result["text"] = self.converter.convert(result["text"])
        for segment in result["segments"]:
            segment["text"] = self.converter.convert(segment["text"])
        # save result to json file with utf-8 encoding, pretty print
        with open(transcript, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)


class Watcher:
    def __init__(self, states: list[dict]) -> None:
        self.states = states

    def __call__(self):
        try:
            self.main()
        except Exception as e:
            msg("Watcher", "Crashed", repr(e), error=True)
            raise
        except KeyboardInterrupt:
            pass

    def main(self) -> None:
        while True:
            # set new tasks to idle workers
            for state in self.states:
                if not state["task"]:
                    state["task"] = self.new_task()
            time.sleep(5)

    def new_task(self) -> tuple[str, str] | None:
        for file in os.listdir(VOCAL_DIR):
            if file.endswith(".mp3"):
                base_name = os.path.splitext(file)[0]
                vocal = os.path.join(VOCAL_DIR, file)
                transcript = os.path.join(TRANSCRIPT_DIR, f"{base_name}.json")
                task = (vocal, transcript)
                # return task if vocal is valid (prerequisite) and valid transcript not exist (job) and not being worked on (job)
                current_tasks = [state["task"] for state in self.states]
                if (
                    valid(base_name, "vocal")
                    and not valid(base_name, "transcript")
                    and task not in current_tasks
                ):
                    return task


def main() -> None:
    msg("Xscribe", "Starting")
    with Manager() as manager:
        # init processes
        states = manager.list(
            [manager.dict({"task": None, "progress": "n/a"}) for _ in range(NUM_GPU)]
        )
        watcher = Process(target=Watcher(states))
        workers = [Process(target=Worker(i, states[i])) for i in range(NUM_GPU)]
        # start processes
        watcher.start()
        # start workers in reverse order as GPU0 might has been occupied by Demucs
        for i in range(NUM_GPU - 1, -1, -1):
            workers[i].start()
        # wait for processes to finish
        while True:
            # print progress
            msg(
                "Xscribe",
                "Progress",
                " ".join(
                    [f'GPU {i} {states[i]["progress"]:<32}' for i in range(NUM_GPU)]
                ),
                end="\r",
            )
            # keep processes alive
            if not watcher.is_alive():
                msg("Xscribe", "Restarting", "Watcher")
                watcher = Process(target=Watcher(states))
                watcher.start()
            for i in range(NUM_GPU - 1, -1, -1):
                if not workers[i].is_alive():
                    msg("Xscribe", "Restarting", f"GPU {i}")
                    workers[i] = Process(target=Worker(i, states[i]))
                    workers[i].start()
            time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        msg("Xscribe", type(e).__name__, e, error=True)
        if hasattr(e, "stdout"):
            msg("Xscribe", "STDOUT", e.stdout.decode(), error=True)
        if hasattr(e, "stderr"):
            msg("Xscribe", "STDERR", e.stderr.decode(), error=True)
        raise
    except KeyboardInterrupt:
        msg("Xscribe", "Safe to Exit")
