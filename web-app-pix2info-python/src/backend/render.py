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
from dataclasses import dataclass
from dataclasses import field
from dataclasses import InitVar
from io import BytesIO
import os
import statistics
from typing import Any, cast, Iterable, Iterator, MutableSequence, Sequence, TypeAlias

from google.cloud.documentai_v1 import BoundingPoly
from google.cloud.documentai_v1 import Document
from PIL import Image
from PIL import ImageColor
from PIL import ImageDraw
from PIL import ImageFont

from .options import ImageFormat
from .options import Options

Page: TypeAlias = Document.Page
Entity: TypeAlias = Document.Entity
TextAnchor: TypeAlias = Document.TextAnchor
TextAnchorKey: TypeAlias = tuple[int, int]
Layout: TypeAlias = Document.Page.Layout
Block: TypeAlias = Document.Page.Block
Table: TypeAlias = Document.Page.Table
Barcode: TypeAlias = Document.Page.DetectedBarcode
FormField: TypeAlias = Document.Page.FormField

Rect: TypeAlias = tuple[int, int, int, int]
PilImage: TypeAlias = Image.Image
PilDraw: TypeAlias = ImageDraw.ImageDraw
PilFont: TypeAlias = ImageFont.FreeTypeFont
PilColor: TypeAlias = str
Vertex: TypeAlias = tuple[int, int]
Vertices: TypeAlias = tuple[Vertex, ...]
ImageIterator: TypeAlias = Iterator[PilImage]
Confidence: TypeAlias = float
CalloutInfoBase: TypeAlias = tuple[Vertices | None, str, Confidence | None]
BgColor: TypeAlias = PilColor
FgColor: TypeAlias = PilColor
CalloutInfo: TypeAlias = tuple[Vertices | None, str, Rect, Vertex, BgColor, FgColor]

FRAME_DURATION_FIRST = 1000
FRAME_DURATION_DEFAULT = 150
FRAME_DURATION_LAST = 2000

GOOGLE_BLUE = "#4285F4"
GOOGLE_RED = "#EA4335"
GOOGLE_YELLOW = "#FBBC04"
GOOGLE_GREEN = "#34A853"
OCR_LEVEL_COLOR = {
    "blocks": GOOGLE_BLUE,
    "paragraphs": GOOGLE_RED,
    "lines": GOOGLE_YELLOW,
    "tokens": GOOGLE_GREEN,
}
DEFAULT_TEXT_COLOR = "#000"
DEFAULT_BG_COLOR = "#FFF"
LOW_CONFIDENCE_BG_COLOR = "#888"
PADDING_BG_COLOR = "#AAA"

CROP_MARGIN = 20
TEXT_PADDING_TEXT_H_RATIO = 0.25
TEXT_OUTLINE_HEIGHT_RATIO = 0.15
TEXT_OUTLINE_MIN_WIDTH = 5
ENTITY_TEXT_MAX_CHARS = 50
FORM_FIELD_NAME_COLOR = GOOGLE_RED
FORM_FIELD_VALUE_COLOR = GOOGLE_GREEN
CHECK_BOX_OUTLINE_COLOR = "#FFF7"
FILLED_CHECKBOX = "filled_checkbox"
UNFILLED_CHECKBOX = "unfilled_checkbox"
TABLE_OUTLINE_COLOR = GOOGLE_BLUE
CONFIDENCE_TEXT_COLOR = "#800"
# Display items with lower confidences differently (arbitrary threshold)
CONFIDENCE_THRESHOLD = 0.1

# Font options
# DejaVuSansMono is installed by default on the App Engine runtime
FONT_FAMILY_LINUX = "DejaVuSansMono-Bold.ttf"
# Consolas is installed by default on Windows
FONT_FAMILY_WIN = "consolab.ttf"
FONT_FAMILY = FONT_FAMILY_WIN if os.name == "nt" else FONT_FAMILY_LINUX


