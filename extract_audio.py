# Extract audio from video files in the directory list.
# If the audio is longer than 1 hour, split it into 1 hour parts.
# Audio files that are already in the directory are skipped.

import os, time
from colorama import Fore
from utils import VIDEO_DIR_LIST, AUDIO_DIR, PART_DURATION, get_duration


def extract_audio(file: str) -> None:
    base_name = os.path.splitext(file)[0]
    duration = get_duration(f"{video_dir}/{file}")
    # if the video is longer than 1 hour, split it into 1 hour parts
    if round(duration) > PART_DURATION:
        for i in range(int(duration // PART_DURATION) + 1):
            out_file = f"{base_name}_part_{1+i:02d}.m4a"
            if not os.path.exists(f"{AUDIO_DIR}/{out_file}"):
                os.system(
                    f'ffmpeg -i "{video_dir}/{file}" -ss {i * PART_DURATION} -t {PART_DURATION} -vn -acodec copy'
                    f'"{AUDIO_DIR}/{out_file}" -v quiet -y'
                )
                print(
                    f'{Fore.GREEN}[{time.strftime("%m-%d %H:%M:%S", time.localtime())} Audio]',
                    f"{Fore.YELLOW}Extracted",
                    f"{Fore.RESET}{out_file}",
                )
    else:
        out_file = f"{base_name}.m4a"
        if not os.path.exists(f"{AUDIO_DIR}/{out_file}"):
            os.system(
                f'ffmpeg -i "{video_dir}/{file}" -vn -acodec copy "{AUDIO_DIR}/{out_file}" -v quiet -y'
            )
            print(
                f'{Fore.GREEN}[{time.strftime("%m-%d %H:%M:%S", time.localtime())} Audio]',
                f"{Fore.YELLOW}Extracted",
                f"{Fore.RESET}{out_file}",
            )


if __name__ == "__main__":
    for video_dir in VIDEO_DIR_LIST:
        for file in os.listdir(video_dir):
            if file.endswith(".mp4") or file.endswith(".flv"):
                extract_audio(file)
