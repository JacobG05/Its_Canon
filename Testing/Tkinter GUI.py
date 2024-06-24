import tkinter as tk
import requests

# Function to send commands to the bot
def send_command(command, url=None):
    if url:
        requests.get(f"http://localhost:8000/command/{command}?url={url}")
    else:
        requests.get(f"http://localhost:8000/command/{command}")

# Function to update the song title
def update_now_playing():
    response = requests.get("http://localhost:8000/command/nowplaying")
    now_playing_label.config(text=response.text)
    root.after(5000, update_now_playing)  # Update every 5 seconds

root = tk.Tk()
root.title("Discord Music Bot")

url_entry = tk.Entry(root)
url_entry.pack()

play_button = tk.Button(root, text="Play", command=lambda: send_command("play", url_entry.get()))
play_button.pack()

pause_button = tk.Button(root, text="Pause", command=lambda: send_command("pause"))
pause_button.pack()

resume_button = tk.Button(root, text="Resume", command=lambda: send_command("resume"))
resume_button.pack()

skip_button = tk.Button(root, text="Skip", command=lambda: send_command("skip"))
skip_button.pack()

stop_button = tk.Button(root, text="Stop", command=lambda: send_command("stop"))
stop_button.pack()

now_playing_label = tk.Label(root, text="Now playing: None")
now_playing_label.pack()

update_now_playing()

root.mainloop()
