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

import com.google.cloud.contentwarehouse.v1.DateTimeTypeOptions;
import com.google.cloud.contentwarehouse.v1.DocumentSchema;
import com.google.cloud.contentwarehouse.v1.DocumentSchemaServiceClient;
import com.google.cloud.contentwarehouse.v1.FloatTypeOptions;
import com.google.cloud.contentwarehouse.v1.LocationName;
import com.google.cloud.contentwarehouse.v1.PropertyDefinition;
import com.google.cloud.contentwarehouse.v1.TextTypeOptions;

/** Sample application that creates a Document AI Warehouse Schema. */
public class CreateSchema {
  private String projectNumber;
  private String location;

  public void setProjectNumber(String projectNumberValue) {
    this.projectNumber = projectNumberValue;
  }

  public void setLocation(String locationValue) {
    this.location = locationValue;
  }

  /** Create a schema. */
  public void createSchema() {
    try {
      try (DocumentSchemaServiceClient documentSchemaServiceClient =
          DocumentSchemaServiceClient.create()) {
        DocumentSchema documentSchema =
            DocumentSchema.newBuilder()
                .setDisplayName("Invoice")
                .setDescription("Invoice Schema")
                .setDocumentIsFolder(false)
                .addPropertyDefinitions(
                    PropertyDefinition.newBuilder()
                        .setName("payee")
                        .setDisplayName("Payee")
                        .setIsFilterable(true)
                        .setIsSearchable(true)
                        .setIsMetadata(true)
                        .setIsRequired(true)
                        .setTextTypeOptions(TextTypeOptions.newBuilder().build())
                        .build())
                .addPropertyDefinitions(
                    PropertyDefinition.newBuilder()
                        .setName("payer")
                        .setDisplayName("Payer")
                        .setIsFilterable(true)
                        .setIsSearchable(false)
                        .setIsMetadata(true)
                        .setIsRequired(true)
                        .setTextTypeOptions(TextTypeOptions.newBuilder().build())
                        .build())
                .addPropertyDefinitions(
                    PropertyDefinition.newBuilder()
                        .setName("amount")
                        .setDisplayName("Amount")
                        .setIsFilterable(true)
                        .setIsSearchable(false)
                        .setIsMetadata(true)
                        .setIsRequired(false)
                        .setFloatTypeOptions(FloatTypeOptions.newBuilder().build())
                        .build())
                .addPropertyDefinitions(
                    PropertyDefinition.newBuilder()
                        .setName("id")
                        .setDisplayName("Invoice ID")
                        .setIsFilterable(true)
                        .setIsSearchable(false)
                        .setIsMetadata(true)
                        .setIsRequired(false)
                        .setTextTypeOptions(TextTypeOptions.newBuilder().build())
                        .build())
                .addPropertyDefinitions(
                    PropertyDefinition.newBuilder()
                        .setName("date")
                        .setDisplayName("Date")
                        .setIsFilterable(true)
                        .setIsSearchable(false)
                        .setIsMetadata(true)
                        .setIsRequired(false)
                        .setDateTimeTypeOptions(DateTimeTypeOptions.newBuilder().build())
                        .build())
                .addPropertyDefinitions(
                    PropertyDefinition.newBuilder()
                        .setName("notes")
                        .setDisplayName("Notes")
                        .setIsFilterable(true)
                        .setIsSearchable(false)
                        .setIsMetadata(true)
                        .setIsRequired(false)
                        .setTextTypeOptions(TextTypeOptions.newBuilder().build())
                        .build())
                .build();
        DocumentSchema newDocumentSchema =
            documentSchemaServiceClient.createDocumentSchema(
                LocationName.of(projectNumber, location), documentSchema);
        System.out.println("name");
        System.out.println(
            "-------------------------------------------------------------------------");
        System.out.println(newDocumentSchema.getName());
      }
    } catch (Exception e) {
      e.printStackTrace();
    }
  } // createSchema

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

    CreateSchema app = new CreateSchema();
    app.setProjectNumber(projectNumber);
    app.setLocation(location);
    app.createSchema();
    System.out.println("CreateSchema completed");
  } // main
} // CreateSchema
