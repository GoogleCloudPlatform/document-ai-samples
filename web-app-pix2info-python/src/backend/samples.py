"""
Copyright 2023 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from pathlib import Path
from typing import Iterator, Mapping, Sequence, TypeAlias

# Document AI supported file types
# See https://cloud.google.com/document-ai/docs/file-types
SUFFIXES = ("pdf", "gif", "tiff", "tif", "jpeg", "jpg", "png", "bmp", "webp")

ProcessorName: TypeAlias = str
SampleName: TypeAlias = str
FilePaths: TypeAlias = Sequence[str]
ProcessorSamples: TypeAlias = Mapping[SampleName, FilePaths]


def get_samples(samples_path: Path) -> Mapping[ProcessorName, ProcessorSamples]:
    """Return the samples found locally."""
    return dict(get_processor_samples(samples_path))


def get_processor_samples(
    samples_path: Path,
) -> Iterator[tuple[ProcessorName, ProcessorSamples]]:
    """Yield the samples found per processor folder."""
    for processor_path in samples_path.iterdir():
        if not processor_path.is_dir():
            continue
        samples = dict(get_folder_samples(processor_path))
        yield processor_path.name, samples


def get_folder_samples(
    parent_path: Path,
    rel_dir: str = "",
) -> Iterator[tuple[SampleName, FilePaths]]:
    """Yield the samples found in the parent folder."""
    paged_samples: list[str] = []

    for path in parent_path.iterdir():
        if path.is_dir():
            sub_dir = f"{rel_dir}/{path.name}" if rel_dir else path.name
            yield from get_folder_samples(path, sub_dir)
            continue
        if path.suffix[1:].lower() not in SUFFIXES:
            continue
        if rel_dir:
            paged_samples.append(f"{rel_dir}/{path.name}")
        else:
            yield path.stem, [path.name]

    if paged_samples:
        yield parent_path.name, sorted(paged_samples)
