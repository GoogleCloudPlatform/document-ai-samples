/*
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package org.example;

import com.google.cloud.contentwarehouse.v1.DeleteDocumentRequest;
import com.google.cloud.contentwarehouse.v1.DocumentServiceClient;
import com.google.cloud.contentwarehouse.v1.RequestMetadata;
import com.google.cloud.contentwarehouse.v1.UserInfo;

/**
 * Sample application that deletes a document from Document AI Warehouse.
 */
public class DeleteDocument {
  private String userId;

  public void setUserId(String userIdValue) {
    this.userId = userIdValue;
  }

  /**
   * Delete a document.
   *
   * @param documentName The name of the document to delete.
   */
  public void deleteDocument(String documentName) {
    try {
      try (DocumentServiceClient documentServiceClient = DocumentServiceClient.create()) {
        RequestMetadata requestMetadata =
            RequestMetadata.newBuilder()
                .setUserInfo(UserInfo.newBuilder().setId(userId).build())
                .build();
        DeleteDocumentRequest deleteDocumentRequest =
            DeleteDocumentRequest.newBuilder()
                .setName(documentName)
                .setRequestMetadata(requestMetadata)
                .build();
        documentServiceClient.deleteDocument(deleteDocumentRequest);
      }
    } catch (Exception e) {
      e.printStackTrace();
    }
  } // deleteDocument

  /**
   * Main entry point into the application.
   *
   * @param args Parameters to the application.
   */
  public static void main(String[] args) {
    String userid = System.getenv("USERID");
    if (userid == null) {
      System.err.println("No USERID environment variable set");
      return;
    }

    if (args.length < 1) {
      System.err.println("Usage: DeleteDocument [DOCUMENT_NAME]");
      return;
    }

    String documentName = args[0];

    DeleteDocument app = new DeleteDocument();
    app.setUserId(userid);
    app.deleteDocument(documentName);
    System.out.println("DeleteDocument completed");
  } // main
} // DeleteDocument
