#FFMPEG Testing
import subprocess

try:
    subprocess.run(['ffmpeg', '-version'], check=True)
    print("FFmpeg is installed and working.")
except subprocess.CalledProcessError:
    print("FFmpeg is not installed correctly.")