def render(document_json: str, options_json: str) -> tuple[BytesIO, str]:
    """Render the document current page and return the image and mimetype."""
    demo = Demo(document_json, options_json)
    image_io = do_render(demo)
    mimetype = demo.options.format.mimetype()

    return image_io, mimetype


@dataclass
class Demo:
    # Initialization data sent by the frontend
    document_json: InitVar[str]
    options_json: InitVar[str]
    # Data
    options: Options = field(init=False)
    document: Document = field(init=False)
    page: Page = field(init=False)
    # Rendering
    input_width: int = field(init=False)
    input_height: int = field(init=False)
    show_confidence: bool = field(init=False)
    page_crop_box: Rect = field(init=False)
    image_crop_box: Rect = field(init=False)
    border_width: int = field(init=False)
    text_height_min: int = field(init=False)
    text_height_median: int = field(init=False)
    font_min: PilFont | None = field(init=False)
    font_median: PilFont | None = field(init=False)
    text_outline_width: int = field(init=False)
    text_padding: int = field(init=False)
    image: PilImage = field(init=False)
    draw: PilDraw = field(init=False)
    rendering: bool = field(init=False)
    frame_count: int = field(init=False)

    def __post_init__(self, document_json: str, options_json: str):
        init_from_json(self, document_json, options_json)

    @classmethod
    def blocks_sorted_by_reading_order(
        cls, blocks: Iterable[Block]
    ) -> MutableSequence[Block]:
        def reading_order_key_for_block(block: Block):
            return reading_order_key_for_layout(block.layout)

        return sorted(blocks, key=reading_order_key_for_block)

    @classmethod
    def tables_sorted_by_reading_order(
        cls, tables: Iterable[Table]
    ) -> MutableSequence[Table]:
        def reading_order_key_for_first_cell(table: Table):
            first_cell = table.header_rows[0].cells[0]
            return reading_order_key_for_layout(first_cell.layout)

        return sorted(tables, key=reading_order_key_for_first_cell)

    @classmethod
    def fields_sorted_by_reading_order(
        cls, fields: Iterable[FormField]
    ) -> MutableSequence[FormField]:
        def reading_order_key_for_field_name(field: FormField):
            return reading_order_key_for_layout(field.field_name)

        return sorted(fields, key=reading_order_key_for_field_name)


def reading_order_key_for_layout(layout: Layout) -> TextAnchorKey:
    return reading_order_key_for_text_anchor(layout.text_anchor)


def reading_order_key_for_text_anchor(
    text_anchor: TextAnchor,
    default_text_index: int = 0,
) -> TextAnchorKey:
    if text_anchor.text_segments:
        text_segments = text_anchor.text_segments
        start_index = text_segments[0].start_index
        end_index = text_segments[-1].end_index
    else:
        start_index = end_index = default_text_index
    return (start_index, end_index)


def init_from_json(demo: Demo, document_json: str, options_json: str):
    demo.options = Options.from_json(options_json)
    demo.document = cast(Document, Document.from_json(document_json))
    demo.page = demo.document.pages[demo.options.page - 1]
    init_confidence(demo)
    init_rendering(demo)


def init_confidence(demo: Demo):
    def can_show_confidence() -> bool:
        options_with_confidence = [
            options.blocks,
            options.paragraphs,
            options.lines,
            options.tokens,
            options.fields,
            options.entities,
        ]
        return any(options_with_confidence)

    options = demo.options
    demo.show_confidence = options.confidence and can_show_confidence()


def init_rendering(demo: Demo):
    demo.image = normalize_image(BytesIO(demo.page.image.content))
    # Memorize original input dimensions (output image may be expanded)
    demo.input_width = demo.image.width
    demo.input_height = demo.image.height
    init_crop_boxes(demo)
    init_font_and_image(demo)
    demo.draw = ImageDraw.Draw(demo.image, mode="RGBA")
    demo.rendering = True
    demo.frame_count = 1


