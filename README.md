# auto-transcribe
Server Pipeline that Transcribes Videos on Detection Unattended

## Environment

```bash
# create a new virtual environment
conda create -n auto-transcribe python=3.10
conda activate auto-transcribe

# install dependencies
pip install -r requirements.txt

# install ffmpeg from conda
conda install ffmpeg

# or through apt
sudo apt install ffmpeg
```

## Workflow

Extract audio from recordings and prepare for vocal extraction (slice into pieces of <= 1 hour for memory issue)

```bash
bash keep_running.sh "python extract_audio.py"
```

Extract vocal with Facebook `Demucs`

```bash
bash keep_running.sh "python extract_vocal.py"
```

Assemble pieces back into whole

```bash
bash keep_running.sh "python assenble_vocal.py"
```

Transcribe with OpenAI `whisper`

```bash
python transcribe.py
```

Monitor the workflow and sanity check

```bash
bash keep_running.sh "python summary.py" 60
```

## Notes

-   Demucs VRAM issue

    The larger `SEGMENT` is, the higher VRAM will be used.

-   Demucs RAM issue

    Demucs spent ~110GB RAM while processing a 12.5h audio. This can be solved by splitting the original audio into 
    pieces of 1 hour, and concatenate afterwards.

-   Speed

    Demucs (`htdemucs`) vocal extraction is about 20~30X real time, i.e., 1 hour audio = 2.5 mins processing.

    Whisper (`large-v2`) transcription is about 4~8X real world speed, i.e., 1 hours audio = 10 mins processing.

    Tested on RTX4090 and RTX3080Ti. Demucs respects TFlops more, while Whisper performs the same on these two cards.

-   Suppress Numba Warning

    If seeing warning from `numba` about some deprecated usage when importing or calling `whisper`, downgrading to 
    `numba==0.56.4` solves the problem.
