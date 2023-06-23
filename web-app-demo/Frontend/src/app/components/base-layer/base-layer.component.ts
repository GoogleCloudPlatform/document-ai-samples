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

@Component({
  selector: "app-base-layer",
  templateUrl: "./base-layer.component.html",
  styleUrls: ["./base-layer.component.css"],
})
/**
 * BaseLayerComponent - base layer for all components to generate
 */
export class BaseLayerComponent implements OnInit, DoCheck {
  /**
   * constructor for BaseLayerComponent
   * @constructor
   * @param {DataSharingServiceService} data - data sharing service
   */
  constructor(public data: DataSharingServiceService) {}
  public processingIsDone!: any;

  message!: string;
  subscription!: Subscription;

  processor!: string;
  fileName!: string;
  file!: any;
  showBounding!: boolean;
  documentProto!: any;
  processIsDone!: boolean;
  processInProgress!: boolean;
  showError!: boolean;
  errorMessage!: string;

  /**
   * initializes component and subscribes to variables
   * @return {void}
   */
  async ngOnInit() {
    //Initialized
  }

  /**
   * check if any variable changed
   * @return {void}
   */
  ngDoCheck() {
    this.subscription = this.data.processor.subscribe(
      (message) => (this.processor = message)
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
    this.subscription = this.data.processingInProgress.subscribe(
      (message) => (this.processInProgress = message)
    );
    this.subscription = this.data.showError.subscribe(
      (message) => (this.showError = message)
    );
    this.subscription = this.data.errorMessage.subscribe(
      (message) => (this.errorMessage = message)
    );
  }
}
