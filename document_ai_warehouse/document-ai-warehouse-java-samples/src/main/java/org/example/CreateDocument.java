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

import com.google.cloud.contentwarehouse.v1.CreateDocumentRequest;
import com.google.cloud.contentwarehouse.v1.CreateDocumentResponse;
import com.google.cloud.contentwarehouse.v1.Document;
import com.google.cloud.contentwarehouse.v1.DocumentServiceClient;
import com.google.cloud.contentwarehouse.v1.LocationName;
import com.google.cloud.contentwarehouse.v1.Property;
import com.google.cloud.contentwarehouse.v1.RawDocumentFileType;
import com.google.cloud.contentwarehouse.v1.RequestMetadata;
import com.google.cloud.contentwarehouse.v1.TextArray;
import com.google.cloud.contentwarehouse.v1.UserInfo;
import com.google.protobuf.ByteString;

import java.io.FileInputStream;

/**
 * Sample that illustrates creating a document in Document AI Warehouse.
 */
public class CreateDocument {
  private String PROJECT_NUMBER;
  private String LOCATION;
  private String USERID;

  public CreateDocument setProjectNumber(String projectNumber) {
    this.PROJECT_NUMBER = projectNumber;
    return this;
  }

  public CreateDocument setLocation(String location) {
    this.LOCATION = location;
    return this;
  }

  public CreateDocument setUserId(String userId) {
    this.USERID = userId;
    return this;
  }


  /**
   * Create a document.
   * This method performs the work to make a request to Document AI Warehouse to create (ingest) a new
   * document.  It is expected that the schema will have at least two properties called `payee` and `payer`.
   * @param fileData The document data to be loaded into Document AI Warehouse.
   * @param schemaName The Document AI Warehouse identity of the schema.
   */
  public void createDocument(String schemaName, ByteString fileData) {
    try {
      try (DocumentServiceClient documentServiceClient = DocumentServiceClient.create()) {
        Document document = Document.newBuilder()
          .setDisplayName("Invoice 1")
          .setTitle("My Invoice 1")
          .setDocumentSchemaName(schemaName)
          .setInlineRawDocument(fileData)
          .setRawDocumentFileType(RawDocumentFileType.RAW_DOCUMENT_FILE_TYPE_PDF)
          .setTextExtractionDisabled(true)
          .addProperties(Property.newBuilder()
            .setName("payee")
            .setTextValues(TextArray.newBuilder().addValues("Developer Company").build())
            .build())
          .addProperties(Property.newBuilder()
            .setName("payer")
            .setTextValues(TextArray.newBuilder().addValues("Buyer Company").build())
            .build())
          .build();

        RequestMetadata requestMetadata = RequestMetadata.newBuilder()
          .setUserInfo(UserInfo.newBuilder()
            .setId(USERID)
            .build())
          .build();

        CreateDocumentRequest createDocumentRequest = CreateDocumentRequest.newBuilder()
          .setDocument(document)
          .setParent(LocationName.of(PROJECT_NUMBER, LOCATION).toString())
          .setRequestMetadata(requestMetadata)
          .build();

        CreateDocumentResponse createDocumentResponse = documentServiceClient.createDocument(createDocumentRequest);

        System.out.println("name");
        System.out.println("-------------------------------------------------------------------------");
        System.out.println(createDocumentResponse.getDocument().getName());
      }
    } catch (Exception e) {
      e.printStackTrace();
    }
  } // createDocument

  public static void main(String[] args) {
    String projectNumber = System.getenv("PROJECT_NUMBER");
    if (projectNumber == null) {
      System.err.println("No PROJECT_NUMBER environment variable set");
      return;
    }
    String userid = System.getenv("USERID");
    if (userid == null) {
      System.err.println("No USERID environment variable set");
      return;
    }
    String location = System.getenv("LOCATION");
    if (location == null) {
      location = "us"; // Default to us location
    }

    if (args.length < 2) {
      System.err.println("Usage: CreateDocument [SCHEMA_NAME] [FILENAME]");
      return;
    }

    String schemaName = args[0]; // Name of schema to associate with document.
    String fileName = args[1];   // Local file name of document.

    try {
      // Read the document data into memory for passing to Document AI Warehouse.
      ByteString fileData = ByteString.readFrom(new FileInputStream(fileName));
      CreateDocument app = new CreateDocument();
      app.setProjectNumber(projectNumber).setUserId(userid).setLocation(location);
      app.createDocument(schemaName, fileData);
    } catch(Exception e) {
      e.printStackTrace();
      return;
    }

    System.out.println("CreateDocument completed");
  } // main
} // CreateDocument
