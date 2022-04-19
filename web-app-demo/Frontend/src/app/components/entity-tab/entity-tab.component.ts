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

/* eslint new-cap: ["error", { "capIsNew": false }]*/

import { Component, DoCheck, OnInit } from "@angular/core";
import { Subscription } from "rxjs";
import { DataSharingServiceService } from "src/app/data-sharing-service.service";
import { DocumentAnnotation } from "src/app/document-annotation";

export interface ExtractedText {
  fieldValue: string;
  fieldName: string;
  bounding: any;
  confidence: number;
}

let DATA: ExtractedText[] = [];

const LAYER1 = "layer1";
const LAYER2 = "layer2";
const LAYER3 = "layer3";

const RED = "rgba(255, 0, 0, 0.25)";
const BLUE = "rgba(0, 0, 255, 0.25)";
const ORANGE = "rgba(255,165,0, 0.25)";

export interface dataSource {
  fieldValue: string;
  fieldName: string;
  bounding: [{ x: number; y: number }];
  confidence: number;
}

interface dataSourceArray extends Array<dataSource> {}

@Component({
  selector: "app-entity-tab",
  templateUrl: "./entity-tab.component.html",
  styleUrls: ["./entity-tab.component.css"],
})
/**
 * EntityTabComponent - presents the extracted text
 */
export class EntityTabComponent implements OnInit, DoCheck {
  dataSource: dataSourceArray | undefined;
  processIsDone!: boolean;
  processor!: string;
  documentProto: any;

  subscription!: Subscription;

  /**
   * constructor for EntityTabComponent
   * @constructor
   * @param {DataSharingServiceService} data - data sharing service
   */
  constructor(public data: DataSharingServiceService) {}

  /**
   * subscribe to variables
   * @return {void}
   */
  ngOnInit() {
    this.subscription = this.data.processorIsDone.subscribe(
      (message) => (this.processIsDone = message)
    );
    this.subscription = this.data.processor.subscribe(
      (message) => (this.processor = message)
    );
    this.subscription = this.data.documentProto.subscribe(
      (message) => (this.documentProto = message)
    );
  }

  /**
   * check if document processing is done
   * then get the text for document
   * @return {void}
   */
  async ngDoCheck() {
    if (this.processIsDone == true) {
      this.clearAll();
      DATA = [];

      switch (this.processor) {
        case "OCR":
          this.extractOCRText(DATA);
          break;
        case "FORM":
          this.extractFormText(DATA);
          break;
        case "INVOICE":
          this.extractInvoiceText(DATA);
          break;
      }

      this.data.changeProcessIsDone(false);
      this.dataSource = DATA;
    }
  }

  /**
   * Get text
   * @param {any} textAnchor
   * @param {any} text
   * @return {void}
   */
  getText(textAnchor: any, text: any) {
    if (!textAnchor.textSegments || textAnchor.textSegments.length === 0) {
      throw new Error("ERROR: Could not find text for given text anchor");
    }

    // First shard in document doesn't have startIndex property
    const startIndex = textAnchor.textSegments[0].startIndex || 0;
    const endIndex = textAnchor.textSegments[0].endIndex;

    return text.substring(startIndex, endIndex);
  }

  /**
   * Get OCR text from document proto
   * @param {ExtractedText[]} data - used for frontend display
   * @return {void}
   */
  extractOCRText(
    data:
      | ExtractedText[]
      | {
          fieldValue: any;
          fieldName: string;
          bounding: { x: any; y: any }[];
          confidence: any;
        }[]
  ) {
    for (const page of this.documentProto.document.pages) {
      for (const block of page.blocks) {
        const paragraphText = this.getText(
          block.layout.textAnchor,
          this.documentProto.document.text
        );
        const ocrVertices = [];
        for (const vertex of block.layout.boundingPoly.normalizedVertices) {
          ocrVertices.push({ x: vertex.x, y: vertex.y });
        }

        data.push({
          fieldValue: paragraphText,
          fieldName: "",
          bounding: ocrVertices,
          confidence: block.layout.confidence,
        });
      }
    }
  }

