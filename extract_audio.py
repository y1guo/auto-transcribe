# Extract audio from video files in the directory list.
# If the audio is longer than 1 hour, split it into 1 hour parts.
# Audio files that are already in the directory are skipped.

import os, time, subprocess
from utils import VIDEO_DIR_LIST, AUDIO_DIR, PART_DURATION, get_duration, msg


def extract_audio(dir: str, file: str) -> None:
    base_name = os.path.splitext(file)[0]
    in_file = os.path.join(dir, file)
    duration = get_duration(in_file)
    # skip if audio has not finished writing
    if not duration:
        return
    # if the video is longer than 1 hour, split it into 1 hour parts
    if round(duration) > PART_DURATION:
        num_part = int(duration // PART_DURATION) + 1
        part_files = [
            os.path.join(AUDIO_DIR, f"{base_name}_part_{1+i:02d}.m4a")
            for i in range(num_part)
        ]
        for i, out_file in enumerate(part_files):
            # extract audio if it does not exist
            if not os.path.exists(out_file):
                msg("Audio", "Extracting", os.path.basename(out_file))
                output = subprocess.run(
                    [
                        "ffmpeg",
                        "-i",
                        in_file,
                        "-ss",
                        f"{i * PART_DURATION}",
                        "-t",
                        f"{PART_DURATION}",
                        "-vn",
                        "-acodec",
                        "copy",
                        out_file,
                        "-y",
                    ],
                    capture_output=True,
                )
                # succeeded
                if output.returncode == 0:
                    msg("Audio", "Extracted", os.path.basename(out_file))
                # failed
                else:
                    msg(
                        "Audio",
                        "Failed Extract",
                        os.path.basename(out_file),
                        error=True,
                    )
    else:
        out_file = os.path.join(AUDIO_DIR, f"{base_name}.m4a")
        # extract audio if it does not exist
        if not os.path.exists(out_file):
            msg("Audio", "Extracting", os.path.basename(out_file))
            output = subprocess.run(
                ["ffmpeg", "-i", in_file, "-vn", "-acodec", "copy", out_file, "-y"],
                capture_output=True,
            )
            # succeeded
            if output.returncode == 0:
                msg("Audio", "Extracted", os.path.basename(out_file))
            # failed
            else:
                msg("Audio", "Failed Extract", os.path.basename(out_file), error=True)


if __name__ == "__main__":
    for video_dir in VIDEO_DIR_LIST:
        for file in os.listdir(video_dir):
            if file.endswith(".mp4") or file.endswith(".flv"):
                extract_audio(video_dir, file)
