/**
 * Copyright 2023 Google LLC
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

/**
 * This code sample shows how to the call the Cloud Document AI API using Apps
 * Script with OAuth. Before running this code please see the documentation
 * guide on getting set up with Document AI processors:
 * https://cloud.google.com/document-ai/docs/create-processor.
 */

const PROJECT_ID = "";
const LOCATION = ""; // Format is 'us' or 'eu'
const PROCESSOR_ID = ""; // Create processor in Cloud Console

const TEST_FILE_ID = ""; // Drive ID of an image or pdf to use for testing

const STORAGE_BUCKET = ""; // Cloud Storage Bucket to Upload
const FILE_PATH = ""; // File Path for Cloud Storage Upload

/**
 * Creates variables for the service account key and email address.
 * Authorization to DocAI requires a GCP service account with a Document AI role.
 */
const SERVICE_ACCOUNT = {
  private_key: "",
  client_email: "",
};

function processDocument(file) {
  var service = getService();
  if (!service.hasAccess()) {
    Logger.log(service.getLastError());
    return;
  }

  // Processor name, should look like: `projects/${projectId}/locations/${location}/processors/${processorId}`;
  const name =
    "projects/" +
    PROJECT_ID +
    "/locations/" +
    LOCATION +
    "/processors/" +
    PROCESSOR_ID;
  var apiEndPoint =
    "https://" +
    LOCATION +
    "-documentai.googleapis.com/v1/" +
    name +
    ":process";

  var docBytes = Utilities.base64Encode(file.getBlob().getBytes());
  var mimeType = file.getMimeType();

  // Creates a structure with the text and request type.
  var requestData = {
    name,
    rawDocument: {
      content: docBytes,
      mimeType: mimeType,
    },
  };

  // Packages all of the options and the data together for the call.
  var options = {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: "Bearer " + service.getAccessToken(),
    },
    payload: JSON.stringify(requestData),
  };
  //  And makes the call.
  var response = UrlFetchApp.fetch(apiEndPoint, options);
  var data = JSON.parse(response);
  return data;
}

function uploadFileToCloudStorage(file) {
  const API = `https://www.googleapis.com/upload/storage/v1/b`;
  const location = encodeURIComponent(`${FILE_PATH}/${file.getName()}`);
  const url = `${API}/${STORAGE_BUCKET}/o?uploadType=media&name=${location}`;

  const service = getService();
  const accessToken = service.getAccessToken();

  var docBytes = file.getBlob().getBytes();
  var mimeType = file.getMimeType();

  const response = UrlFetchApp.fetch(url, {
    method: "POST",
    contentLength: docBytes.length,
    contentType: mimeType,
    payload: docBytes,
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  const result = JSON.parse(response.getContentText());
  return result;
}

/**
 * Reset the authorization state, so that it can be re-tested.
 */
function reset() {
  var service = getService();
  service.reset();
}

/**
 * Configures the service.
 */
function getService() {
  return (
    OAuth2.createService("GCP")
      // Set the endpoint URL.
      .setTokenUrl("https://accounts.google.com/o/oauth2/token")

      // Set the private key and issuer.
      .setPrivateKey(SERVICE_ACCOUNT.private_key)
      .setIssuer(SERVICE_ACCOUNT.client_email)

      // Set the property store where authorized tokens should be persisted.
      .setPropertyStore(PropertiesService.getScriptProperties())

      // Set the scope. This must match one of the scopes configured during the
      // setup of domain-wide delegation.
      .setScope(["https://www.googleapis.com/auth/cloud-platform"])
  );
}

/**
 * Main function for Online Processing
 */
function runOnlineProcessing() {
  reset();
  var file = DriveApp.getFileById(TEST_FILE_ID);
  console.log(file.getName());
  var response = processDocument(file);
  console.log(JSON.stringify(response, null, 4));
}

/**
 * Main function for Import to Cloud Storage
 */
function runCloudStorage() {
  reset();
  var file = DriveApp.getFileById(TEST_FILE_ID);
  console.log(file.getName());
  var response = uploadFileToCloudStorage(file);
  console.log(JSON.stringify(response, null, 4));
}