def normalize_image(image_io: BytesIO) -> PilImage:
    image = Image.open(image_io)
    if image.mode in ("LA", "RGBA"):  # Remove transparency
        image = image.convert(image.mode[:-1])
    # Add additional pre-processing if needed...

    return image


def init_crop_boxes(demo: Demo):
    img_max_x, img_max_y = demo.input_width - 1, demo.input_height - 1
    min_x, max_x = img_max_x, 0
    min_y, max_y = img_max_y, 0
    for block in demo.page.blocks:
        for x, y in vertices_from_layout(demo, block.layout):
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
    min_x, max_x = max(min_x - CROP_MARGIN, 0), min(max_x + CROP_MARGIN, img_max_x)
    min_y, max_y = max(min_y - CROP_MARGIN, 0), min(max_y + CROP_MARGIN, img_max_y)
    demo.page_crop_box = (min_x, min_y, max_x + 1, max_y + 1)
    demo.image_crop_box = demo.page_crop_box


def init_font_and_image(demo: Demo):
    demo.border_width = int(0.003 * demo.input_width)

    options = demo.options
    expand_image = options.barcodes or options.entities
    needs_font = expand_image or options.fields or demo.show_confidence
    if not needs_font:
        demo.text_height_min = 0
        demo.text_height_median = 0
        demo.font_min = None
        demo.font_median = None
        demo.text_outline_width = 0
        demo.text_padding = 0
        return

    img_max_x, img_max_y = demo.input_width - 1, demo.input_height - 1
    heights = [
        layout_height(item.layout, img_max_x, img_max_y) for item in demo.page.tokens
    ]
    demo.text_height_min = min(heights)
    demo.text_height_median = statistics.median_low(heights)
    demo.font_min = ImageFont.truetype(FONT_FAMILY, size=demo.text_height_min)
    demo.font_median = ImageFont.truetype(FONT_FAMILY, size=demo.text_height_median)
    text_outline_width = int(demo.text_height_median * TEXT_OUTLINE_HEIGHT_RATIO + 0.5)
    text_outline_width = max(text_outline_width, TEXT_OUTLINE_MIN_WIDTH)
    demo.text_outline_width = text_outline_width
    demo.text_padding = int(demo.text_height_median * TEXT_PADDING_TEXT_H_RATIO + 0.5)

    # Image may need to be expanded to display additional information on the right side
    if not expand_image:
        return
    coords = [(x, y) for _, _, (_, _, x, y), _, _, _ in callout_info(demo)]
    if not coords:
        return

    max_x, max_y = cast(tuple[int, int], map(max, zip(*coords)))
    demo.image_crop_box = (
        demo.page_crop_box[0],
        demo.page_crop_box[1],
        max_x + CROP_MARGIN,
        max(max_y + CROP_MARGIN, demo.page_crop_box[3]),
    )
    max_x = demo.image_crop_box[2]
    max_y = demo.image_crop_box[3]
    pad_w, pad_h = max(0, max_x - img_max_x), max(0, max_y - img_max_y)
    if pad_w == 0 and pad_h == 0:
        return

    padded = Image.new(
        demo.image.mode,
        (demo.image.width + pad_w, demo.image.height + pad_h),
        PADDING_BG_COLOR,
    )
    padded.paste(demo.image)
    demo.image = padded


def layout_height(layout: Layout, max_x: int, max_y: int) -> int:
    top_right, bottom_right = layout.bounding_poly.normalized_vertices[1:3]
    dx = bottom_right.x - top_right.x
    dy = bottom_right.y - top_right.y
    if dx == 0:
        v1_v2_distance = dy * max_y
    elif dy == 0:
        v1_v2_distance = dx * max_x
    else:
        v1_v2_distance = ((dx * max_x) ** 2 + (dy * max_y) ** 2) ** 0.5
    return int(v1_v2_distance + 0.5)


