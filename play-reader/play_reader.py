import os
from random import choice
from typing import Dict, List, Tuple

from gender_guesser.detector import Detector
from google.cloud import texttospeech_v1beta1 as texttospeech
from pydub import AudioSegment

DEFAULT_LANGUAGE = "en"
# Voice used for narration, scene details, etc.
DEFAULT_VOICE = ("en-GB-Neural2-B", "en-GB")

tts_client = texttospeech.TextToSpeechClient()
gender_detector = Detector()

SILENCE_LENGTH = 200


def list_voices_by_gender(
    language_code: str = DEFAULT_LANGUAGE,
) -> Tuple[Dict[str, List], int]:
    gender_to_voices: Dict[str, List[Tuple[str, str]]] = {}
    total_voices = 0

    # Performs the list voices request
    response = tts_client.list_voices(language_code=language_code)

    for voice in response.voices:
        if "Neural2" not in voice.name or DEFAULT_VOICE == voice.name:
            continue

        ssml_gender = texttospeech.SsmlVoiceGender(voice.ssml_gender).name.lower()

        if gender_to_voices.get(ssml_gender):
            gender_to_voices[ssml_gender].append((voice.name, voice.language_codes[0]))
        else:
            gender_to_voices[ssml_gender] = [(voice.name, voice.language_codes[0])]

        total_voices += 1

    return gender_to_voices, total_voices


def print_gender_map(gender_to_voices: Dict[str, str]):
    print(f"Gender\t| Voice Name")

    for gender, voices in gender_to_voices.items():
        for voice in voices:
            print(f"{gender}\t| {voice}")


def create_character_map(
    names: List[str], gender_to_voices: Dict[str, List]
) -> Dict[str, Tuple]:
    character_to_voice: Dict[str, Tuple] = {}
    supported_genders = list(gender_to_voices.keys())

    for name in names:

        if name == "Narrator":
            character_to_voice[name] = DEFAULT_VOICE
            continue

        gender = gender_detector.get_gender(name)

        # If gender is indeterminate/androgynous, pick random one
        if gender not in supported_genders:
            gender = choice(supported_genders)

        # Assign Voice to Character and don't reuse.
        character_to_voice[name] = gender_to_voices[gender].pop()

    return character_to_voice


def print_character_map(character_to_voice: Dict[str, str]):
    print(f"Character\t| Voice Name")

    for name, voice in character_to_voice.items():
        print(f"{name}\t| {voice}")


def synthesize_text(
    text: str, output: str, voice_name: str, language_code: str = DEFAULT_LANGUAGE
):
    input_text = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code, name=voice_name
    )

    # Note: you can pass in multiple effects_profile_id. They will be applied
    # in the same order they are provided.
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
    )

    response = tts_client.synthesize_speech(
        input=input_text, voice=voice, audio_config=audio_config
    )

    # The response's audio_content is binary.
    with open(output, "wb") as out:
        out.write(response.audio_content)


def combine_audio_files(audio_files: List, filename: str):

    full_audio = AudioSegment.silent(duration=SILENCE_LENGTH)

    for file in audio_files:
        sound = AudioSegment.from_mp3(file)
        silence = AudioSegment.silent(duration=SILENCE_LENGTH)
        full_audio = full_audio + sound + silence

        os.remove(file)

    outfile_name = f"{filename}-complete.mp3"
    full_audio.export(outfile_name, format="mp3")
    print(f"Audio content written to file {outfile_name}")


def main():

    gender_to_voices, total_voices = list_voices_by_gender()
    print_gender_map(gender_to_voices)
    print("\n")

    character_list = [
        "Petruchio",
        "Hortensio",
        "Gremio",
        "Baptista",
    ]

    if len(character_list) > total_voices:
        print(
            f"Too many characters in play. Need {len(character_list)}, Max {total_voices}"
        )
        return

    character_to_voice = create_character_map(character_list, gender_to_voices)
    print_character_map(character_to_voice)

    # input_file = "TheTamingoftheShrew.txt"
    filename = "TheTamingoftheShrew"
    input_file = f"{filename}.txt"

    with open(input_file, "r") as f:
        lines = f.readlines()

    line_number = 1

    output_files = []
    for line in lines:
        split_line = line.strip().split(": ", 1)

        character = split_line[0]
        # Skip blank lines
        if not character:
            continue

        voice = character_to_voice.get(character, DEFAULT_VOICE)

        if len(split_line) <= 1:
            dialogue = split_line[0]
        else:
            dialogue = split_line[1]

        output_file = f"{filename}-{line_number}.mp3"
        output_files.append(output_file)
        synthesize_text(dialogue, output_file, voice[0], voice[1])
        line_number += 1

    combine_audio_files(output_files, filename)


if __name__ == "__main__":
    main()
