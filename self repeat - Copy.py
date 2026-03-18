import sounddevice as sd
import numpy as np
import tkinter as tk
import wavio
import threading
from datetime import datetime

# Parameters
RATE = 44100    # samples per second
CHANNELS = 2    # number of channels
DTYPE = np.int16 # data type

# Directory for saving the recording
DIRECTORY = "C:\\Users\\Komp_i7\\Documents\\coding\\Python\\Audio_self_repeat2\\Recordings\\"

# Global recording array
recording = None

# Callback function to be called every time the buffer is full
def callback(indata, frames, time, status):
    global recording
    recording = np.append(recording, indata, axis=0)

# Start recording from microphone
def start():
    global recording
    recording = np.empty((0, CHANNELS), dtype=DTYPE)
    print("Start recording...")
    stream = sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype=DTYPE, callback=callback)
    with stream:
        tk_root.wait_variable(var)

# Stop recording and save to file
def stop():
    global recording
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = DIRECTORY + timestamp + ".wav"
    print("Stop recording...")
    wavio.write(filename, recording, RATE, sampwidth=2)
    print(f"Saved recording to {filename}")
    var.set(1)

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
stop_button = tk.Button(tk_root, text="Stop", command=stop)
stop_button.pack()

# Create a variable to communicate between main and recording threads
var = tk.IntVar()

# Bind the space key to the stop function
tk_root.bind('<space>', lambda event: stop())

# Run the GUI loop
tk_root.mainloop()
