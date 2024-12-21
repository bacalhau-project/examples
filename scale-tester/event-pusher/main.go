package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"math/rand"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/joho/godotenv"
)

// Message represents the structure we'll send to SQS
type Message struct {
	VMName    string `json:"vm_name"`
	IconName  string `json:"icon_name"`
	Timestamp string `json:"timestamp"`
}

func getSignatureKey(key, datestamp, region, service string) []byte {
	kDate := hmac.New(sha256.New, []byte("AWS4"+key))
	kDate.Write([]byte(datestamp))
	kRegion := hmac.New(sha256.New, kDate.Sum(nil))
	kRegion.Write([]byte(region))
	kService := hmac.New(sha256.New, kRegion.Sum(nil))
	kService.Write([]byte(service))
	kSigning := hmac.New(sha256.New, kService.Sum(nil))
	kSigning.Write([]byte("aws4_request"))
	return kSigning.Sum(nil)
}

func createSignature(method, host, uri, region, accessKey, secretKey string, params map[string]string) map[string]string {
	t := time.Now().UTC()
	amzDate := t.Format("20060102T150405Z")
	datestamp := t.Format("20060102")

	// Create form data
	formData := url.Values{}
	for k, v := range params {
		formData.Set(k, v)
	}

	// Calculate payload hash from form-encoded data
	payload := formData.Encode()
	payloadHash := fmt.Sprintf("%x", sha256.Sum256([]byte(payload)))

	// Create canonical request with exact formatting
	canonicalRequest := fmt.Sprintf("%s\n%s\n\n%s:%s\nx-amz-date:%s\n\n%s\n%s",
		method,
		uri,
		"host", host,
		amzDate,
		"host;x-amz-date",
		payloadHash,
	)

	// Create string to sign
	algorithm := "AWS4-HMAC-SHA256"
	credentialScope := fmt.Sprintf("%s/%s/sqs/aws4_request", datestamp, region)
	stringToSign := fmt.Sprintf("%s\n%s\n%s\n%x",
		algorithm,
		amzDate,
		credentialScope,
		sha256.Sum256([]byte(canonicalRequest)),
	)

	// Calculate signature
	signingKey := getSignatureKey(secretKey, datestamp, region, "sqs")
	signature := hmac.New(sha256.New, signingKey)
	signature.Write([]byte(stringToSign))
	sig := fmt.Sprintf("%x", signature.Sum(nil))

	// Create authorization header
	authorizationHeader := fmt.Sprintf("%s Credential=%s/%s, SignedHeaders=host;x-amz-date, Signature=%s",
		algorithm,
		accessKey,
		credentialScope,
		sig,
	)

	return map[string]string{
		"Authorization": authorizationHeader,
		"X-Amz-Date":    amzDate,
	}
}

func sendSQSMessage(msg Message, region, accessKey, secretKey, queueURL string) error {
	msgJSON, err := json.Marshal(msg)
	if err != nil {
		return fmt.Errorf("error marshaling message: %w", err)
	}

	parsedURL, err := url.Parse(queueURL)
	if err != nil {
		return fmt.Errorf("invalid queue URL: %w", err)
	}

	params := map[string]string{
		"Action":      "SendMessage",
		"MessageBody": string(msgJSON),
		"Version":     "2012-11-05",
	}

	// Use the full SQS hostname
	host := fmt.Sprintf("sqs.%s.amazonaws.com", region)
	headers := createSignature("POST", host, parsedURL.Path, region, accessKey, secretKey, params)

	// Create form data
	formData := url.Values{}
	for k, v := range params {
		formData.Set(k, v)
	}

	// Create request
	req, err := http.NewRequest("POST", queueURL, strings.NewReader(formData.Encode()))
	if err != nil {
		return fmt.Errorf("error creating request: %w", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	req.Header.Set("Host", host) // Explicitly set the Host header

	// Send request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("error sending request: %w", err)
	}
	defer resp.Body.Close()

	// Check response
	if resp.StatusCode != http.StatusOK {
		body, _ := ioutil.ReadAll(resp.Body)
		return fmt.Errorf("SQS error (status %d): %s", resp.StatusCode, string(body))
	}

	return nil
}

func main() {
	// Initialize local random source
	r := rand.New(rand.NewSource(time.Now().UnixNano()))

	// Load .env file
	if err := godotenv.Load(); err != nil {
		fmt.Printf("Error loading .env file: %v\n", err)
		os.Exit(1)
	}

	// Get configuration from environment variables
	awsRegion := os.Getenv("AWS_REGION")
	awsAccessKey := os.Getenv("AWS_ACCESS_KEY_ID")
	awsSecretKey := os.Getenv("AWS_SECRET_ACCESS_KEY")
	queueURL := os.Getenv("AWS_SQS_QUEUE_URL")

	// Validate required environment variables
	if awsRegion == "" || awsAccessKey == "" || awsSecretKey == "" || queueURL == "" {
		fmt.Println("Missing required environment variables. Please ensure all AWS credentials are set in .env file")
		os.Exit(1)
	}

	fmt.Println("Starting message publisher...")

	// Continuously send messages
	for {
		msg := Message{
			VMName:    fmt.Sprintf("vm-%d", r.Intn(100)),
			IconName:  GetRandomIcon(r),
			Timestamp: time.Now().Format(time.RFC3339),
		}

		if err := sendSQSMessage(msg, awsRegion, awsAccessKey, awsSecretKey, queueURL); err != nil {
			fmt.Printf("Error: %v\n", err)
		} else {
			msgJSON, _ := json.Marshal(msg)
			fmt.Printf("Sent message: %s\n", string(msgJSON))
		}

		sleepTime := 100 + r.Intn(2900) // 100ms to 3000ms
		time.Sleep(time.Duration(sleepTime) * time.Millisecond)
	}
}
