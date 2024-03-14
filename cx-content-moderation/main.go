// Copyright 2023 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"context"
	"fmt"
	"log"
	"os"

	documentai "cloud.google.com/go/documentai/apiv1beta3"
	"cloud.google.com/go/documentai/apiv1beta3/documentaipb"

	"google.golang.org/api/option"

	"github.com/googlecloudplatform/ezcx"
)

var (
	contentModerationProcessorName = envCheck("CONTENT_MODERATION_NAME", "")
	port                           = envCheck("PORT", "8080")
)

const location = "us"

func main() {
	log.Printf("cx-content-moderation")

	if contentModerationProcessorName == "" {
		log.Fatal("need to provide CONTENT_MODERATION_NAME reference to name of Content Moderation API Document Processor name")
	}

	ctx := context.Background()
	server := ezcx.NewServer(ctx, ":"+port, log.Default())
	server.HandleCx("/analyze", analyzeCommentHandler)
	server.ListenAndServe(ctx)
}

// analyzeCommentHandler is the Dialogflow CX interface for the Content Moderation API
func analyzeCommentHandler(res *ezcx.WebhookResponse, req *ezcx.WebhookRequest) error {
	params := req.GetSessionParameters()
	text := req.GetText()
	if text == "" {
		return fmt.Errorf("no text provided")
	}

	// perform content moderation on text
	ctx := context.Background()
	resp, err := rateToxicityContentModeration(ctx, text)
	if err != nil {
		log.Printf("unable to process document: %v", err)
		return err
	}

	// map the content moderation API results to a CX Session parameter
	attributes := make(map[string]interface{})
	for _, attribute := range resp.Document.Entities {
		attributes[attribute.GetType()] = attribute.GetConfidence()
	}
	if params == nil {
		params = make(map[string]interface{})
	}
	params["content-moderation"] = attributes

	// add this parameter to the response parameters
	err = res.AddSessionParameters(params)
	if err != nil {
		log.Printf("unable to add content-moderation session params: %v", err)
	}
	log.Printf("%+v", res)

	return nil
}

// rateToxicityContentModeration invokes the Content Moderation API DocumentAI Processor with a given text content string
func rateToxicityContentModeration(ctx context.Context, content string) (*documentaipb.ProcessResponse, error) {
	resp := &documentaipb.ProcessResponse{}
	c, err := documentai.NewDocumentProcessorClient(ctx, option.WithEndpoint(apiEndpoint()))
	if err != nil {
		log.Printf("error creating Document Processor client: %v", err)
		return resp, err
	}
	defer c.Close()

	req := &documentaipb.ProcessRequest{
		Source: &documentaipb.ProcessRequest_InlineDocument{
			InlineDocument: &documentaipb.Document{
				Text:     content,
				MimeType: "text/plain",
			},
		},
		Name: contentModerationProcessorName,
	}

	resp, err = c.ProcessDocument(ctx, req)
	if err != nil {
		return resp, err
	}

	return resp, nil
}

// apiEndpoint returns the URL of the Document AI API endpoint based upon the
// user's choice for the Document AI API location
func apiEndpoint() string {
	return fmt.Sprintf("%s-documentai.googleapis.com:443", location)
}

// envCheck checks for an environment variable, otherwise returns default
func envCheck(environmentVariable, defaultVar string) string {
	envar, ok := os.LookupEnv(environmentVariable)
	if envar == "" || !ok {
		return defaultVar
	}
	return envar
}
