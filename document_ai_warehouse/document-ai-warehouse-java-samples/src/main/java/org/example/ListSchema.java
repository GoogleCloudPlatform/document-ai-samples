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

import com.google.cloud.contentwarehouse.v1.DocumentSchema;
import com.google.cloud.contentwarehouse.v1.DocumentSchemaServiceClient;
import com.google.cloud.contentwarehouse.v1.LocationName;

/**
 * A sample application that lists schemas.
 */
public class ListSchema {
  private String projectNumber;
  private String location;

  public void setProjectNumber(String projectNumberValue) {
    this.projectNumber = projectNumberValue;
  }

  public void setLocation(String locationValue) {
    this.location = locationValue;
  }

  /** List the schema that are defined in Document AI Warehouse. */
  public void listSchema() {
    try {
      try (DocumentSchemaServiceClient documentSchemaServiceClient =
          DocumentSchemaServiceClient.create()) {
        DocumentSchemaServiceClient.ListDocumentSchemasPagedResponse response =
            documentSchemaServiceClient.listDocumentSchemas(
                LocationName.of(projectNumber, location));
        System.out.println("display name    name");
        System.out.println(
            "--------------- ------------------------------------------------------------------------");
        for (DocumentSchema currentSchema : response.iterateAll()) {
          System.out.printf(
              "%-15.15s %s\n", currentSchema.getDisplayName(), currentSchema.getName());
        }
      }
    } catch (Exception e) {
      e.printStackTrace();
    }
  } // listSchema

  /**
   * Main entry into the application.
   *
   * @param args Arguments to the application.
   */
  public static void main(String[] args) {
    String projectNumber = System.getenv("PROJECT_NUMBER");
    if (projectNumber == null) {
      System.err.println("No PROJECT_NUMBER environment variable set");
      return;
    }
    String location = System.getenv("LOCATION");
    if (location == null) {
      location = "us"; // Default to us location
    }

    ListSchema app = new ListSchema();
    app.setProjectNumber(projectNumber);
    app.setLocation(location);
    app.listSchema();
    System.out.println("ListSchema completed");
  } // main
} // ListSchema
