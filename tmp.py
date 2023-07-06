import torchaudio, os
from utils import *


def load_audio(path):
    return torchaudio.load(path)  # type: ignore


waveform, sample_rate = load_audio(os.path.join(TMP_DIR, "12962_20230401_045123_玩MC.wav"))
print(waveform.shape, sample_rate)