def tiff_container_for_images(images: Sequence[BytesIO]) -> tuple[BytesIO, str]:
    if len(images) < 2:
        raise ValueError("At least two images are expected")

    next_images = (normalize_image(image) for image in images)
    first_image = next(next_images)
    image_format, mime_type = "tiff", "image/tiff"
    compression = "tiff_lzw"  # Lossless (use lossy compression to further reduce size)
    params = dict(save_all=True, append_images=next_images, compression=compression)

    image_io = BytesIO()
    first_image.save(image_io, image_format, **params)
    image_io.seek(0)

    return image_io, mime_type


def do_render(demo: Demo) -> BytesIO:
    image_io = do_render_pass1(demo)
    image_io = do_render_pass2(demo, image_io)
    return image_io


def do_render_pass1(demo: Demo) -> BytesIO:
    next_frames = render_frames(demo)
    first_frame = next(next_frames)
    format = demo.options.format

    params: dict[str, Any] = dict()
    if 1 < demo.frame_count:
        if format == ImageFormat.GIF:
            format = ImageFormat.PNG  # Optimize as GIF in pass 2
        image_sequence = FrameSequence(format, next_frames)
        durations = animation_durations(demo)
        params.update(save_all=True, append_images=image_sequence, duration=durations)
    params.update(format=format.name)

    image_io = BytesIO()
    first_frame.save(image_io, **params)
    image_io.seek(0)

    return image_io


def do_render_pass2(demo: Demo, input_io: BytesIO) -> BytesIO:
    if demo.frame_count <= 1 or demo.options.format != ImageFormat.GIF:
        return input_io

    next_frames = gif_frames_gen(input_io)
    first_frame = next(next_frames)
    params = dict(format="GIF", save_all=True, append_images=next_frames)

    image_io = BytesIO()
    first_frame.save(image_io, **params)
    image_io.seek(0)

    return image_io


class FrameSequence:
    """Optimization to support generators in PilImage.save(append_images=...).
    Reduces memory consumption by limiting frame copies (can reach XX GiB otherwise).
    """

    def __init__(self, image_format: ImageFormat, next_frames: ImageIterator):
        # See PIL/PngImagePlugin.py (append_images is iterated twice)
        self.double_iter = image_format == ImageFormat.PNG
        self.next_frames = next_frames

    def __iter__(self):
        return self

    def __next__(self):
        if self.double_iter:
            # No need to iterate the first time (all frames have the same format)
            self.double_iter = False
            raise StopIteration()
        else:
            return next(self.next_frames)


def animation_durations(demo: Demo) -> list[int]:
    durations = [FRAME_DURATION_DEFAULT] * demo.frame_count
    if 1 < demo.frame_count:
        durations[0] = FRAME_DURATION_FIRST
    if 2 < demo.frame_count:
        durations[-1] = FRAME_DURATION_LAST
    return durations


def gif_frames_gen(image_io: BytesIO) -> ImageIterator:
    image = Image.open(image_io)
    assert 1 < image.n_frames

    # Build a paletted reference image with the most significant colors
    # The animation is iterative, with layers building up upon the first frame
    # Use first + last frames (some parts can gradually get hidden)
    ref = Image.new(image.mode, (image.width, image.height * 2))
    ref.paste(image, (0, 0))
    image.seek(image.n_frames - 1)
    ref.paste(image, (0, image.height))

    # Quantize all frames to 8bpp (base image was dithered in prepare_rendering)
    method = Image.Quantize.FASTOCTREE.value  # Best method for overlays
    dither = Image.Dither.NONE  # No dithering (fastest + no visual artefacts)
    ref = ref.quantize(method=method, dither=dither)
    for frame_index in range(image.n_frames):
        image.seek(frame_index)
        yield image.quantize(palette=ref, dither=dither, method=method)


def render_frames(demo: Demo) -> ImageIterator:
    copy_frame = prepare_rendering(demo)
    for frame in render_full_frames(demo):
        if demo.options.cropped:
            yield frame.crop(demo.image_crop_box)
        else:
            yield frame.copy() if copy_frame else frame


