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

import { Component, OnInit } from "@angular/core";
import { Subscription } from "rxjs";
import { DataSharingServiceService } from "src/app/data-sharing-service.service";

@Component({
  selector: "app-canvas",
  templateUrl: "./canvas.component.html",
  styleUrls: ["./canvas.component.css"],
})
/**
 * CanvasComponent - the canvas to draw on
 */
export class CanvasComponent implements OnInit {
  subscription!: Subscription;

  /**
   * constructor for CanvasComponent
   * @constructor
   * @param {DataSharingServiceService} data - data sharing service
   */
  constructor(public data: DataSharingServiceService) {}

  /**
   * initializes component
   * @return {void}
   */
  ngOnInit(): void {
    console.log("canvas init");
  }
}
