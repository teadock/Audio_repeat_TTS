# azure_tts_module.py
import azure.cognitiveservices.speech as speechsdk
import os
import configparser
import json

def get_azure_config():
    """Read Azure configuration from config.ini"""
    try:
        # Get the parent directory (main script directory)
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_file = os.path.join(script_dir, 'config.ini')
        
        config = configparser.ConfigParser()
        config.read(config_file)
        
        if 'AZURE' in config:
            api_key = config['AZURE'].get('api_key', '').strip()
            region = config['AZURE'].get('region', 'westeurope').strip()
            voice = config['AZURE'].get('voice', 'en-US-BrianNeural').strip()
            return api_key, region, voice
        else:
            print("Azure configuration not found in config.ini")
            return None, None, 'en-US-BrianNeural'
    except FileNotFoundError:
        print("Config file not found. Please ensure 'config.ini' is in the main directory.")
        return None, None, 'en-US-BrianNeural'
    except Exception as e:
        print(f"An error occurred while reading the configuration: {e}")
        return None, None, 'en-US-BrianNeural'

def get_available_voices():
    """Fetch available voices from Azure Speech Service"""
    SUBSCRIPTION_KEY, REGION, _ = get_azure_config()
    if not SUBSCRIPTION_KEY or not REGION:
        return []
    
    try:
        speech_config = speechsdk.SpeechConfig(subscription=SUBSCRIPTION_KEY, region=REGION)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        
        result = synthesizer.get_voices_async().get()
        
        if result.reason == speechsdk.ResultReason.VoicesListRetrieved:
            voices = []
            for voice in result.voices:
                voices.append({
                    'name': voice.short_name,
                    'locale': voice.locale,
                    'gender': voice.gender.name,
                    'voice_type': voice.voice_type.name
                })
            return voices
        else:
            print(f"Failed to retrieve voices: {result.reason}")
            return []
    except Exception as e:
        print(f"Error fetching voices: {e}")
        return []

def azure_tts(text, filename, voice_name=None):
    SUBSCRIPTION_KEY, REGION, default_voice = get_azure_config()
    if not SUBSCRIPTION_KEY or not REGION:
        print("Azure API key or region not configured. Please set them in config.ini")
        return
    
    # Use provided voice or default from config
    selected_voice = voice_name if voice_name else default_voice
    
    speech_config = speechsdk.SpeechConfig(subscription=SUBSCRIPTION_KEY, region=REGION)
    speech_config.speech_synthesis_voice_name = selected_voice

    # Determine output format based on file extension
    if filename.lower().endswith('.wav'):
        # Use WAV format for better compatibility
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
        )
    elif not filename.lower().endswith('.mp3'):
        # Default to MP3 if no extension or add .mp3
        filename += '.mp3'
    
    # Set audio output to file
    audio_config = speechsdk.audio.AudioOutputConfig(filename=filename)

    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    result = synthesizer.speak_text(text)

    # Check for successful synthesis
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech synthesized to speaker for text [{}]".format(text))
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation = result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation.reason))
        if cancellation.reason == speechsdk.CancellationReason.Error:
            if cancellation.error_details:
                print("Error details: {}".format(cancellation.error_details))
