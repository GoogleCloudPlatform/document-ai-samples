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
from enum import auto
from enum import Enum
from json import loads
from typing import NamedTuple


class ImageFormat(Enum):
    """Possible formats for images sent to the frontend.

    Each chosen format supports both single-frame images and animations.
    """

    AUTO = auto()
    WEBP = auto()
    PNG = auto()
    GIF = auto()

    @classmethod
    def _missing_(cls, value):
        """Create instance from string."""
        assert isinstance(value, str)
        return cls[value.upper()]

    def mimetype(self) -> str:
        """Return its MIME type."""
        assert self.value != self.AUTO
        return f"image/{self.name.lower()}"


class Options(NamedTuple):
    """Rendering options sent by the frontend."""

    page: int
    blocks: bool
    paragraphs: bool
    lines: bool
    tokens: bool
    tables: bool
    barcodes: bool
    fields: bool
    entities: bool
    animated: bool
    cropped: bool
    confidence: bool
    normalized: bool
    format: ImageFormat

    @classmethod
    def from_json(cls, json: str):
        """Create instance from frontend json."""
        options = loads(json)

        format = ImageFormat(options.get("format", "png"))
        if format == ImageFormat.AUTO:
            if options["animated"]:
                # GIF is the most supported format for animations (esp. by blogs)
                # Additionally, WebP animations take ~3x more time to generate (in Pillow)
                format = ImageFormat.GIF
            else:
                # Best file size alternative
                format = ImageFormat.WEBP
        options["format"] = format

        return cls(**options)
