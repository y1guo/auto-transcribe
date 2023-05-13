import os, json, whisper, opencc, torch, time
from multiprocessing import Process, Queue, Manager
from utils import VOCAL_DIR, TRANSCRIPT_DIR, get_duration, msg, valid


NUM_GPU = torch.cuda.device_count()


class Package:
    def __init__(self, message: str, data: any = None, sender: str = "") -> None:
        self.message = message
        self.data = data
        self.sender = sender


class Worker:
    def __init__(self, gpu_id: int, queue_in: Queue, queue_out: Queue) -> None:
        self.gpu_id = gpu_id
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.model = None
        self.converter = opencc.OpenCC("t2s.json")

    def __call__(self) -> None:
        # msg(f" GPU {self.gpu_id} ", "Wait for 5 seconds to crash")
        # time.sleep(5)
        # raise Exception("Test Crash")
        while True:
            self.send(Package("ready"))
            package = self.listen()
            if package.data:
                self.send(Package("onto", package.data))
                vocal, transcript = package.data
                msg(f" GPU {self.gpu_id} ", "Xscribing", file=vocal)
                start_time = time.time()
                try:
                    self.transcribe(vocal, transcript)
                except Exception as e:
                    try:
                        os.remove(transcript)
                    except:
                        pass
                    msg(
                        f" GPU {self.gpu_id} ",
                        "Xscribe Failed",
                        repr(e),
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

    def listen(self) -> Package:
        """Wait for a package to arrive"""
        package = self.queue_in.get()
        # msg(f" GPU {self.gpu_id} ", "Received", package.message)
        return package

    def send(self, package: Package) -> None:
        package.sender = str(self.gpu_id)
        self.queue_out.put(package)
        # msg(f" GPU {self.gpu_id} ", "Sent", package.message)

    def transcribe(self, vocal: str, transcript: str) -> None:
        # transcribe
        if not self.model:
            msg(f" GPU {self.gpu_id} ", "Loading Model")
            self.model = whisper.load_model("large-v2", device=f"cuda:{self.gpu_id}")
            msg(f" GPU {self.gpu_id} ", "Model Loaded")
        result = self.model.transcribe(vocal, language="zh", verbose=False)
        # convert to simplified chinese
        result["text"] = self.converter.convert(result["text"])
        for segment in result["segments"]:
            segment["text"] = self.converter.convert(segment["text"])
        # save result to json file with utf-8 encoding, pretty print
        with open(transcript, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)


class Watcher:
    def __init__(self, queue_in: Queue, queue_out: Queue) -> None:
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.current_task = {str(i): "init" for i in range(NUM_GPU)}

    def __call__(self):
        while True:
            # update worker status
            for package in self.receive():
                if package.message == "onto":
                    self.current_task[package.sender] = package.data
                elif package.message == "ready":
                    self.current_task[package.sender] = None
            # send new task to an idle worker
            for worker in self.current_task:
                if not self.current_task[worker]:
                    self.send(Package("task", self.new_task()))
                    break
            # allow some time for the worker to accept task
            time.sleep(5)

    def receive(self) -> list[Package]:
        """Grab all packages in queue, no waiting"""
        packages = []
        while not self.queue_in.empty():
            packages.append(self.queue_in.get())
            # msg("Watcher", "Received", packages[-1].message)
        return packages

    def send(self, package: Package) -> None:
        self.queue_out.put(package)
        # msg("Watcher", "Sent", package.message)

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
                    and task not in self.current_task.values()
                ):
                    return task


if __name__ == "__main__":
    msg("Xscribe", "Starting")
    # init processes
    m2w = Queue()
    w2m = Queue()
    processes = []
    for i in range(NUM_GPU - 1, -1, -1):
        processes.append(Process(target=Worker(i, m2w, w2m)))
    processes.append(Process(target=Watcher(w2m, m2w)))
    for p in processes:
        p.start()
    # wait for processes to finish
    try:
        for p in processes:
            p.join()
        # while True:
        #     time.sleep(10)
    except KeyboardInterrupt:
        for p in processes:
            p.terminate()
        msg("Xstribe", "Safe to Exit")