def prepare_rendering(demo: Demo) -> bool:
    demo.rendering = False
    demo.frame_count = sum(1 for _ in render_full_frames(demo))
    demo.rendering = True
    copy_frame = 1 < demo.frame_count and demo.options.format == ImageFormat.WEBP

    if demo.options.format == ImageFormat.GIF and 1 < demo.frame_count:
        # Quantize base image to 8bpp
        method = Image.Quantize.MEDIANCUT.value  # Best with dithering
        dither = Image.Dither.FLOYDSTEINBERG  # Best for real-life pictures
        demo.image = demo.image.quantize(method=method, dither=dither).convert("RGB")
        demo.draw = ImageDraw.Draw(demo.image, mode="RGBA")

    return copy_frame


def render_full_frames(demo: Demo) -> ImageIterator:
    yield from show_if_animated(demo)

    yield from render_ocr_levels(demo)  # Blocks + Paragraphs + Lines + Tokens
    yield from render_tables(demo)
    yield from render_form_fields(demo)
    yield from render_callout_info(demo)  # Barcodes + Entities

    yield from show_if_not_animated(demo)


def show_if_animated(demo: Demo) -> ImageIterator:
    if demo.options.animated:
        yield demo.image


def show_if_not_animated(demo: Demo) -> ImageIterator:
    if not demo.options.animated:
        yield demo.image


def render_ocr_levels(demo: Demo) -> ImageIterator:
    levels = dict(
        blocks=(demo.options.blocks, demo.page.blocks),
        paragraphs=(demo.options.paragraphs, demo.page.paragraphs),
        lines=(demo.options.lines, demo.page.lines),
        tokens=(demo.options.tokens, demo.page.tokens),
    )
    for level, (enabled, items) in levels.items():
        if not enabled:
            continue
        color = OCR_LEVEL_COLOR[level]
        for item in items:  # type: ignore
            if demo.rendering:
                render_layout(demo, item.layout, color)
            yield from show_if_animated(demo)


def render_tables(demo: Demo) -> ImageIterator:
    if not demo.options.tables:
        return
    color = TABLE_OUTLINE_COLOR
    for table in demo.page.tables:
        for row in (*table.header_rows, *table.body_rows):
            for cell in row.cells:
                if demo.rendering:
                    xy = vertices_from_layout(demo, cell.layout)
                    # Table cell bounding boxes are straight rectangles
                    render_round_rectangle(demo, xy, color)
                yield from show_if_animated(demo)


def render_form_fields(demo: Demo) -> ImageIterator:
    if not demo.options.fields:
        return
    form_fields = Demo.fields_sorted_by_reading_order(demo.page.form_fields)
    for form_field in form_fields:
        yield from render_form_field(demo, form_field)


def render_form_field(demo: Demo, form_field: FormField) -> ImageIterator:
    xy = None
    for i, layout in enumerate((form_field.field_name, form_field.field_value)):
        is_key = i == 0
        xy = vertices_from_layout(demo, layout)
        if demo.rendering:
            color = FORM_FIELD_NAME_COLOR if is_key else FORM_FIELD_VALUE_COLOR
            # Form field bounding boxes are straight rectangles
            render_round_rectangle(demo, xy, color)
        yield from show_if_animated(demo)

        if is_key and render_confidence(demo, layout, xy):
            yield from show_if_animated(demo)

    if xy is None or form_field.value_type not in (FILLED_CHECKBOX, UNFILLED_CHECKBOX):
        return
    if demo.rendering:
        checkbox_filled = form_field.value_type == FILLED_CHECKBOX
        text = "[×]" if checkbox_filled else "[ ]"
        center_xy = center_vertex(xy)
        text_color = FORM_FIELD_VALUE_COLOR
        outline_color = CHECK_BOX_OUTLINE_COLOR
        render_centered_text(demo, text, center_xy, text_color, outline_color)
    yield from show_if_animated(demo)


