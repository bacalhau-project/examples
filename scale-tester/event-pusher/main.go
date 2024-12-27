package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"sync/atomic"
	"time"

	"github.com/joho/godotenv"
)

// Add counters for monitoring
var (
	messagesSent  uint64
	messagesError uint64
)

// Message represents the structure we'll send to SQS
type Message struct {
	VMName      string `json:"vm_name"`
	IconName    string `json:"icon_name"`
	Timestamp   string `json:"timestamp"`
	Color       string `json:"color"`
	ContainerID string `json:"container_id"`
}

// Simple regex to validate a 6-digit hex code with a leading '#'
var hexColorRegex = regexp.MustCompile(`^#[0-9A-Fa-f]{6}$`)

const containerIDLength = 8

func GetRandomIcon(r *rand.Rand) string {
	return GetRandomEmoji(r)
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

	// Create a unique deduplication ID based on the message content and timestamp
	deduplicationID := fmt.Sprintf("%x", sha256.Sum256([]byte(fmt.Sprintf("%s-%s", msgJSON, msg.Timestamp))))

	params := map[string]string{
		"Action":                 "SendMessage",
		"MessageBody":            string(msgJSON),
		"Version":                "2012-11-05",
		"MessageGroupId":         msg.VMName, // Use VM name as the group ID to maintain order per VM
		"MessageDeduplicationId": deduplicationID,
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
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("SQS error (status %d): %s", resp.StatusCode, string(body))
	}

	return nil
}

func getContainerID() string {
	// Try to get container ID from /proc/self/mountinfo (works in most container runtimes)
	if mountData, err := os.ReadFile("/proc/self/mountinfo"); err == nil {
		lines := strings.Split(string(mountData), "\n")
		for _, line := range lines {
			if strings.Contains(line, "/containers/") {
				parts := strings.Split(line, "/containers/")
				if len(parts) > 1 {
					containerID := strings.Split(parts[1], "/")[0]
					if len(containerID) >= containerIDLength {
						return containerID[:containerIDLength]
					}
				}
			}
		}
	}

	// Try to get container ID from cgroup file (Docker)
	if cgroupData, err := os.ReadFile("/proc/self/cgroup"); err == nil {
		lines := strings.Split(string(cgroupData), "\n")
		for _, line := range lines {
			if strings.Contains(line, "docker") {
				parts := strings.Split(line, "/")
				containerID := parts[len(parts)-1]
				if len(containerID) >= containerIDLength {
					return containerID[:containerIDLength]
				}
			}
			// Check for containerd format
			if strings.Contains(line, "containers") {
				parts := strings.Split(line, "/")
				for i, part := range parts {
					if strings.HasPrefix(part, "containers") && i+1 < len(parts) {
						containerID := parts[i+1]
						if len(containerID) >= containerIDLength {
							return containerID[:containerIDLength]
						}
					}
				}
			}
		}
	}

	// Try to get container ID from hostname (Kubernetes pods)
	if hostname, err := os.Hostname(); err == nil {
		// Kubernetes pod names often contain the container/pod ID
		if strings.Contains(hostname, "-") {
			parts := strings.Split(hostname, "-")
			lastPart := parts[len(parts)-1]
			if len(lastPart) >= containerIDLength {
				return lastPart[:containerIDLength]
			}
		}
		return hostname
	}

	return "unknown"
}

