import sys
import subprocess
import os

# Auto-install missing dependencies
def check_and_install_dependencies():
    """Check for required packages and install if missing"""
    required_packages = {
        'pygame': 'pygame',
        'pyaudio': 'pyaudio',
        'scipy': 'scipy',
        'pydub': 'pydub',
        'azure.cognitiveservices.speech': 'azure-cognitiveservices-speech'
    }
    
    missing_packages = []
    
    for import_name, pip_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(pip_name)
    
    if missing_packages:
        print(f"Missing packages detected: {', '.join(missing_packages)}")
        print("Installing missing packages...")
        
        for package in missing_packages:
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"Successfully installed {package}")
            except subprocess.CalledProcessError as e:
                print(f"Error installing {package}: {e}")
                print(f"Please manually install {package} using: pip install {package}")
        
        print("All required packages have been installed. Restarting application...")
        # Restart the script to load newly installed modules
        os.execv(sys.executable, [sys.executable] + sys.argv)

# Run dependency check before importing other modules
check_and_install_dependencies()

import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox
import pygame
import pyaudio
from scipy.io.wavfile import write
import shutil
import datetime
import wave
import configparser
import re
import time
import webbrowser
from pydub import AudioSegment

class App:
    def __init__(self, root):
        pygame.mixer.init()

        self.root = root
        root.geometry("273x480")  # Increased height for mic volume slider
        
        # Dictionary to store phrase mappings
        self.phrases_dict = {}

        self.config = configparser.ConfigParser()

        # Get the directory of the script and the absolute path of the config file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(script_dir, 'config.ini')

        self.config.read(self.config_path)

        self.audio_files = []  # Audio files that are to be played
        self.rounds = []  # A list of rounds where each round is a list of audio files
        self.current_round = []  # The current round of audio files being played
        self.current_file = ""  # Current file being played
        self.playing = False  # Flag to check if audio is playing or not
        self.mode = "Play"  # Current mode of the App

        # User field
        self.user_label = tk.Label(root, text="User")
        self.user_label.pack()
        self.user_entry = tk.Entry(root)
        self.user_entry.pack()

        # Repeat X times field (formerly Clones)
        self.clones_label = tk.Label(root, text="Repeat X times")
        self.clones_label.pack()
        self.clones_entry = tk.Entry(root)
        self.clones_entry.pack()

        # Phrases in a cycle field (formerly Round Quantity)
        self.rq_label = tk.Label(root, text="Phrases in a cycle")
        self.rq_label.pack()
        self.rq_entry = tk.Entry(root)
        self.rq_entry.pack()

        # Repeat cycle field (formerly Round Repeat Number)
        self.rrn_label = tk.Label(root, text="Repeat cycle")
        self.rrn_label.pack()
        self.rrn_entry = tk.Entry(root)
        self.rrn_entry.pack()

        # Give me more time percentage field
        self.gmt_label = tk.Label(root, text="Give me more time (%)")
        self.gmt_label.pack()
        self.gmt_entry = tk.Entry(root)
        self.gmt_entry.pack()

        # Subtitles checkbox
        self.show_subtitles = tk.BooleanVar(value=False)
        self.subtitles_checkbox = tk.Checkbutton(root, text="Show Subtitles", variable=self.show_subtitles, command=self.toggle_subtitles)
        self.subtitles_checkbox.pack(pady=5)

        # Subtitle text field (initially hidden)
        self.subtitle_text = tk.Text(root, height=3, width=30, wrap=tk.WORD, state=tk.DISABLED, bg='#f0f0f0')
        self.subtitle_text.pack_forget()  # Hide initially

        # Microphone volume control
        self.mic_volume_frame = tk.Frame(root)
        self.mic_volume_frame.pack(pady=5)
        
        self.mic_volume_label = tk.Label(self.mic_volume_frame, text="Mic Volume:", font=("Arial", 9))
        self.mic_volume_label.pack(side=tk.LEFT, padx=5)
        
        # Volume slider (0-200%, default 100%)
        self.mic_volume = tk.DoubleVar(value=100.0)
        self.mic_volume_slider = tk.Scale(
            self.mic_volume_frame,
            from_=0,
            to=200,
            orient=tk.HORIZONTAL,
            variable=self.mic_volume,
            command=self.update_mic_volume_label,
            length=150,
            showvalue=0
        )
        self.mic_volume_slider.pack(side=tk.LEFT)
        
        self.mic_volume_value_label = tk.Label(self.mic_volume_frame, text="100%", font=("Arial", 9), width=5)
        self.mic_volume_value_label.pack(side=tk.LEFT, padx=5)

        # Start, Stop, Load, and Export buttons       
        self.load_button = tk.Button(root, text='Load', command=self.load)
        self.load_button.pack(pady=(10, 10))  # Add some space above the button

        self.create_sounds_button = tk.Button(root, text='Create New Sounds', command=self.open_create_sounds_window, bg='lightblue')
        self.create_sounds_button.pack(pady=3)  # Add button for creating new sounds

        self.start_button = tk.Button(root, text='Start', command=self.start)
        self.start_button.pack(pady=3)  # Add some space above and below the button

        self.stop_button = tk.Button(root, text='Stop', command=self.stop)
        self.stop_button.pack(pady=3)  # Add some space above and below the button

        self.export_button = tk.Button(root, text='Export {enter}', command=self.export)
        self.export_button.pack(pady=(10, 15))  # Add some space above the button


        root.bind('<Return>', lambda event: self.export_button.invoke())  # Bind Enter key to the button's command

        if 'DEFAULT' in self.config:
            default_config = self.config['DEFAULT']
            self.rq_entry.insert(0, default_config.get('RQ', ''))
            self.rrn_entry.insert(0, default_config.get('RRN', ''))
            self.clones_entry.insert(0, default_config.get('Clones', ''))
            # GMT value stored as the offset (e.g., 30 means 130%)
            gmt_value = default_config.get('GMT', '130')
            # Convert old format (130) to new format (30)
            try:
                gmt_num = float(gmt_value)
                if gmt_num > 100:
                    gmt_num = gmt_num - 100
                self.gmt_entry.insert(0, str(int(gmt_num)))
            except:
                self.gmt_entry.insert(0, '30')
            self.user_entry.insert(0, default_config.get('User', ''))
            
            # Load mic volume setting
            mic_vol = default_config.get('mic_volume', '100')
            try:
                vol_value = float(mic_vol)
                self.mic_volume.set(vol_value)
                # Update the label to match the loaded value
                self.mic_volume_value_label.config(text=f"{int(vol_value)}%")
            except:
                self.mic_volume.set(100.0)
                self.mic_volume_value_label.config(text="100%")
            
            # Load subtitle checkbox state
            show_subs = default_config.get('show_subtitles', 'False')
            if show_subs.lower() == 'true':
                self.show_subtitles.set(True)
                self.toggle_subtitles()  # Show the subtitle field

    def start_and_save(self):
        self.save_config()
        self.start()

    def save_config(self):
        if 'DEFAULT' not in self.config:
            self.config['DEFAULT'] = {}
        
        self.config['DEFAULT']['RQ'] = self.rq_entry.get()
        self.config['DEFAULT']['RRN'] = self.rrn_entry.get()
        self.config['DEFAULT']['Clones'] = self.clones_entry.get()
        self.config['DEFAULT']['GMT'] = self.gmt_entry.get()
        self.config['DEFAULT']['User'] = self.user_entry.get()
        self.config['DEFAULT']['mic_volume'] = str(self.mic_volume.get())
        self.config['DEFAULT']['show_subtitles'] = str(self.show_subtitles.get())

        with open(self.config_path, 'w') as configfile:
            self.config.write(configfile)
    
    def update_mic_volume_label(self, value):
        """Update the mic volume label when slider moves"""
        self.mic_volume_value_label.config(text=f"{int(float(value))}%")
        # Save the mic volume setting
        if 'DEFAULT' not in self.config:
            self.config['DEFAULT'] = {}
        self.config['DEFAULT']['mic_volume'] = str(float(value))
        with open(self.config_path, 'w') as configfile:
            self.config.write(configfile)
    
    def toggle_subtitles(self):
        """Show or hide the subtitle text field"""
        if self.show_subtitles.get():
            self.subtitle_text.pack(pady=5, before=self.load_button)
            # Update window height to accommodate subtitles
            self.root.geometry("273x550")
        else:
            self.subtitle_text.pack_forget()
            # Restore original window height
            self.root.geometry("273x480")
        
        # Save the subtitle checkbox state
        if 'DEFAULT' not in self.config:
            self.config['DEFAULT'] = {}
        self.config['DEFAULT']['show_subtitles'] = str(self.show_subtitles.get())
        with open(self.config_path, 'w') as configfile:
            self.config.write(configfile)
    
    def update_subtitle(self, audio_file):
        """Update subtitle text based on current audio file"""
        if not self.show_subtitles.get():
            return
        
        # Extract filename from full path
        filename = os.path.basename(audio_file)
        
        # Check if we have a phrase for this file
        phrase = self.phrases_dict.get(filename, "")
        
        # Update subtitle text
        self.subtitle_text.config(state=tk.NORMAL)
        self.subtitle_text.delete("1.0", tk.END)
        self.subtitle_text.insert("1.0", phrase)
        self.subtitle_text.config(state=tk.DISABLED)
    
    def load_phrases_file(self, folder_path):
        """Load the _phrases.txt file if it exists in the folder"""
        phrases_file = os.path.join(folder_path, "_phrases.txt")
        self.phrases_dict = {}
        
        if os.path.exists(phrases_file):
            try:
                with open(phrases_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if '|' in line:
                            filename, phrase = line.strip().split('|', 1)
                            self.phrases_dict[filename] = phrase
            except Exception as e:
                print(f"Error loading phrases file: {e}")
       

    def load(self):
        # Get last used path from config
        initial_dir = None
        if 'DEFAULT' in self.config:
            last_path = self.config['DEFAULT'].get('last_load_path', '')
            if last_path and os.path.exists(last_path):
                initial_dir = last_path
        
        # If no last path or it doesn't exist, use script directory
        if not initial_dir:
            initial_dir = os.path.dirname(os.path.abspath(__file__))
        
        original_audio_files = filedialog.askopenfilenames(
            filetypes=[('Audio Files', '*.wav;*.mp3')],
            initialdir=initial_dir
        )
        
        # Save the directory of the first selected file
        if original_audio_files:
            first_file_dir = os.path.dirname(original_audio_files[0])
            if 'DEFAULT' not in self.config:
                self.config['DEFAULT'] = {}
            self.config['DEFAULT']['last_load_path'] = first_file_dir
            with open(self.config_path, 'w') as configfile:
                self.config.write(configfile)
            
            # Load phrases file if it exists in the same folder
            self.load_phrases_file(first_file_dir)

        try:
            RQ = int(self.rq_entry.get())
            RRN = int(self.rrn_entry.get())
            Clones = int(self.clones_entry.get())
        except ValueError:
            print("Invalid input for Round Quantity, Round Repeat Number, or Clones.")
            return

        # Clone each audio file
        self.audio_files = [file for file in original_audio_files for _ in range(Clones)]
        self.rounds = []

        # Create rounds taking into account the Clones
        for i in range(0, len(self.audio_files), RQ*Clones):
            round = self.audio_files[i:i + RQ*Clones]
            self.rounds.extend([round] * RRN)

        # Load the first audio file to be played
        if self.rounds:
            self.current_round = self.rounds[0][:]
            pygame.mixer.music.load(self.current_round[0])
            self.current_file = self.current_round[0]
            self.current_round = self.current_round[1:]

    def start(self):
        self.save_config()  # Add this line to save the configuration every time the start button is pressed
        self.playing = True
        self.mode = "Play"
        # Update subtitle for the first file
        if self.current_file:
            self.update_subtitle(self.current_file)
        pygame.mixer.music.play()
        pygame.mixer.music.set_endevent(pygame.USEREVENT)
        self.check_music()

    def stop(self):
        self.playing = False
        pygame.mixer.music.stop()
        # Unload any music to release file handles
        pygame.mixer.music.unload()

    def record_and_play(self):
        # Unload any currently loaded music to release the recording.wav file
        pygame.mixer.music.unload()
        
        p = pyaudio.PyAudio()
        
        freq = 22050  # Sample rate
        duration = pygame.mixer.Sound(self.current_file).get_length()  # Duration of recording

        try:
            gmt_value = float(self.gmt_entry.get())
            # Convert to percentage: input value + 100
            # e.g., 30 becomes 130%, -20 becomes 80%
            gmt = 100 + gmt_value
        except ValueError:
            print("Invalid input for 'Give me more time'")
            return

        duration *= gmt / 100

        frames = []  # Initialize array to store frames

        # Start Recording
        stream = p.open(format=p.get_format_from_width(2), channels=1, rate=freq, input=True,
                        frames_per_buffer=int(freq / 5))  # Here we record in chunks of 1/5 of a second

        for _ in range(int(duration * 5)):  # The 5 is because we're recording in chunks of 1/5 of a second
            data = stream.read(int(freq / 5))
            frames.append(data)

        # Stop Recording
        stream.stop_stream()
        stream.close()
        p.terminate()

        # Save the raw recording first
        wf = wave.open('recording_raw.wav', 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(2)  # Set sample width directly to 2 (bytes)
        wf.setframerate(freq)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        # Apply volume adjustment using pydub
        try:
            from pydub import AudioSegment
            
            # Get microphone volume from slider (0-200%)
            mic_volume_percent = self.mic_volume.get()
            
            # Load the raw recording
            audio = AudioSegment.from_wav('recording_raw.wav')
            
            # Calculate dB change
            # 100% = 0dB (no change), 200% = +6dB (double), 50% = -6dB (half)
            if mic_volume_percent > 0:
                db_change = 20 * (mic_volume_percent / 100.0 - 1)
                audio = audio + db_change
            else:
                # If 0%, make it silent
                audio = audio - 100
            
            # Export the adjusted recording
            audio.export('recording.wav', format='wav')
            
            # Clean up raw file
            import os
            if os.path.exists('recording_raw.wav'):
                os.remove('recording_raw.wav')
                
        except Exception as e:
            print(f"Error adjusting volume: {e}")
            # If volume adjustment fails, just rename the raw file
            import shutil
            shutil.move('recording_raw.wav', 'recording.wav')

    def check_music(self):
        if not pygame.mixer.music.get_busy() and self.playing:
            if self.mode == "Play":
                pygame.mixer.music.set_volume(1.0)  # Set volume to 100%
                # Update subtitle for the current file being played
                self.update_subtitle(self.current_file)
                self.record_and_play()
                self.mode = "Record"
                pygame.mixer.music.load('recording.wav')
                # Volume is already adjusted in the audio file, so play at full volume
                pygame.mixer.music.set_volume(1.0)
                pygame.mixer.music.play()
            elif self.mode == "Record":
                self.mode = "Play"
                pygame.mixer.music.set_volume(1.0)  # Set volume back to 100%
                # Unload recording.wav before loading next file
                pygame.mixer.music.unload()
                if self.current_round:
                    pygame.mixer.music.load(self.current_round[0])
                    self.current_file = self.current_round[0]
                    self.current_round = self.current_round[1:]
                    pygame.mixer.music.play()
                    # Update subtitle for the new file
                    self.update_subtitle(self.current_file)
                elif self.rounds:
                    self.rounds = self.rounds[1:]
                    if self.rounds:
                        self.current_round = self.rounds[0][:]
                        pygame.mixer.music.load(self.current_round[0])
                        self.current_file = self.current_round[0]
                        self.current_round = self.current_round[1:]
                        pygame.mixer.music.play()
                        # Update subtitle for the new file
                        self.update_subtitle(self.current_file)

        root.after(100, self.check_music)

    def check_api_key(self):
        """Check if Azure API key exists in config.ini"""
        if 'AZURE' in self.config:
            api_key = self.config['AZURE'].get('api_key', '').strip()
            return len(api_key) > 0
        return False

    def toggle_api_button_color(self):
        """Toggle the API key button color for blinking effect"""
        if hasattr(self, 'api_key_button') and not self.check_api_key():
            current_color = self.api_key_button.cget('bg')
            new_color = 'red' if current_color == 'darkred' else 'darkred'
            self.api_key_button.config(bg=new_color)
            root.after(500, self.toggle_api_button_color)
        elif hasattr(self, 'api_key_button'):
            self.api_key_button.config(bg='lightgreen')

    def open_api_key_window(self):
        """Open Azure API key management window"""
        api_window = tk.Toplevel(root)
        api_window.title("Azure API Key")
        api_window.geometry("500x300")
        
        # Title
        title_label = tk.Label(api_window, text="Azure Speech Service Configuration", font=("Arial", 12, "bold"))
        title_label.pack(pady=(15, 10))
        
        # API Key field
        key_label = tk.Label(api_window, text="API Key:", font=("Arial", 10))
        key_label.pack(pady=(5, 5))
        
        key_entry = tk.Entry(api_window, width=50, show="*")
        key_entry.pack(pady=5)
        
        # Region field
        region_label = tk.Label(api_window, text="Region (e.g., westeurope, eastus):", font=("Arial", 10))
        region_label.pack(pady=(10, 5))
        
        region_entry = tk.Entry(api_window, width=50)
        region_entry.pack(pady=5)
        
        # Load existing values from config.ini
        if 'AZURE' in self.config:
            existing_key = self.config['AZURE'].get('api_key', '').strip()
            existing_region = self.config['AZURE'].get('region', 'westeurope').strip()
            if existing_key:
                key_entry.insert(0, existing_key)
            if existing_region:
                region_entry.insert(0, existing_region)
        
        # Button frame
        button_frame = tk.Frame(api_window)
        button_frame.pack(pady=20)
        
        # How to Get button
        how_to_button = tk.Button(
            button_frame,
            text="How to Get",
            command=lambda: self.show_how_to_get_key(),
            bg='lightblue',
            font=("Arial", 9)
        )
        how_to_button.grid(row=0, column=0, padx=5)
        
        # Save button
        save_button = tk.Button(
            button_frame,
            text="Save",
            command=lambda: self.save_api_key(key_entry.get(), region_entry.get(), api_window),
            bg='lightgreen',
            font=("Arial", 9, "bold")
        )
        save_button.grid(row=0, column=1, padx=5)

    def show_how_to_get_key(self):
        """Show instructions for getting Azure API key"""
        instructions_window = tk.Toplevel(root)
        instructions_window.title("How to Get Azure API Key")
        instructions_window.geometry("600x550")
        
        # Title
        title_label = tk.Label(
            instructions_window, 
            text="How to Get Your Azure Speech API Key", 
            font=("Arial", 13, "bold")
        )
        title_label.pack(pady=(15, 10))
        
        # Instructions text
        instructions_text = scrolledtext.ScrolledText(
            instructions_window, 
            width=70, 
            height=20, 
            wrap=tk.WORD,
            font=("Arial", 9)
        )
        instructions_text.pack(pady=10, padx=15)
        
        instructions = """Follow these steps to get your Azure Speech Service API key:

1. CREATE AZURE ACCOUNT (if you don't have one)
   • Click the "Azure Portal" button below
   • Sign in with your Microsoft account or create a new one
   • You'll get $200 free credit for 30 days

2. CREATE A SPEECH RESOURCE
   • In Azure Portal, click "+ Create a resource" in the left menu
   • Search for "Speech" or "Cognitive Services Speech"
   • Click "Create" on the Speech service
   • Or use the "Create Speech Resource" button below

3. CONFIGURE YOUR SPEECH RESOURCE
   • Subscription: Select your Azure subscription
   • Resource Group: Create new or use existing
   • Region: Choose a location near you (e.g., "West Europe", "East US")
     Note: Remember your region - you'll need it!
   • Name: Give it a unique name (e.g., "my-speech-service")
   • Pricing Tier: Select "Free F0" for testing or "Standard S0" for production
   • Click "Review + create", then "Create"

4. GET YOUR API KEY
   • Wait for deployment to complete (1-2 minutes)
   • Click "Go to resource"
   • In the left menu, click "Keys and Endpoint"
   • You'll see two keys (KEY 1 and KEY 2)
   • Click the copy icon next to KEY 1 to copy it
   • Copy your REGION as well (shown on the same page)
   • Paste both into this application

IMPORTANT NOTES:
   • Keep your API key secret - don't share it publicly
   • The free tier includes 5 hours of audio per month
   • You can regenerate keys if needed from the Azure Portal

Need more help? Click the "Documentation" button below."""
        
        instructions_text.insert("1.0", instructions)
        instructions_text.config(state='disabled')  # Make read-only
        
        # Button frame for clickable links
        link_frame = tk.Frame(instructions_window)
        link_frame.pack(pady=10)
        
        # Azure Portal button
        azure_portal_button = tk.Button(
            link_frame,
            text="🌐 Azure Portal",
            command=lambda: webbrowser.open("https://portal.azure.com"),
            bg='#0078D4',
            fg='white',
            font=("Arial", 9, "bold"),
            cursor="hand2"
        )
        azure_portal_button.grid(row=0, column=0, padx=5, pady=5)
        
        # Create Speech Resource button
        create_resource_button = tk.Button(
            link_frame,
            text="➕ Create Speech Resource",
            command=lambda: webbrowser.open("https://portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices"),
            bg='#28a745',
            fg='white',
            font=("Arial", 9, "bold"),
            cursor="hand2"
        )
        create_resource_button.grid(row=0, column=1, padx=5, pady=5)
        
        # Documentation button
        docs_button = tk.Button(
            link_frame,
            text="📖 Documentation",
            command=lambda: webbrowser.open("https://learn.microsoft.com/en-us/azure/ai-services/speech-service/"),
            bg='#6c757d',
            fg='white',
            font=("Arial", 9, "bold"),
            cursor="hand2"
        )
        docs_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Close button
        close_button = tk.Button(
            instructions_window,
            text="Close",
            command=instructions_window.destroy,
            bg='lightblue',
            font=("Arial", 10)
        )
        close_button.pack(pady=10)

    def save_api_key(self, api_key, region, window):
        """Save the API key and region to config.ini"""
        if not api_key.strip():
            messagebox.showerror("Error", "Please enter an API key.")
            return
        
        if not region.strip():
            messagebox.showerror("Error", "Please enter a region.")
            return
        
        try:
            # Create AZURE section if it doesn't exist
            if 'AZURE' not in self.config:
                self.config['AZURE'] = {}
            
            # Save the key and region
            self.config['AZURE']['api_key'] = api_key.strip()
            self.config['AZURE']['region'] = region.strip()
            
            # Write to config file
            with open(self.config_path, 'w') as configfile:
                self.config.write(configfile)
            
            messagebox.showinfo("Success", "API key and region saved successfully to config.ini!")
            window.destroy()
            
            # Update button color
            if hasattr(self, 'api_key_button'):
                self.api_key_button.config(bg='lightgreen')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {e}")

    def open_voice_settings(self):
        """Open voice settings window with language and voice selection"""
        settings_window = tk.Toplevel(root)
        settings_window.title("Voice Settings")
        settings_window.geometry("600x500")
        
        # Title
        title_label = tk.Label(settings_window, text="Text-to-Speech Voice Settings", font=("Arial", 13, "bold"))
        title_label.pack(pady=(15, 10))
        
        # Status label
        status_label = tk.Label(settings_window, text="Loading voices...", font=("Arial", 9), fg="gray")
        status_label.pack(pady=5)
        
        # Language selection
        lang_frame = tk.Frame(settings_window)
        lang_frame.pack(pady=10, padx=20, fill='x')
        
        lang_label = tk.Label(lang_frame, text="Language:", font=("Arial", 10, "bold"))
        lang_label.pack(side='left', padx=(0, 10))
        
        language_var = tk.StringVar()
        language_combo = ttk.Combobox(lang_frame, textvariable=language_var, state='readonly', width=30)
        language_combo.pack(side='left', fill='x', expand=True)
        
        # Voice selection
        voice_frame = tk.Frame(settings_window)
        voice_frame.pack(pady=10, padx=20, fill='x')
        
        voice_label = tk.Label(voice_frame, text="Voice:", font=("Arial", 10, "bold"))
        voice_label.pack(side='left', padx=(0, 10))
        
        voice_var = tk.StringVar()
        voice_combo = ttk.Combobox(voice_frame, textvariable=voice_var, state='readonly', width=40)
        voice_combo.pack(side='left', fill='x', expand=True)
        
        # Voice info label
        info_label = tk.Label(settings_window, text="", font=("Arial", 8), fg="darkblue", wraplength=550)
        info_label.pack(pady=5)
        
        # Test section
        test_frame = tk.LabelFrame(settings_window, text="Test Voice", font=("Arial", 10, "bold"), padx=10, pady=10)
        test_frame.pack(pady=15, padx=20, fill='both', expand=True)
        
        test_text_label = tk.Label(test_frame, text="Test text:", font=("Arial", 9))
        test_text_label.pack(anchor='w')
        
        test_text_var = tk.StringVar(value="Hello, this is a test of the selected voice.")
        test_text_entry = tk.Entry(test_frame, textvariable=test_text_var, width=60)
        test_text_entry.pack(pady=5, fill='x')
        
        test_button = tk.Button(
            test_frame,
            text="▶ Play Test",
            command=lambda: self.test_voice(voice_var.get(), test_text_var.get(), settings_window),
            bg='#4CAF50',
            fg='white',
            font=("Arial", 10, "bold"),
            cursor="hand2"
        )
        test_button.pack(pady=10)
        
        # Button frame
        button_frame = tk.Frame(settings_window)
        button_frame.pack(pady=15)
        
        save_button = tk.Button(
            button_frame,
            text="Save as Default",
            command=lambda: self.save_voice_setting(voice_var.get(), settings_window),
            bg='lightgreen',
            font=("Arial", 9, "bold")
        )
        save_button.pack(side='left', padx=5)
        
        close_button = tk.Button(
            button_frame,
            text="Close",
            command=settings_window.destroy,
            bg='lightgray',
            font=("Arial", 9)
        )
        close_button.pack(side='left', padx=5)
        
        # Load voices in background
        def load_voices():
            script_dir = os.path.dirname(os.path.abspath(__file__))
            tts_module_path = os.path.join(script_dir, 'tts_module')
            sys.path.insert(0, tts_module_path)
            
            try:
                from azure_tts_module import get_available_voices
                voices = get_available_voices()
                
                if not voices:
                    status_label.config(text="Failed to load voices. Check API key.", fg="red")
                    return
                
                # Organize voices by language with priorities
                voices_by_lang = self.organize_voices_by_language(voices)
                
                # Populate language dropdown
                languages = list(voices_by_lang.keys())
                language_combo['values'] = languages
                
                # Get current voice from config
                current_voice = 'en-US-BrianNeural'
                if 'AZURE' in self.config:
                    current_voice = self.config['AZURE'].get('voice', current_voice).strip()
                
                # Find and select current language
                current_lang = None
                for lang, voice_list in voices_by_lang.items():
                    if any(v['name'] == current_voice for v in voice_list):
                        current_lang = lang
                        break
                
                if current_lang:
                    language_var.set(current_lang)
                elif languages:
                    language_var.set(languages[0])
                
                # Update voice list when language changes
                def on_language_change(event):
                    selected_lang = language_var.get()
                    voice_list = voices_by_lang.get(selected_lang, [])
                    voice_names = [f"{v['name']} ({v['gender']}) {'[Neural]' if v['voice_type'] == 'Neural' else ''}" 
                                   for v in voice_list]
                    voice_combo['values'] = voice_names
                    if voice_names:
                        voice_combo.current(0)
                        update_voice_info()
                
                def update_voice_info():
                    selected_display = voice_var.get()
                    if selected_display:
                        voice_name = selected_display.split(' (')[0]
                        selected_lang = language_var.get()
                        voice_list = voices_by_lang.get(selected_lang, [])
                        voice_data = next((v for v in voice_list if v['name'] == voice_name), None)
                        if voice_data:
                            info_label.config(
                                text=f"Voice: {voice_data['name']}\nLocale: {voice_data['locale']}\n"
                                     f"Gender: {voice_data['gender']}\nType: {voice_data['voice_type']}"
                            )
                
                language_combo.bind('<<ComboboxSelected>>', on_language_change)
                voice_combo.bind('<<ComboboxSelected>>', lambda e: update_voice_info())
                
                # Trigger initial load
                on_language_change(None)
                
                # Select current voice if found
                if current_lang:
                    voice_list = voices_by_lang.get(current_lang, [])
                    for idx, v in enumerate(voice_list):
                        if v['name'] == current_voice:
                            voice_combo.current(idx)
                            update_voice_info()
                            break
                
                status_label.config(text=f"Loaded {len(voices)} voices", fg="green")
                
            except Exception as e:
                status_label.config(text=f"Error: {e}", fg="red")
        
        # Run in thread to avoid blocking UI
        import threading
        threading.Thread(target=load_voices, daemon=True).start()
    
    def organize_voices_by_language(self, voices):
        """Organize voices by language with neural voices first and common variants prioritized"""
        # Priority order for language variants
        priority_locales = {
            'en': ['en-US', 'en-GB', 'en-AU', 'en-CA', 'en-IN'],
            'es': ['es-ES', 'es-MX', 'es-AR', 'es-CO'],
            'fr': ['fr-FR', 'fr-CA', 'fr-BE', 'fr-CH'],
            'de': ['de-DE', 'de-AT', 'de-CH'],
            'pt': ['pt-BR', 'pt-PT'],
            'zh': ['zh-CN', 'zh-TW', 'zh-HK'],
            'ar': ['ar-SA', 'ar-EG', 'ar-AE'],
            'it': ['it-IT'],
            'ja': ['ja-JP'],
            'ko': ['ko-KR'],
            'ru': ['ru-RU'],
            'nl': ['nl-NL', 'nl-BE'],
        }
        
        # Group by base language
        lang_groups = {}
        for voice in voices:
            locale = voice['locale']
            lang_code = locale.split('-')[0]
            
            if lang_code not in lang_groups:
                lang_groups[lang_code] = {}
            
            if locale not in lang_groups[lang_code]:
                lang_groups[lang_code][locale] = []
            
            lang_groups[lang_code][locale].append(voice)
        
        # Create organized structure
        organized = {}
        lang_names = {
            'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
            'pt': 'Portuguese', 'zh': 'Chinese', 'ar': 'Arabic', 'it': 'Italian',
            'ja': 'Japanese', 'ko': 'Korean', 'ru': 'Russian', 'nl': 'Dutch',
            'pl': 'Polish', 'tr': 'Turkish', 'sv': 'Swedish', 'da': 'Danish',
            'fi': 'Finnish', 'no': 'Norwegian', 'cs': 'Czech', 'el': 'Greek',
            'he': 'Hebrew', 'hi': 'Hindi', 'th': 'Thai', 'vi': 'Vietnamese'
        }
        
        for lang_code, locales in sorted(lang_groups.items()):
            lang_name = lang_names.get(lang_code, lang_code.upper())
            
            # Sort locales by priority
            priority_list = priority_locales.get(lang_code, [])
            sorted_locales = []
            
            # Add priority locales first
            for priority_locale in priority_list:
                if priority_locale in locales:
                    sorted_locales.append(priority_locale)
            
            # Add remaining locales
            for locale in sorted(locales.keys()):
                if locale not in sorted_locales:
                    sorted_locales.append(locale)
            
            # Combine all voices for this language
            all_voices = []
            for locale in sorted_locales:
                locale_voices = locales[locale]
                # Sort: Neural first, then by name
                locale_voices.sort(key=lambda v: (0 if v['voice_type'] == 'Neural' else 1, v['name']))
                all_voices.extend(locale_voices)
            
            if all_voices:
                organized[lang_name] = all_voices
        
        return organized
    
    def test_voice(self, voice_display, test_text, parent_window):
        """Test the selected voice"""
        if not voice_display or not test_text.strip():
            messagebox.showwarning("Warning", "Please select a voice and enter test text.")
            return
        
        voice_name = voice_display.split(' (')[0]
        
        try:
            # Import TTS module
            script_dir = os.path.dirname(os.path.abspath(__file__))
            tts_module_path = os.path.join(script_dir, 'tts_module')
            sys.path.insert(0, tts_module_path)
            
            from azure_tts_module import azure_tts
            
            # Create temp file for test
            temp_file = os.path.join(script_dir, 'temp_voice_test.wav')
            
            # Generate audio
            azure_tts(test_text.strip(), temp_file, voice_name)
            
            # Play the audio
            if os.path.exists(temp_file):
                pygame.mixer.music.load(temp_file)
                pygame.mixer.music.play()
                
                # Clean up after playing completes
                def cleanup():
                    # Wait until playback is actually finished
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                    
                    # Additional small delay to ensure complete playback
                    time.sleep(0.5)
                    
                    if os.path.exists(temp_file):
                        try:
                            pygame.mixer.music.unload()
                            time.sleep(0.2)
                            os.remove(temp_file)
                        except:
                            pass
                
                import threading
                threading.Thread(target=cleanup, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to test voice: {e}")
    
    def save_voice_setting(self, voice_display, window):
        """Save the selected voice to config"""
        if not voice_display:
            messagebox.showwarning("Warning", "Please select a voice.")
            return
        
        voice_name = voice_display.split(' (')[0]
        
        try:
            if 'AZURE' not in self.config:
                self.config['AZURE'] = {}
            
            self.config['AZURE']['voice'] = voice_name
            
            with open(self.config_path, 'w') as configfile:
                self.config.write(configfile)
            
            messagebox.showinfo("Success", f"Voice '{voice_name}' saved as default!")
            window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save voice setting: {e}")

    def open_create_sounds_window(self):
        """Open a popup window for creating new sounds using Azure TTS"""
        sounds_window = tk.Toplevel(root)
        sounds_window.title("Create New Sounds")
        sounds_window.geometry("500x550")
        
        # Azure API Key button at the top
        self.api_key_button = tk.Button(
            sounds_window, 
            text='Azure API Key', 
            command=self.open_api_key_window, 
            font=("Arial", 9)
        )
        self.api_key_button.pack(pady=(10, 5))
        
        # Settings button
        settings_button = tk.Button(
            sounds_window, 
            text='⚙ Voice Settings', 
            command=self.open_voice_settings, 
            bg='#f0f0f0',
            font=("Arial", 9)
        )
        settings_button.pack(pady=(0, 10))
        
        # Start blinking animation for API key button
        self.toggle_api_button_color()
        
        # Topic field
        topic_label = tk.Label(sounds_window, text="Topic:", font=("Arial", 10))
        topic_label.pack(pady=(10, 5))
        
        topic_entry = tk.Entry(sounds_window, width=50)
        topic_entry.pack(pady=5)
        
        # Text area label
        text_label = tk.Label(sounds_window, text="Text (one phrase per line):", font=("Arial", 10))
        text_label.pack(pady=(10, 5))
        
        # Large text area for pasting text
        text_area = scrolledtext.ScrolledText(sounds_window, width=55, height=15, wrap=tk.WORD)
        text_area.pack(pady=5, padx=10)
        
        # Generate button
        generate_button = tk.Button(
            sounds_window, 
            text="Generate Audio Files", 
            command=lambda: self.generate_sounds(topic_entry.get(), text_area.get("1.0", tk.END), sounds_window),
            bg='lightgreen',
            font=("Arial", 10, "bold")
        )
        generate_button.pack(pady=15)
        
        # Instructions
        instructions = tk.Label(
            sounds_window, 
            text="Enter a topic name and paste text below.\nEach line will be converted to an audio file.",
            font=("Arial", 8),
            fg="gray"
        )
        instructions.pack(pady=5)

    def generate_sounds(self, topic, text, parent_window):
        """Generate audio files from text using Azure TTS"""
        # Validate inputs
        if not topic.strip():
            messagebox.showerror("Error", "Please enter a topic name.")
            return
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            messagebox.showerror("Error", "Please enter some text to convert.")
            return
        
        # Import the TTS module
        script_dir = os.path.dirname(os.path.abspath(__file__))
        tts_module_path = os.path.join(script_dir, 'tts_module')
        sys.path.insert(0, tts_module_path)
        
        try:
            from azure_tts_module import azure_tts, get_azure_config
        except ImportError as e:
            messagebox.showerror("Error", f"Could not import Azure TTS module: {e}")
            return
        
        # Get current voice configuration
        api_key, region, voice_name = get_azure_config()
        if not api_key or not region:
            messagebox.showerror("Error", "Azure API key not configured. Please set it up first.")
            return
        
        # Extract language from voice name (e.g., "en-US-BrianNeural" -> "English")
        locale = voice_name.split('-')[0] if '-' in voice_name else 'en'
        lang_names = {
            'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
            'pt': 'Portuguese', 'zh': 'Chinese', 'ar': 'Arabic', 'it': 'Italian',
            'ja': 'Japanese', 'ko': 'Korean', 'ru': 'Russian', 'nl': 'Dutch',
            'pl': 'Polish', 'tr': 'Turkish', 'sv': 'Swedish', 'da': 'Danish',
            'fi': 'Finnish', 'no': 'Norwegian', 'cs': 'Czech', 'el': 'Greek',
            'he': 'Hebrew', 'hi': 'Hindi', 'th': 'Thai', 'vi': 'Vietnamese',
            'uk': 'Ukrainian', 'ro': 'Romanian', 'bg': 'Bulgarian', 'hr': 'Croatian',
            'sk': 'Slovak', 'sl': 'Slovenian', 'hu': 'Hungarian', 'id': 'Indonesian',
            'ms': 'Malay', 'ta': 'Tamil', 'te': 'Telugu', 'bn': 'Bengali'
        }
        language_name = lang_names.get(locale, locale.upper())
        
        # Create folder structure: sounds/Language/Topic
        sounds_folder = os.path.join(script_dir, 'sounds')
        language_folder = os.path.join(sounds_folder, language_name)
        topic_folder = os.path.join(language_folder, topic.strip())
        
        # Create all necessary folders
        if not os.path.exists(sounds_folder):
            os.makedirs(sounds_folder)
        if not os.path.exists(language_folder):
            os.makedirs(language_folder)
        if not os.path.exists(topic_folder):
            os.makedirs(topic_folder)
        
        # Create progress window
        progress_window = tk.Toplevel(parent_window)
        progress_window.title("Generating Audio Files")
        progress_window.geometry("400x150")
        
        progress_label = tk.Label(progress_window, text="Generating audio files...", font=("Arial", 10))
        progress_label.pack(pady=10)
        
        progress_bar = ttk.Progressbar(progress_window, length=300, mode='determinate')
        progress_bar.pack(pady=10)
        progress_bar['maximum'] = len(lines)
        
        status_label = tk.Label(progress_window, text="", font=("Arial", 8))
        status_label.pack(pady=5)
        
        # Prepare phrases index file
        from datetime import datetime
        phrases_data = []
        
        # Process each line
        for idx, line in enumerate(lines):
            # Update progress
            progress_bar['value'] = idx
            status_label.config(text=f"Processing: {line[:50]}..." if len(line) > 50 else f"Processing: {line}")
            progress_window.update()
            
            # Generate timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Sanitize filename - remove invalid characters, take first 10 chars
            safe_name = re.sub(r'[<>:"/\\|?*]', '', line)
            safe_name = safe_name.replace(' ', '_')[:10]
            
            # Generate filename: number_preview_timestamp.wav
            filename = f"{idx+1:03d}_{safe_name}_{timestamp}.wav"
            final_wav = os.path.join(topic_folder, filename)
            
            # Generate audio using Azure TTS directly to WAV
            try:
                # Call the modified azure_tts function to generate WAV directly
                azure_tts(line, final_wav)
                
                # Store filename and full phrase for index file
                phrases_data.append(f"{filename}|{line}")
                    
            except Exception as e:
                print(f"Error generating audio for line '{line}': {e}")
                continue
        
        # Create phrases index file
        phrases_file = os.path.join(topic_folder, "_phrases.txt")
        try:
            with open(phrases_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(phrases_data))
        except Exception as e:
            print(f"Error creating phrases file: {e}")
        
        # Complete progress
        progress_bar['value'] = len(lines)
        status_label.config(text="Complete!")
        progress_window.update()
        
        # Wait a moment before closing
        progress_window.after(1000, lambda: self.load_generated_folder(topic_folder, progress_window, parent_window))

    def load_generated_folder(self, folder_path, progress_window, sounds_window):
        """Load the generated audio files as the current testing folder"""
        # Close the progress window
        progress_window.destroy()
        sounds_window.destroy()
        
        # Load phrases file if it exists
        self.load_phrases_file(folder_path)
        
        # Get all MP3 files from the folder
        audio_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
                      if f.lower().endswith(('.mp3', '.wav'))]
        audio_files.sort()  # Sort files alphabetically
        
        if not audio_files:
            messagebox.showwarning("Warning", "No audio files found in the generated folder.")
            return
        
        # Load the files into the audio repeater
        try:
            RQ = int(self.rq_entry.get())
            RRN = int(self.rrn_entry.get())
            Clones = int(self.clones_entry.get())
        except ValueError:
            print("Invalid input for Round Quantity, Round Repeat Number, or Clones.")
            return
        
        # Clone each audio file
        self.audio_files = [file for file in audio_files for _ in range(Clones)]
        self.rounds = []
        
        # Create rounds taking into account the Clones
        for i in range(0, len(self.audio_files), RQ*Clones):
            round = self.audio_files[i:i + RQ*Clones]
            self.rounds.extend([round] * RRN)
        
        # Load the first audio file to be played
        if self.rounds:
            self.current_round = self.rounds[0][:]
            pygame.mixer.music.load(self.current_round[0])
            self.current_file = self.current_round[0]
            self.current_round = self.current_round[1:]
        
        messagebox.showinfo("Success", f"Loaded {len(audio_files)} audio files from '{os.path.relpath(folder_path, os.path.dirname(os.path.abspath(__file__)))}'!")

    def export(self):
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime("%Y%m%d_%H%M%S")  # Added %S for seconds

        user = self.user_entry.get()

        # Fetch the directory of the script from the earlier function
        script_directory = os.path.dirname(os.path.abspath(__file__))

        # Create the path for the parent folder
        parent_folder_path = os.path.join(script_directory, user)

        # Check if the parent folder exists
        if not os.path.exists(parent_folder_path):
            os.makedirs(parent_folder_path)  # Create parent folder if it doesn't exist

        # Update the daily folder name to include user name
        folder_name = f"{user} Recordings {current_time.strftime('%Y%m%d')}"
        
        # Add the parent folder to the daily folder path
        daily_folder_path = os.path.join(parent_folder_path, folder_name)

        if not os.path.exists(daily_folder_path):  # Check if the daily folder exists
            os.makedirs(daily_folder_path)  # Create daily folder if it doesn't exist

        shutil.copy('recording.wav', f'{daily_folder_path}/{user} recording {formatted_time}.wav')  # Copy file to the new folder

root = tk.Tk()
app = App(root)
root.mainloop()
