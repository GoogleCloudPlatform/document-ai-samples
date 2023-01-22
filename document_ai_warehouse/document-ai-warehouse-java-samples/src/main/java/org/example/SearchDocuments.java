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

import com.google.cloud.contentwarehouse.v1.DocumentQuery;
import com.google.cloud.contentwarehouse.v1.DocumentServiceClient;
import com.google.cloud.contentwarehouse.v1.LocationName;
import com.google.cloud.contentwarehouse.v1.RequestMetadata;
import com.google.cloud.contentwarehouse.v1.SearchDocumentsRequest;
import com.google.cloud.contentwarehouse.v1.SearchDocumentsResponse;
import com.google.cloud.contentwarehouse.v1.UserInfo;

public class SearchDocuments {
  private String PROJECT_NUMBER;
  private String LOCATION;
  private String USERID;

  public SearchDocuments setProjectNumber(String projectNumber) {
    this.PROJECT_NUMBER = projectNumber;
    return this;
  }

  public SearchDocuments setLocation(String location) {
    this.LOCATION = location;
    return this;
  }

  public void setUserId(String userId) {
    this.USERID = userId;
  }

  /**
   */
  public void searchDocuments(String query) {
    try {
      try (DocumentServiceClient documentServiceClient =
             DocumentServiceClient.create()) {
        DocumentQuery documentQuery = DocumentQuery.newBuilder()
          .setQuery(query)
          .build();

        RequestMetadata requestMetadata = RequestMetadata.newBuilder()
          .setUserInfo(UserInfo.newBuilder()
            .setId(USERID)
            .build())
          .build();

        SearchDocumentsRequest searchDocumentsRequest =
          SearchDocumentsRequest.newBuilder()
          .setDocumentQuery(documentQuery)
          .setParent(LocationName.of(PROJECT_NUMBER, LOCATION).toString())
          .setRequestMetadata(requestMetadata)
          .build();

        DocumentServiceClient.SearchDocumentsPagedResponse response
          = documentServiceClient.searchDocuments(searchDocumentsRequest);
        System.out.println("display name    name");
        System.out.println("--------------- ----------------------------" +
          "--------------------------------------------");
        for (SearchDocumentsResponse.MatchingDocument matchingDocument:
          response.iterateAll()) {
          System.out.printf("%-15.15s %s\n",
            matchingDocument.getDocument().getDisplayName() ,
              matchingDocument.getDocument().getName());
        }
      }
    } catch (Exception e) {
      e.printStackTrace();
    }
  } // searchDocuments

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
    if (args.length < 1) {
      System.err.println("Usage: SearchDocument [QUERY]");
      return;
    }

    String query = args[0]; // Query string to look for.
    try {
      SearchDocuments app = new SearchDocuments();
      app.setProjectNumber(projectNumber)
        .setLocation(location)
        .setUserId(userid);
      app.searchDocuments(query);
    } catch(Exception e) {
      e.printStackTrace();
      return;
    }

    System.out.println("SearchDocuments completed");
  } // main
} // SearchDocuments
