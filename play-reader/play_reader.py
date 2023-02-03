import argparse
import os
from random import choice
import sys
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
TXT_EXTENSION = ".txt"

# For character names that are not supported by gender_guesser
CHARACTER_GENDER = {"Macbeth": "male", "Lady Macbeth": "female", "Ariel": "female"}


def list_voices_by_gender(
    language_code: str = DEFAULT_LANGUAGE,
) -> Tuple[Dict[str, List], int]:
    gender_to_voices: Dict[str, List[Tuple[str, str]]] = {}
    total_voices = 0

    # Performs the list voices request
    response = tts_client.list_voices(language_code=language_code)

    for voice in response.voices:
        if "Neural2" not in voice.name or DEFAULT_VOICE[0] == voice.name:
            continue

        ssml_gender = texttospeech.SsmlVoiceGender(voice.ssml_gender).name.lower()

        if gender_to_voices.get(ssml_gender):
            gender_to_voices[ssml_gender].append((voice.name, voice.language_codes[0]))
        else:
            gender_to_voices[ssml_gender] = [(voice.name, voice.language_codes[0])]

        total_voices += 1

    return gender_to_voices, total_voices


def print_gender_map(gender_to_voices: Dict[str, List]):
    print(f"Gender\t| Voice Name")
    for gender, voices in gender_to_voices.items():
        for voice in voices:
            print(f"{gender}\t| {voice}")
    print("\n")


def create_character_map(
    names: List[str], gender_to_voices: Dict[str, List]
) -> Dict[str, Tuple]:
    character_to_voice: Dict[str, Tuple] = {}
    supported_genders = list(gender_to_voices.keys())

    for name in names:
        if name == "Narrator":
            character_to_voice[name] = DEFAULT_VOICE
            continue

        if name in CHARACTER_GENDER:
            gender = CHARACTER_GENDER[name]
        else:
            gender = gender_detector.get_gender(name)

        # If gender is indeterminate/androgynous, pick random one
        if gender not in supported_genders:
            gender = choice(supported_genders)

        # Assign Voice to Character and don't reuse.
        voice = choice(gender_to_voices[gender])
        gender_to_voices[gender].remove(voice)
        character_to_voice[name] = voice

    return character_to_voice


def print_character_map(character_to_voice: Dict[str, Tuple]):
    print(f"Character\t| Voice Name")
    for name, voice in character_to_voice.items():
        print(f"{name}\t| {voice}")
    print("\n")


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


def get_characters(input_file) -> List:
    character_list = []
    with open(input_file, "r") as f:
        lines = f.readlines()

    start_line = lines.index("Characters:\n")

    for i in range(start_line + 2, len(lines)):
        if lines[i] == "\n":
            break
        character_list.append(lines[i].strip())
    return character_list


def parse_file(input_file: str, character_to_voice: Dict[str, Tuple]) -> List[str]:
    with open(input_file, "r") as f:
        lines = f.readlines()

    line_number = 1
    output_files = []
    filename = file_prefix(input_file)

    for line in lines:
        split_line = line.strip().split(": ", 1)

        character = split_line[0]
        # Skip blank lines
        if not character:
            continue

        voice = character_to_voice.get(character, DEFAULT_VOICE)

        if len(split_line) <= 1:
            dialogue = split_line[0]
        elif "Scene" in split_line[0]:
            dialogue = split_line[0] + split_line[1]
        else:
            dialogue = split_line[1]

        output_file = f"{filename}-{line_number}.mp3"
        output_files.append(output_file)
        synthesize_text(dialogue, output_file, voice[0], voice[1])
        line_number += 1

    return output_files


def file_prefix(input_file: str) -> str:
    return input_file.replace(TXT_EXTENSION, "")


def main(args: argparse.Namespace) -> int:
    input_file = os.path.abspath(args.input)

    if not os.path.isfile(input_file):
        print(f"Could not find file at {input_file}")
        return 1

    if TXT_EXTENSION not in args.input:
        print(f"Input file {args.input} is not a TXT")
        return 1

    gender_to_voices, total_voices = list_voices_by_gender()
    print_gender_map(gender_to_voices)

    character_list = get_characters(input_file)

    if len(character_list) > total_voices:
        print(
            f"Too many characters in play. Need {len(character_list)}, Max {total_voices}"
        )
        return 1

    character_to_voice = create_character_map(character_list, gender_to_voices)
    print_character_map(character_to_voice)

    output_files = parse_file(input_file, character_to_voice)
    combine_audio_files(output_files, file_prefix(input_file))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Output a Play as Audio")
    parser.add_argument(
        "-i", "--input", help="filepath of input TXT File", required=True
    )
    sys.exit(main(parser.parse_args()))
