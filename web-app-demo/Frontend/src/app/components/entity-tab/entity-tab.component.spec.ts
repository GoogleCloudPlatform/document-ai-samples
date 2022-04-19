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

import { ComponentFixture, TestBed } from "@angular/core/testing";

import { EntityTabComponent } from "./entity-tab.component";
import { BrowserModule } from "@angular/platform-browser";
import { BrowserAnimationsModule } from "@angular/platform-browser/animations";
import { FormsModule, ReactiveFormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";
import { MatPaginatorModule } from "@angular/material/paginator";
import { MatCardModule } from "@angular/material/card";
import { CUSTOM_ELEMENTS_SCHEMA } from "@angular/core";
import { CanvasComponent } from "src/app/components/canvas/canvas.component";
import { DataSharingServiceService } from "src/app/data-sharing-service.service";

import ocrResponse from "../../../assets/ocrTestProto.json";
import formResponse from "../../../assets/formTestProto.json";
import invoiceResponse from "../../../assets/invoiceTestProto.json";

const testText = "Hello this is a test";

const data = {
  bounding: [
    { x: 0, y: 0 },
    { x: 0, y: 0 },
    { x: 0, y: 0 },
    { x: 0, y: 0 },
  ],
};

describe("EntityTabComponent", () => {
  let component: EntityTabComponent;
  let fixture: ComponentFixture<EntityTabComponent>;
  const dataSharing = new DataSharingServiceService();

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [EntityTabComponent, CanvasComponent],
      imports: [
        BrowserModule,
        BrowserAnimationsModule,
        MatButtonModule,
        MatIconModule,
        MatProgressBarModule,
        MatSelectModule,
        FormsModule,
        ReactiveFormsModule,
        MatTableModule,
        MatPaginatorModule,
        MatCardModule,
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    }).compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(EntityTabComponent);
    component = fixture.componentInstance;
    component.data = dataSharing;
    fixture.detectChanges();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });

  it("should populate data source for OCR", () => {
    dataSharing.changeDocumentProto(ocrResponse);

    component.ngDoCheck();
    expect(component.dataSource).not.toBeNull();
  });

  it("should populate data source for Invoice", () => {
    dataSharing.changeDocumentProto(invoiceResponse);

    component.ngDoCheck();
    expect(component.dataSource).not.toBeNull();
  });

  it("should populate data source for Form", () => {
    dataSharing.changeDocumentProto(formResponse);

    component.ngDoCheck();
    expect(component.dataSource).not.toBeNull();
  });

  it("should get text", () => {
    const textAnchor = { textSegments: [{ startIndex: 0, endIndex: 20 }] };
    expect(component.getText(textAnchor, testText)).toEqual(testText);
  });

  it("should highlight Bounding Boxes for OCR", () => {
    spyOn(component, "highlightBoundingBoxes").and.callThrough();

    const fixture2 = TestBed.createComponent(CanvasComponent);
    const component2 = fixture2.componentInstance;
    component2.ngOnInit();

    dataSharing.changeProcessor("OCR");

    component.highlightBoundingBoxes(data);

    expect(component.highlightBoundingBoxes).toHaveBeenCalled();
  });

  it("should highlight Bounding Boxes for Invoice", () => {
    spyOn(component, "highlightBoundingBoxes").and.callThrough();

    const fixture2 = TestBed.createComponent(CanvasComponent);
    const component2 = fixture2.componentInstance;
    component2.ngOnInit();

    dataSharing.changeProcessor("Invoice");

    component.highlightBoundingBoxes(data);

    expect(component.highlightBoundingBoxes).toHaveBeenCalled();
  });

  it("should highlight Bounding Boxes for Form", () => {
    spyOn(component, "highlightBoundingBoxes").and.callThrough();

    const fixture2 = TestBed.createComponent(CanvasComponent);
    const component2 = fixture2.componentInstance;
    component2.ngOnInit();

    dataSharing.changeProcessor("Form");

    const data = {
      bounding: [
        {
          value: [
            { x: 0, y: 0 },
            { x: 0, y: 0 },
            { x: 0, y: 0 },
            { x: 0, y: 0 },
          ],
          name: [
            { x: 0, y: 0 },
            { x: 0, y: 0 },
            { x: 0, y: 0 },
            { x: 0, y: 0 },
          ],
        },
      ],
    };

    component.highlightBoundingBoxes(data);

    expect(component.highlightBoundingBoxes).toHaveBeenCalled();
  });

  it("should clear bounding box canvas", () => {
    spyOn(component, "clearBoundingBoxes").and.callThrough();

    const fixture2 = TestBed.createComponent(CanvasComponent);
    const component2 = fixture2.componentInstance;
    component2.ngOnInit();

    component.clearBoundingBoxes();

    expect(component.clearBoundingBoxes).toHaveBeenCalled();
  });
});
