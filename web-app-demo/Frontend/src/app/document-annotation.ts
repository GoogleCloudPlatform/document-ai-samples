/**
 * Copyright 2022 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

export interface BoundingPoly {
  normalizedVertices: NormalizedVerticesEntity[];
}
export interface NormalizedVerticesEntity {
  x: number;
  y: number;
}

interface BoundingPolyArray extends Array<NormalizedVerticesEntity> {}

/**
 * Class that handles bounding box drawing
 */
export class DocumentAnnotation {
  /**
   * Draws bounding boxes on canvas.
   * @param {CanvasRenderingContext2D} context - context of the canvas
   * @param {HTMLCanvasElement} canvas - canvas to draw on
   * @param {BoundingPoly | null} boundingPoly - the vertices of the polygon
   * @param {any} color - the color of the bounding box
   * @param {any} fillOrStroke - if the function should fill or stroke
   * @param {any[]} boundingPolyArray - array of boundingPoly
   * @return {void}
   */
  drawBoundingBoxes(
    context: CanvasRenderingContext2D,
    canvas: HTMLCanvasElement,
    boundingPoly: BoundingPoly | null,
    color: string,
    fillOrStroke: string,
    boundingPolyArray: BoundingPolyArray
  ): void {
    let ocrVertices = [];
    context.strokeStyle = color;

    let width = 1;
    let height = 1;

    if (fillOrStroke == "fill") {
      height = canvas.height;
      width = canvas.width;
      ocrVertices = boundingPolyArray;
      context.globalCompositeOperation = "source-over";
      context.fillStyle = color;
    } else {
      for (let j = 0; j < boundingPoly!.normalizedVertices.length; j++) {
        ocrVertices.push({
          x: boundingPoly!.normalizedVertices[j].x * canvas.width,
          y: boundingPoly!.normalizedVertices[j].y * canvas.height,
        });
      }
      context.strokeStyle = color;
    }

    context.beginPath();
    context.moveTo(ocrVertices[0].x * width, ocrVertices[0].y * height);
    context.lineTo(ocrVertices[1].x * width, ocrVertices[1].y * height);
    context.lineTo(ocrVertices[2].x * width, ocrVertices[2].y * height);
    context.lineTo(ocrVertices[3].x * width, ocrVertices[3].y * height);
    context.closePath();

    if (fillOrStroke == "fill") {
      context.fill();
    } else {
      context.stroke();
    }

    ocrVertices = [];
  }
}
