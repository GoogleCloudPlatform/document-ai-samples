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

import { Injectable } from "@angular/core";
import { BehaviorSubject } from "rxjs";

@Injectable({
  providedIn: "root",
})
/**
 * Class that handles Data Sharing
 */
export class DataSharingServiceService {
  private fileNameSource = new BehaviorSubject("");
  private fileSource = new BehaviorSubject("");
  private documentProtoSource = new BehaviorSubject("");
  private processingIsDoneSource = new BehaviorSubject(false);
  private processorSource = new BehaviorSubject("");
  private processIsDoneSource = new BehaviorSubject(false);
  private showBoundingSource = new BehaviorSubject(false);
  private processingInProgressSource = new BehaviorSubject(false);
  private errorMessageSource = new BehaviorSubject("");
  private showErrorSource = new BehaviorSubject(false);

  fileName = this.fileNameSource.asObservable();
  file = this.fileSource.asObservable();
  documentProto = this.documentProtoSource.asObservable();
  processingIsDone = this.processIsDoneSource.asObservable();
  processor = this.processorSource.asObservable();
  processorIsDone = this.processIsDoneSource.asObservable();
  showBounding = this.showBoundingSource.asObservable();
  processingInProgress = this.processingInProgressSource.asObservable();
  errorMessage = this.errorMessageSource.asObservable();
  showError = this.showErrorSource.asObservable();

  /**
   * changes the fileName variable
   * @param {any} message we want to set.
   * @return {void}
   */
  changeFileName(message: string) {
    this.fileNameSource.next(message);
  }
  /**
   * changes the file variable
   * @param {any} message we want to set.
   * @return {void}
   */
  changeFile(message: any) {
    this.fileSource.next(message);
  }

  /**
   * changes the documentProto variable
   * @param {any} message we want to set.
   * @return {void}
   */
  changeDocumentProto(message: any) {
    this.documentProtoSource.next(message);
  }

  /**
   * changes the processingIsDone variable
   * @param {any} message we want to set.
   * @return {void}
   */
  changeProcessingIsDone(message: boolean) {
    this.processingIsDoneSource.next(message);
  }

  /**
   * changes the processor variable
   * @param {any} message we want to set.
   * @return {void}
   */
  changeProcessor(message: string) {
    this.processorSource.next(message);
  }

  /**
   * changes the ProcessIsDone variable
   * @param {any} message we want to set.
   * @return {void}
   */
  changeProcessIsDone(message: boolean) {
    this.processIsDoneSource.next(message);
  }

  /**
   * changes the ShowBounding variable
   * @param {any} message we want to set.
   * @return {void}
   */
  changeShowBounding(message: boolean) {
    this.showBoundingSource.next(message);
  }

  /**
   * changes the ProcessInProgress variable
   * @param {any} message we want to set.
   * @return {void}
   */
  changeProcessInProgress(message: boolean) {
    this.processingInProgressSource.next(message);
  }

  /**
   * changes the errorMessage variable
   * @param {any} message we want to set.
   * @return {void}
   */
  changeErrorMessage(message: string) {
    this.errorMessageSource.next(message);
  }

  /**
   * changes the showError variable
   * @param {any} message we want to set.
   * @return {void}
   */
  changeShowError(message: boolean) {
    this.showErrorSource.next(message);
  }
}