func main() {
	// Initialize local random source
	r := rand.New(rand.NewSource(time.Now().UnixNano()))

	// Check for ENV_FILE environment variable
	envFile := os.Getenv("ENV_FILE")
	var envSource string

	if envFile != "" {
		// Check if the specified file exists and is readable
		if _, err := os.Stat(envFile); err != nil {
			fmt.Printf("Error: Specified ENV_FILE '%s' is not accessible: %v\n", envFile, err)
			os.Exit(1)
		}
		// Load the specified env file
		if err := godotenv.Load(envFile); err != nil {
			fmt.Printf("Error loading specified env file '%s': %v\n", envFile, err)
			os.Exit(1)
		}
		envSource = fmt.Sprintf("Environment loaded from specified ENV_FILE: %s", envFile)
	} else {
		// Try to load default .env file, but don't error if it doesn't exist
		if err := godotenv.Load(); err != nil {
			envSource = "Using environment variables (no .env file found)"
		} else {
			envSource = "Environment loaded from default .env file in current directory"
		}
	}

	fmt.Println(envSource)

	// Get environment variables
	required := map[string]string{
		"AWS_REGION":            os.Getenv("AWS_REGION"),
		"AWS_ACCESS_KEY_ID":     os.Getenv("AWS_ACCESS_KEY_ID"),
		"AWS_SECRET_ACCESS_KEY": os.Getenv("AWS_SECRET_ACCESS_KEY"),
		"SQS_QUEUE_URL":         os.Getenv("SQS_QUEUE_URL"),
	}

	// Check for missing required variables
	var missing []string
	for name, value := range required {
		if value == "" {
			missing = append(missing, name)
		}
	}

	if len(missing) > 0 {
		fmt.Printf("\nMissing required environment variables in %s:\n%s\n\n",
			strings.TrimPrefix(envSource, "Environment loaded from "),
			strings.Join(missing, "\n"))
		fmt.Println("Required variables:")
		fmt.Println("- AWS_REGION")
		fmt.Println("- AWS_ACCESS_KEY_ID")
		fmt.Println("- AWS_SECRET_ACCESS_KEY")
		fmt.Println("- SQS_QUEUE_URL")
		fmt.Println("\nOptional variables:")
		fmt.Println("- COLOR (hex color code, e.g., #4287f5)")
		os.Exit(1)
	}

	// Get optional color variable
	color := os.Getenv("COLOR")
	if color == "" {
		color = "#4287f5" // Default to a nice blue if not specified
	}

	// Validate color format
	if !hexColorRegex.MatchString(color) {
		fmt.Printf("Error: COLOR must be a valid hex color code (e.g., #4287f5), got: %s\n", color)
		os.Exit(1)
	}

	fmt.Println("Starting message publisher...")
	startTime := time.Now()

	// Print stats every minute
	go func() {
		ticker := time.NewTicker(1 * time.Minute)
		defer ticker.Stop()

		for range ticker.C {
			sent := atomic.LoadUint64(&messagesSent)
			errors := atomic.LoadUint64(&messagesError)
			uptime := time.Since(startTime).Round(time.Second)

			fmt.Printf("\n=== Stats (Uptime: %v) ===\n", uptime)
			fmt.Printf("Messages Sent: %d\n", sent)
			fmt.Printf("Errors: %d\n", errors)
			fmt.Printf("Success Rate: %.2f%%\n", float64(sent)/(float64(sent+errors))*100)
			fmt.Println("===========================")
		}
	}()

	// Continuously send messages
	for {
		hostname, err := os.Hostname()
		if err != nil {
			hostname = "unknown"
		}

		msg := Message{
			VMName:      hostname,
			IconName:    GetRandomIcon(r),
			Timestamp:   time.Now().Format(time.RFC3339),
			Color:       color,
			ContainerID: getContainerID(),
		}

		if err := sendSQSMessage(msg, os.Getenv("AWS_REGION"), os.Getenv("AWS_ACCESS_KEY_ID"), os.Getenv("AWS_SECRET_ACCESS_KEY"), os.Getenv("SQS_QUEUE_URL")); err != nil {
			atomic.AddUint64(&messagesError, 1)
			fmt.Printf("❌ Error sending message: %v\n", err)
		} else {
			atomic.AddUint64(&messagesSent, 1)
			msgJSON, _ := json.Marshal(msg)
			fmt.Printf("✅ Successfully sent message: %s\n", string(msgJSON))
		}

		sleepTime := 100 + r.Intn(2900) // 100ms to 3000ms
		time.Sleep(time.Duration(sleepTime) * time.Millisecond)
	}
}
