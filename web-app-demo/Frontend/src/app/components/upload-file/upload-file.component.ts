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

import { Component, Input, OnInit } from "@angular/core";
import { Subscription } from "rxjs";
import { DataSharingServiceService } from "src/app/data-sharing-service.service";

@Component({
  selector: "app-upload-file",
  templateUrl: "./upload-file.component.html",
  styleUrls: ["./upload-file.component.css"],
})
/**
 * UploadFileComponents - handles file uploads
 */
export class UploadFileComponent implements OnInit {
  @Input()
  requiredFileType: string | undefined;

  fileName = "";
  fileContent = "";

  uploadProgress = null;
  uploadSub = null;

  message!: string;
  subscription!: Subscription;

  /**
   * constructor for UploadFileComponent
   * @constructor
   * @param {DataSharingServiceService} data - data sharing service
   */
  constructor(public data: DataSharingServiceService) {}

  /**
   * subscribes to specific variables on init
   * @return {void}
   */
  ngOnInit(): void {
    this.subscription = this.data.fileName.subscribe(
      (message) => (this.fileName = message)
    );
    this.subscription = this.data.file.subscribe(
      (message) => (this.fileContent = message)
    );
  }

  /**
   * Stores the file that was uploaded to correct variables
   * @param {Event} e - the event the holds the file information.
   * @return {void}
   */
  async handleFileInput(e: Event) {
    const files = (e.target as HTMLInputElement).files!;
    this.fileName = files[0].name;
    if (files[0].type == "application/pdf" && files[0].size < 20000001) {
      this.data.changeShowError(false);
      this.data.changeErrorMessage("");
      this.data.changeFile(files[0]);
      this.data.changeFileName(files[0].name);
    } else {
      this.data.changeShowError(true);
      this.data.changeErrorMessage(
        "ERROR : File type does not match accepted type (PDF)"
      );
    }
  }
}
