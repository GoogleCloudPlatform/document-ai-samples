"""
Copyright 2022 Google LLC
Author: Holt Skinner

General Utility Functions
"""
import yaml


def read_yaml(file_path):
    """
    Reads a yaml file and returns a dictionary
    """
    with open(file_path, "r", encoding="utf8") as file:
        return yaml.safe_load(file)


def write_yaml(file_path, data):
    """
    Writes a yaml file from a dictionary
    """
    with open(file_path, "w", encoding="utf8") as file:
        yaml.dump(data, file)


def invert_dictionary_with_array(dictionary: dict):
    """
    Inverts a dictionary with arrays as values
    e.g. {key: [value1, value2]} -> {value1: key, value2: key}
    """
    inv_map = {}
    for key, array in dictionary.items():
        for value in array:
            inv_map[value] = key
    return inv_map
