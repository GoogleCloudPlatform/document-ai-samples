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

import { Component } from "@angular/core";
import { DataSharingServiceService } from "./data-sharing-service.service";
import { Router } from "@angular/router";
import { Subscription } from "rxjs";

declare var backendURL: string;

@Component({
  selector: "app-root",
  templateUrl: "./app.component.html",
  styleUrls: ["./app.component.css"],
})
/**
 * AppComponent sets title and backendURL
 */
export class AppComponent {
  title = "Document AI Modular App";
  sharingClient = new DataSharingServiceService();
  public static backendURL = "";

  activeProcessor!: IProcessor;
  fileName: string = "";
  file!: any;
  showBounding!: boolean;
  showError!: boolean;
  documentProto!: any;
  processIsDone!: boolean;
  subscription!: Subscription;
  url!: string[];
  backend!: string;

  /**
   * constructor for ProcessorSelectionComponent
   * @constructor
   * @param {DataSharingServiceService} data - data sharing service
   */
  constructor(public data: DataSharingServiceService) { }

  async ngOnInit(): Promise<void> {
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

}
