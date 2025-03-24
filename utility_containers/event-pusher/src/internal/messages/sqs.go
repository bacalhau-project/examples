package messages

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/url"
	"sort"
	"strings"
	"time"

	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/http"
)

// SQSConfig contains configuration for SQS messaging
type SQSConfig struct {
	Region    string
	AccessKey string
	SecretKey string
	QueueURL  string
	Simulate  bool
}

// SQSSender handles sending messages to an SQS queue
type SQSSender struct {
	Config     SQSConfig
	messageLog []Message // For testing
}

// NewSQSSender creates a new SQS message sender
func NewSQSSender(config SQSConfig) *SQSSender {
	return &SQSSender{
		Config:     config,
		messageLog: make([]Message, 0),
	}
}

// SendMessage sends a message to an SQS queue
func (s *SQSSender) SendMessage(msg Message) error {
	// Add message to log
	s.messageLog = append(s.messageLog, msg)

	// Skip all HTTP work if in simulation mode
	if s.Config.Simulate {
		msgJSON, _ := json.Marshal(msg)
		fmt.Printf("Simulation: Would send message to %s: %s\n", s.Config.QueueURL, string(msgJSON))
		return nil
	}

	// Create HTTP client
	httpClient := http.New()

	// Marshal message to JSON
	msgJSON, err := json.Marshal(msg)
	if err != nil {
		return fmt.Errorf("error marshaling message: %v", err)
	}

	// Parse queue URL
	parsedURL, err := url.Parse(s.Config.QueueURL)
	if err != nil {
		return fmt.Errorf("invalid queue URL: %v", err)
	}

	// Create a unique deduplication ID
	deduplicationID := sha256Hash([]byte(fmt.Sprintf("%s-%s", string(msgJSON), msg.Timestamp)))

	// Create timestamp for AWS request
	t := time.Now().UTC()
	amzDate := t.Format("20060102T150405Z")
	datestamp := t.Format("20060102")

	// Create AWS SQS parameters
	params := map[string]string{
		"Action":                 "SendMessage",
		"MessageBody":            string(msgJSON),
		"Version":                "2012-11-05",
		"MessageGroupId":         msg.ContainerID,
		"MessageDeduplicationId": deduplicationID,
	}

	// Sort parameters for canonical request
	var paramKeys []string
	for k := range params {
		paramKeys = append(paramKeys, k)
	}
	sort.Strings(paramKeys)

	// Build form data string for payload hashing
	var formValues []string
	for _, k := range paramKeys {
		formValues = append(formValues, fmt.Sprintf("%s=%s", url.QueryEscape(k), url.QueryEscape(params[k])))
	}
	formData := strings.Join(formValues, "&")

	// Calculate payload hash
	payloadHash := sha256Hash([]byte(formData))

	// Format for AWS SQS
	host := fmt.Sprintf("sqs.%s.amazonaws.com", s.Config.Region)

	// Create canonical request
	canonicalRequest := fmt.Sprintf("POST\n%s\n\n%s:%s\nx-amz-date:%s\n\n%s\n%s",
		parsedURL.Path,
		"host", host,
		amzDate,
		"host;x-amz-date",
		payloadHash,
	)

	// Create string to sign
	algorithm := "AWS4-HMAC-SHA256"
	credentialScope := fmt.Sprintf("%s/%s/sqs/aws4_request", datestamp, s.Config.Region)
	stringToSign := fmt.Sprintf("%s\n%s\n%s\n%s",
		algorithm,
		amzDate,
		credentialScope,
		sha256Hash([]byte(canonicalRequest)),
	)

	// Calculate signature
	signingKey := getSignatureKey(s.Config.SecretKey, datestamp, s.Config.Region, "sqs")
	signature := hmacSHA256(signingKey, []byte(stringToSign))
	signatureHex := hex.EncodeToString(signature)

	// Create authorization header
	authorizationHeader := fmt.Sprintf("%s Credential=%s/%s, SignedHeaders=host;x-amz-date, Signature=%s",
		algorithm,
		s.Config.AccessKey,
		credentialScope,
		signatureHex,
	)

	// Create headers map from our interface
	headers := map[string]string{
		"Content-Type":  "application/x-www-form-urlencoded",
		"Host":          host,
		"X-Amz-Date":    amzDate,
		"Authorization": authorizationHeader,
	}

	// Get method constant
	methodCode, err := httpClient.GetMethodConstant("POST")
	if err != nil {
		return fmt.Errorf("error getting method constant: %v", err)
	}

	// Send HTTP request
	resp, err := httpClient.Request(methodCode, s.Config.QueueURL, headers, formData)
	if err != nil {
		return fmt.Errorf("error sending request: %v", err)
	}

	// Check response
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("SQS error (status %d): %s", resp.StatusCode, resp.Body)
	}

	return nil
}

// UpdateConfig updates the SQS configuration
func (s *SQSSender) UpdateConfig(config SQSConfig) {
	s.Config = config
}

// GetLastMessages returns the last N messages sent (for testing)
func (s *SQSSender) GetLastMessages(count int) []Message {
	if count <= 0 || count > len(s.messageLog) {
		count = len(s.messageLog)
	}
	result := make([]Message, count)
	start := len(s.messageLog) - count
	for i := 0; i < count; i++ {
		result[i] = s.messageLog[start+i]
	}
	return result
}

// getSignatureKey generates AWS signature key
func getSignatureKey(key, datestamp, region, service string) []byte {
	kDate := hmacSHA256([]byte("AWS4"+key), []byte(datestamp))
	kRegion := hmacSHA256(kDate, []byte(region))
	kService := hmacSHA256(kRegion, []byte(service))
	kSigning := hmacSHA256(kService, []byte("aws4_request"))
	return kSigning
}

// hmacSHA256 performs HMAC SHA256
func hmacSHA256(key, data []byte) []byte {
	h := hmac.New(sha256.New, key)
	h.Write(data)
	return h.Sum(nil)
}

// sha256Hash calculates SHA256 hash of data
func sha256Hash(data []byte) string {
	hasher := sha256.New()
	hasher.Write(data)
	return hex.EncodeToString(hasher.Sum(nil))
}
