import os
import sounddevice as sd
import numpy as np
import tkinter as tk
import wavio
import threading
from datetime import datetime

# Parameters
RATE = 44100    # samples per second
DTYPE = np.int16 # data type

# Auto-detect the number of channels supported by the default input device
def get_input_channels():
    try:
        device_info = sd.query_devices(kind='input')
        channels = int(device_info['max_input_channels'])
        return min(channels, 2) if channels >= 1 else 1
    except Exception:
        return 1

CHANNELS = get_input_channels()

# Directory for saving the recording (based on script's location)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIRECTORY = os.path.join(SCRIPT_DIR, "Recordings")

# Ensure the directory exists
if not os.path.exists(DIRECTORY):
    os.makedirs(DIRECTORY)

# Global recording array
recording = None

# Flag to control the recording cycle
continue_recording = True

# Callback function to be called every time the buffer is full
def callback(indata, frames, time, status):
    global recording
    recording = np.append(recording, indata, axis=0)

# Start recording from microphone
def start():
    global recording, continue_recording
    while continue_recording:
        recording = np.empty((0, CHANNELS), dtype=DTYPE)
        print("Start recording...")
        stream = sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype=DTYPE, callback=callback)
        with stream:
            tk_root.wait_variable(var)

        # Stop recording and save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(DIRECTORY, f"{timestamp}.wav")
        print("Stop recording...")
        wavio.write(filename, recording, RATE, sampwidth=2)
        print(f"Saved recording to {filename}")

        # Play back the recording
        print("Playing back the recording...")
        sd.play(recording, RATE)
        sd.wait()

# Stop the entire script
def stop_script():
    global continue_recording
    continue_recording = False
    var.set(1)
    print("Stopped the script.")
    tk_root.quit()

# Function to be run in a separate thread
def recording_thread():
    start()

# Create a GUI window
tk_root = tk.Tk()
tk_root.title("Microphone Recorder")

# Start button
start_button = tk.Button(tk_root, text="Start", command=lambda: threading.Thread(target=recording_thread, daemon=True).start())
start_button.pack()

# Stop button
stop_button = tk.Button(tk_root, text="Stop", command=stop_script)
stop_button.pack()

# Create a variable to communicate between main and recording threads
var = tk.IntVar()

# Bind the space key to the stop function for recording only
tk_root.bind('<space>', lambda event: var.set(1))

# Run the GUI loop
tk_root.mainloop()