  /**
   * Get form text from document proto
   * @param {ExtractedText[]} data - used for frontend display
   * @return {void}
   */
  extractFormText(
    data:
      | ExtractedText[]
      | {
          fieldValue: any;
          fieldName: any;
          bounding: {
            value: { x: any; y: any }[];
            name: { x: any; y: any }[];
          }[];
          confidence: any;
        }[]
  ) {
    for (const page of this.documentProto.document.pages) {
      for (const field of page.formFields) {
        const fieldName = this.getText(
          field.fieldName.textAnchor,
          this.documentProto.document.text
        );
        const fieldValue = this.getText(
          field.fieldValue.textAnchor,
          this.documentProto.document.text
        );

        const formVertices = [];
        const verticesFieldName = [];
        const verticesFieldValue = [];
        for (const vertex of field.fieldName.boundingPoly.normalizedVertices) {
          verticesFieldName.push({ x: vertex.x, y: vertex.y });
        }
        for (const vertex of field.fieldValue.boundingPoly.normalizedVertices) {
          verticesFieldValue.push({ x: vertex.x, y: vertex.y });
        }
        formVertices.push({
          value: verticesFieldValue,
          name: verticesFieldName,
        });

        data.push({
          fieldValue: fieldValue,
          fieldName: fieldName,
          bounding: formVertices,
          confidence: field.fieldName.confidence,
        });
      }
    }
  }

  /**
   * Get invoice text from document proto
   * @param {ExtractedText[]} data - used for frontend display
   * @return {void}
   */
  extractInvoiceText(
    data:
      | ExtractedText[]
      | {
          fieldValue: any;
          fieldName: any;
          bounding: { x: any; y: any }[];
          confidence: any;
        }[]
  ) {
    for (const entity of this.documentProto.document.entities) {
      const ocrVertices = [];
      const normalizedVertices =
        entity.pageAnchor.pageRefs[0].boundingPoly.normalizedVertices;
      for (const vertex of normalizedVertices) {
        ocrVertices.push({ x: vertex.x, y: vertex.y });
      }
      data.push({
        fieldValue: entity.mentionText,
        fieldName: entity.type,
        bounding: ocrVertices,
        confidence: entity.confidence,
      });
    }
  }

  /**
   * Highlights the bounding box that is selected
   * @param {any} data - the selecting box
   * @return {void}
   */
  highlightBoundingBoxes(data: any) {
    const canvas = <HTMLCanvasElement>document.getElementById(LAYER3)!;

    // Gets the canvas and sets teh editing mode to draw over everything
    const context = canvas.getContext("2d")!;

    const drawClient = new DocumentAnnotation();

    context.globalCompositeOperation = "source-over";
    if (this.processor == "OCR" || this.processor == "INVOICE") {
      const color = this.processor == "OCR" ? ORANGE : BLUE;
      drawClient.drawBoundingBoxes(
        context,
        canvas,
        null,
        color,
        "fill",
        data.bounding
      );
    } else if (this.processor == "FORM") {
      drawClient.drawBoundingBoxes(
        context,
        canvas,
        null,
        RED,
        "fill",
        data.bounding[0].value
      );
      drawClient.drawBoundingBoxes(
        context,
        canvas,
        null,
        BLUE,
        "fill",
        data.bounding[0].name
      );
    }
  }

  /**
   * Clears only bounding boxes on canvas
   * @return {void}
   */
  clearBoundingBoxes() {
    const canvas = <HTMLCanvasElement>document.getElementById(LAYER3)!;
    const context = canvas.getContext("2d")!;
    context.clearRect(0, 0, canvas.width, canvas.height);
  }
  /**
   * Clears all canvases
   * @return {void}
   */
  clearAll() {
    let canvas = <HTMLCanvasElement>document.getElementById(LAYER1)!;
    let context = canvas.getContext("2d")!;
    context.clearRect(0, 0, canvas.width, canvas.height);
    canvas = <HTMLCanvasElement>document.getElementById(LAYER2)!;
    context = canvas.getContext("2d")!;
    context.clearRect(0, 0, canvas.width, canvas.height);
    canvas = <HTMLCanvasElement>document.getElementById(LAYER3)!;
    context = canvas.getContext("2d")!;
    context.clearRect(0, 0, canvas.width, canvas.height);
  }
}
