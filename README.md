# bilirec-transcribe
Pipeline for Transcribing BiliRec Recordings

## Development Environment

```bash
# create a new virtual environment
conda create -n bilirec-transcribe python=3.10
conda activate bilirec-transcribe

# install dependencies
pip install -r requirements.txt

# install ffmpeg either way
conda install ffmpeg    # from conda
sudo apt install ffmpeg # from apt
```

## Workflow

-   Extract audio from recordings and prepare for vocal extraction

    ```bash
    bash keep_running.sh "python extract_audio.py"
    ```

-   Extract vocal with Facebook `Demucs`

    ```bash
    bash keep_running.sh "python extract_vocal.py"
    ```

-   Transcribe with OpenAI `whisper`

    ```bash
    bash keep_running.sh "python transcribe.py"
    ```

-   Monitor the workflow and sanity check

    ```bash
    bash keep_running.sh "python validate.py" 60
    ```

## Notes

-   Ultimate Vocal Remover 5 (Windows) GPU Selection

    UVR uses `cuda:0` in `pytorch`. However, the GPU order in `pytorch` is different from that of
    `nvidia-smi`. That's because `pytorch` order is by default `FASTEST_FIRST` while `nvidia-smi` and windows task
    mangaer use `PCI_BUS_ID`. To set the `pytorch` GPU order, add `CUDA_DEVICE_ORDER = PCI_BUS_ID` in the windows 
    environment variables in the advanced settings.

-   Demucs Insufficient RAM / VRAM

    Set `SEGMENT` to `1` could lower the VRAM requirement. The `Default` is probably prettly large. For audio of about
    an hour, `Default` requires less than `3GB` of VRAM. 

    In terms of RAM, audio of duration >7 hours will overflow my 96GB RAM. This can be solved by splitting original
    audio into pieces of 1 hour, and concatenate afterwards.

-   Speed Comparison

    UVR vocal extraction is much faster (2 ~ 5 X) than Whisper (`large-v2`) transcription .

    Whisper (`large-v2`) transcription time is about 6 X real-world speed, i.e., 1 hours audio = 10 mins computation
    on an RTX4090.

-   Suppress Numba Warning

    If seeing warning from `numba` about some deprecated usage when importing or calling `whisper`, downgrading to 
    `numba==0.56.4` might solve the problem.