def render_callout_info(demo: Demo) -> ImageIterator:
    for vertices, text, r, text_xy, bg_color, fg_color in callout_info(demo):
        if vertices is not None:
            if demo.rendering:
                # Draw the reference item
                render_vertices(demo, vertices, fg_color)
                demo.draw.polygon(vertices, outline=fg_color, width=2)
            yield from show_if_animated(demo)

            # Highlight the path from the item to its callout
            if demo.rendering:
                path_xy = (vertices[1], (r[0], r[1]), (r[0], r[3]), vertices[2])
                render_vertices(demo, path_xy, fg_color)
            yield from show_if_animated(demo)

        # Draw the callout
        if demo.rendering:
            demo.draw.rectangle(r, fill=bg_color, outline=fg_color, width=2)
            demo.draw.text(
                text_xy, text, fill=DEFAULT_TEXT_COLOR, font=demo.font_median
            )
        yield from show_if_animated(demo)


def callout_info(demo: Demo) -> Iterator[CalloutInfo]:
    font = demo.font_median
    if font is None:
        return

    callout_info_gens = []
    if demo.options.barcodes:
        callout_info_gens.append(callout_info_for_barcodes(demo))
    if demo.options.entities:
        callout_info_gens.append(callout_info_for_entities(demo))
    if not callout_info_gens:
        return

    box_x = demo.page_crop_box[2] + demo.text_height_median
    box_y = demo.page_crop_box[1] + CROP_MARGIN
    offset_y = demo.text_height_median * 2
    box_padding = demo.text_padding * 2

    colors = color_gen()
    for callout_info_gen in callout_info_gens:
        for vertices, text, confidence in callout_info_gen:
            text = text.replace("\n", "\\n")  # Show new line characters
            text_size = font.getsize(text)
            box_w, box_h = text_size[0] + box_padding, text_size[1] + box_padding
            rect = (box_x, box_y, box_x + box_w, box_y + box_h)
            text_xy = (box_x + demo.text_padding, box_y + demo.text_padding)
            box_y += offset_y
            if confidence is None or confident_enough(confidence):
                bg_color = DEFAULT_BG_COLOR
                fg_color = next(colors)
            else:
                bg_color = color_transparent_like_a_highlighter(DEFAULT_BG_COLOR)
                fg_color = LOW_CONFIDENCE_BG_COLOR

            yield vertices, text, rect, text_xy, bg_color, fg_color


def callout_info_for_barcodes(demo: Demo) -> Iterator[CalloutInfoBase]:
    def reading_order_key_for_barcode(barcode: Barcode) -> TextAnchorKey:
        return reading_order_key_for_layout(barcode.layout)

    barcodes = sorted(demo.page.detected_barcodes, key=reading_order_key_for_barcode)
    for barcode in barcodes:
        vertices = vertices_from_bounding_poly(demo, barcode.layout.bounding_poly)
        text = display_text_for_barcode(barcode)
        confidence = None  # barcode.layout.confidence is not present

        yield vertices, text, confidence


def display_text_for_barcode(detected_barcode: Barcode) -> str:
    barcode = detected_barcode.barcode
    return f"{barcode.value_format}[{barcode.format_}]: {barcode.raw_value}"


