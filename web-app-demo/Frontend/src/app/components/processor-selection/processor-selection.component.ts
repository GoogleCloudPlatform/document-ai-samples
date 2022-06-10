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
import { DocumentAnnotation } from "../../document-annotation";
import { AppComponent } from "../../app.component";

import { OCR_PROCESSOR, FORM_PARSER, BLUE, RED, ORANGE, LAYER2 } from "../../consts";

export interface File {
  content: string;
  name: string;
  type: string;
  size: number;
}

@Component({
  selector: "app-processor-selection",
  templateUrl: "./processor-selection.component.html",
  styleUrls: ["./processor-selection.component.css"],
})
/**
 * ProcessSelectionComponent - handles file processing
 */
export class ProcessorSelectionComponent implements OnInit, DoCheck {

  /**
   * constructor for ProcessorSelectionComponent
   * @constructor
   * @param {DataSharingServiceService} data - data sharing service
   */
  constructor(public data: DataSharingServiceService) { }

  activeProcessor!: IProcessor;
  processorList: IProcessor[] = [];
  fileName: string = "";
  file!: any;
  showBounding!: boolean;
  showError!: boolean;
  documentProto!: any;
  processIsDone!: boolean;
  processInProgress = false;
  subscription!: Subscription;
  url!: string[];
  backend!: string;

  /**
   * On init setup subscribed variables and inits backend
   * @return {void}
   */
  async ngOnInit(): Promise<void> {

    // Special case for Cloud Run Button
    if (location.href.includes("-")) {
      this.url = location.href.split("-");
      this.url.splice(0, 3);
      this.backend = "https://backend-" + this.url.join("-");
    } else if (location.href.includes("localhost")) {
      this.backend = "http://localhost:5000/";
    } else {
      this.url = [location.href];
      this.backend = location.href;
    }

    await fetch(this.backend + "api/processor/list", {
      method: "GET",
      mode: "cors",
    })
      .then(async (response) => {
        const json = await response.json();
        if (json["resultStatus"] == "ERROR") {
          throw new Error(json["errorMessage"]);
        }

        this.processorList = json["processorList"];
      })
      .catch((error) => {
        this.data.changeShowError(true);
        this.data.changeErrorMessage(error);
      });

    this.subscription = this.data.activeProcessor.subscribe(
      (message) => (this.activeProcessor = message)
    );
    this.subscription = this.data.fileName.subscribe(
      (message) => (this.fileName = message)
    );
    this.subscription = this.data.file.subscribe(
      (message) => (this.file = message)
    );
    this.subscription = this.data.showBounding.subscribe(
      (message) => (this.showBounding = message)
    );
    this.subscription = this.data.documentProto.subscribe(
      (message) => (this.documentProto = message)
    );
    this.subscription = this.data.processingIsDone.subscribe(
      (message) => (this.processIsDone = message)
    );
    this.subscription = this.data.showError.subscribe(
      (message) => (this.showError = message)
    );
  }

  /**
   * checks if selected processor has changed
   * @return {void}
   */
  ngDoCheck() {
    if (this.activeProcessor) {
      this.data.changeActiveProcessor(this.activeProcessor);
    }
  }

  /**
   * Process uploaded document
   * @return {void}
   */
  processDocument() {
    this.data.changeProcessInProgress(true);
    if (this.fileName == "" || this.file == null) {
      this.data.changeProcessInProgress(false);
      this.data.changeShowError(true);
      this.data.changeErrorMessage("ERROR : File was not selected");
      return;
    }

    const data = new FormData();
    data.append("file", this.file);
    data.append("filename", this.fileName);
    data.append("processorName", this.activeProcessor.name);
    data.append("showBounding", String(this.showBounding));

    fetch(this.backend + "api/docai", {
      method: "POST",
      mode: "cors",
      body: data,
    })
      .then(async (response) => {
        const json = await response.json();
        if (
          json["resultStatus"] != undefined &&
          json["resultStatus"] == "ERROR"
        ) {
          throw new Error(json["errorMessage"]);
        } else {
          this.data.changeDocumentProto(json);
          return json;
        }
      })
      .then(() => {
        this.data.changeProcessIsDone(true);
        this.data.changeProcessInProgress(false);
        const canvas = <HTMLCanvasElement>document.getElementById(LAYER2)!;
        const context = canvas.getContext("2d")!;
        const background = new Image();
        background.src =
          "data:image/png;base64," +
          this.documentProto.document.pages[0].image.content;

        // Make sure the image is loaded first otherwise nothing will draw.
        background.onload = () => {
          context.drawImage(
            background,
            0,
            0,
            background.width,
            background.height,
            0,
            0,
            canvas.width,
            canvas.height
          );
          this.drawBoxes(context, canvas);
        };
      })
      .catch((error) => {
        this.data.changeShowError(true);
        this.data.changeErrorMessage(error);
        this.data.changeProcessInProgress(false);
      });
  }

  /**
   * Calls drawBoundingBoxes to draw bounding boxes for document
   * @param {CanvasRenderingContext2D} context - the context of rendered canvas
   * @param {HTMLCanvasElement} canvas - canvas to draw on
   * @return {void}
   */
  drawBoxes(context: CanvasRenderingContext2D, canvas: HTMLCanvasElement) {
    const data = this.documentProto;

    const drawClient = new DocumentAnnotation();

    switch (this.activeProcessor.type) {
      case OCR_PROCESSOR:
        for (const block of data.document.pages[0].blocks) {
          drawClient.drawBoundingBoxes(
            context,
            canvas,
            block.layout.boundingPoly,
            ORANGE,
            "stroke",
            []
          );
        }
        break;
      case FORM_PARSER:
        for (const formField of data.document.pages[0].formFields) {
          drawClient.drawBoundingBoxes(
            context,
            canvas,
            formField.fieldName.boundingPoly,
            BLUE,
            "stroke",
            []
          );
          drawClient.drawBoundingBoxes(
            context,
            canvas,
            formField.fieldValue.boundingPoly,
            RED,
            "stroke",
            []
          );
        }
        break;
      default:
        // Specialized Processor
        for (const entity of data.document.entities) {
          if (entity?.pageAnchor?.pageRefs[0]?.boundingPoly) {
            drawClient.drawBoundingBoxes(
              context,
              canvas,
              entity.pageAnchor.pageRefs[0].boundingPoly,
              BLUE,
              "stroke",
              []
            );
          }
        }
    }
    return;
  }
}
