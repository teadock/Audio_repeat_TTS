===================================================
   AUDIO REPEATER - Language Learning Tool
===================================================

INSTALLATION:
-------------
1. Install required Python packages:
   pip install pygame pyaudio scipy azure-cognitiveservices-speech pydub

2. Copy config.ini.template to config.ini
3. Add your Azure Speech API key to config.ini


CONFIGURATION (config.ini):
---------------------------
[DEFAULT]
- rq (Round Quantity): Number of files in one round
- rrn (Round Repeat Number): How many times to repeat each round
- clones: How many times to repeat each sentence in a row
- gmt (Give Me Time): Percentage of time for your recording (100% = same length as audio)
- user: Your name (for organizing exported recordings)

[AZURE]
- api_key: Your Azure Speech Service API key
- region: Your Azure region (westeurope, eastus, etc.)


HOW TO USE:
-----------
1. LOAD: Select audio files (WAV or MP3) to practice with
2. START: Begin the playback and recording cycle
3. STOP: Stop the session
4. EXPORT (Enter): Save your recordings to dated folder

OR

CREATE NEW SOUNDS:
------------------
1. Click "Create New Sounds" button
2. Set up Azure API Key if needed (button will blink red if missing)
3. Enter a topic name
4. Paste text (one phrase per line)
5. Click "Generate Audio Files"
6. Files are automatically loaded for practice!


FEATURES:
---------
- Automatic Text-to-Speech using Azure Neural Voices
- Spaced repetition with configurable rounds
- Record your practice attempts
- Export and track your progress
- Organized folder structure for recordings


SECURITY NOTE:
--------------
- API keys are stored in config.ini (excluded from git)
- Never share your config.ini file publicly
- Regenerate keys from Azure Portal if compromised