def callout_info_for_entities(demo: Demo) -> Iterator[CalloutInfoBase]:
    def flatten(
        entities: Iterable[Entity],
        parent_page_ref: Document.PageAnchor.PageRef | None = None,
    ) -> Iterator[Entity]:
        page_index = demo.options.page - 1
        for entity in entities:
            render, page_ref = will_render_entity(entity, parent_page_ref, page_index)
            if render:
                yield entity
            if entity.properties:
                yield from flatten(entity.properties, page_ref)

    def reading_order_key_for_entity(entity: Entity) -> TextAnchorKey:
        return reading_order_key_for_text_anchor(entity.text_anchor, default_text_index)

    def entity_vertices_gen() -> Iterator[tuple[Entity, Vertices | None]]:
        page_index = demo.options.page - 1
        for entity in entities:
            if not entity.page_anchor.page_refs:
                yield entity, None
                continue
            for page_ref in entity.page_anchor.page_refs:
                if page_ref.page != page_index:
                    continue
                if page_ref.bounding_poly.normalized_vertices:
                    vertices = vertices_from_bounding_poly(demo, page_ref.bounding_poly)
                else:
                    vertices = None
                yield entity, vertices

    default_text_index = len(demo.document.text)  # Place entities with no anchor last
    entities = sorted(flatten(demo.document.entities), key=reading_order_key_for_entity)

    for entity, vertices in entity_vertices_gen():
        entity_text, normalized = text_for_entity(demo, entity)
        caption = entity.type_
        if normalized:
            caption += "(n)"
        confidence = entity.confidence if "confidence" in entity else None
        if confidence is not None and not confident_enough(confidence):
            caption += f"[{confidence:.0%}]"
        text = f"{caption}: {entity_text}"

        yield vertices, text, confidence


def confident_enough(confidence: float) -> bool:
    return CONFIDENCE_THRESHOLD <= confidence


def is_quality_score_entity(entity: Document.Entity) -> bool:
    return entity.type_.startswith("quality/") or entity.type_ == "quality_score"


def will_render_entity(
    entity: Document.Entity,
    parent_page_ref: Document.PageAnchor.PageRef | None = None,
    page_index: int | None = None,
) -> tuple[bool, Document.PageAnchor.PageRef | None]:
    """Returns whether the entity will be rendered (some are skipped for the sake of simplicity)."""
    if is_quality_score_entity(entity):
        render = "confidence" in entity
        return render, parent_page_ref

    if entity.properties:
        # Don't render parent properties (arbitrary choice to limit what's rendered)
        return False, parent_page_ref

    render = True
    if page_index is not None and entity.page_anchor.page_refs:
        # The entity is page relative, make sure it's visible
        for page_ref in entity.page_anchor.page_refs:
            if page_ref is not None and page_ref.page == page_index:
                parent_page_ref = page_ref
                break  # Entity is visible on current page
        else:
            render = False

    return render, parent_page_ref


def color_gen() -> Iterator[PilColor]:
    colors = (GOOGLE_BLUE, GOOGLE_RED, GOOGLE_YELLOW, GOOGLE_GREEN)
    while True:
        for color in colors:
            yield color


def text_for_entity(demo: Demo, entity: Entity) -> tuple[str, bool]:
    if demo.options.normalized:
        text, normalized = normalized_text_for_entity(entity)
    else:
        text, normalized = default_text_for_entity(entity)
    if ENTITY_TEXT_MAX_CHARS < len(text):
        text = text[:ENTITY_TEXT_MAX_CHARS] + "…"

    return text, normalized


def normalized_text_for_entity(entity: Entity) -> tuple[str, bool]:
    """Return the entity normalized text (if possible) and whether it's normalized."""
    normalized_value = entity.normalized_value

    if "datetime_value" in normalized_value:
        dt = normalized_value.datetime_value
        text = f"{dt.hours:02}:{dt.minutes:02}"  # type: ignore
        if dt.seconds:  # type: ignore
            text += f":{dt.seconds:02}"  # type: ignore
        return text, True

    if normalized_value.text and not entity.type_.startswith("fraud_signals"):
        return normalized_value.text, True

    return default_text_for_entity(entity)


def default_text_for_entity(entity: Entity) -> tuple[str, bool]:
    """Return the entity default text and whether it's normalized."""
    if entity.mention_text:
        return entity.mention_text.strip("\n"), False

    if entity.normalized_value.text:
        # Typical for enriched info (e.g. supplier_name)
        return entity.normalized_value.text, True

    # Typical for qualitative info (e.g. quality/defect_glare)
    return f"{entity.confidence:.0%}", False


def vertices_from_layout(demo: Demo, layout: Layout) -> Vertices:
    return vertices_from_bounding_poly(demo, layout.bounding_poly)


def vertices_from_bounding_poly(demo: Demo, bounding_poly: BoundingPoly) -> Vertices:
    if bounding_poly.vertices:
        return Vertices((v.x, v.y) for v in bounding_poly.vertices)

    vertices = bounding_poly.normalized_vertices
    img_w, img_h = demo.input_width, demo.input_height
    return Vertices((int(v.x * img_w + 0.5), int(v.y * img_h + 0.5)) for v in vertices)


def center_vertex(vertices: Vertices) -> Vertex:
    """Returns the center vertex of v0 ↔ v2 if input is (v0, v1, v2, v3), v0 otherwise."""
    if len(vertices) != 4:
        return vertices[0]
    v1, v2 = vertices[0], vertices[2]
    return (int((v1[0] + v2[0]) / 2 + 0.5), int((v1[1] + v2[1]) / 2 + 0.5))


def render_layout(demo: Demo, layout: Layout, color: PilColor):
    xy = vertices_from_layout(demo, layout)
    render_vertices(demo, xy, color)
    render_confidence(demo, layout, xy)


def render_vertices(demo: Demo, xy: Vertices, color: PilColor):
    fill = color_transparent_like_a_highlighter(color)
    demo.draw.polygon(xy, fill=fill)


def render_confidence(demo: Demo, layout: Layout, xy: Vertices) -> bool:
    if not demo.show_confidence:
        return False
    if not demo.rendering:
        return True

    text = f"{layout.confidence:.0%}"
    center_xy = center_vertex(xy)
    text_color = CONFIDENCE_TEXT_COLOR
    outline_color = (
        DEFAULT_BG_COLOR
        if confident_enough(layout.confidence)
        else LOW_CONFIDENCE_BG_COLOR
    )
    render_centered_text(demo, text, center_xy, text_color, outline_color)
    return True


def render_text(
    demo: Demo,
    text: str,
    xy: Vertex,
    text_color: PilColor | None = None,
    outline_color: PilColor | None = None,
):
    do_render_text(demo, text, "la", xy, text_color, outline_color)


def render_centered_text(
    demo: Demo,
    text: str,
    xy: Vertex,
    text_color: PilColor | None = None,
    outline_color: PilColor | None = None,
):
    do_render_text(demo, text, "mm", xy, text_color, outline_color)


def do_render_text(
    demo: Demo,
    text: str,
    anchor: str,
    xy: Vertex,
    text_color: PilColor | None = None,
    outline_color: PilColor | None = None,
):
    if text_color is None:
        text_color = DEFAULT_TEXT_COLOR
    demo.draw.text(
        text=text,
        xy=xy,
        anchor=anchor,
        fill=text_color,
        stroke_fill=outline_color,
        stroke_width=demo.text_outline_width,
        font=demo.font_min,
    )


def render_round_rectangle(demo: Demo, xy: Vertices, color: PilColor):
    (x0, y0), (x2, y2) = xy[0], xy[2]  # Use top-left and bottom-right vertices
    tl_br = ((x0, y0), (x2 + 1, y2 + 1))
    color = color_transparent_for_outlines(color)
    width = demo.border_width
    demo.draw.rounded_rectangle(tl_br, radius=width, outline=color, width=width)


def color_transparent_like_a_highlighter(color: PilColor) -> PilColor:
    return make_color_transparent(color, 0x44)


def color_transparent_for_outlines(color: PilColor) -> PilColor:
    return make_color_transparent(color, 0x80)


def make_color_transparent(color: PilColor, alpha: int) -> PilColor:
    t = ImageColor.getrgb(color)
    return f"#{t[0]:02x}{t[1]:02x}{t[2]:02x}{alpha:02x}" if len(t) == 3 else color
