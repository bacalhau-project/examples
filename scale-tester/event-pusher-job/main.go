package main

import (
	"context"
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
	"github.com/joho/godotenv"
)

// Message represents the structure we'll send to SQS
type Message struct {
	VMName    string `json:"vm_name"`
	IconName  string `json:"icon_name"`
	Timestamp string `json:"timestamp"`
}

func getRandomIcon(r *rand.Rand) string {
	return icons[r.Intn(len(icons))]
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

	// Configure AWS credentials
	awsCfg, err := config.LoadDefaultConfig(context.Background(),
		config.WithRegion(awsRegion),
		config.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(
			awsAccessKey,
			awsSecretKey,
			"",
		)))

	if err != nil {
		fmt.Printf("Failed to configure AWS: %v\n", err)
		os.Exit(1)
	}

	// Create SQS client
	sqsClient := sqs.NewFromConfig(awsCfg)

	fmt.Println("Starting message publisher...")

	// Continuously send messages
	for {
		// Create message
		msg := Message{
			VMName:    fmt.Sprintf("vm-%d", r.Intn(100)),
			IconName:  getRandomIcon(r),
			Timestamp: time.Now().Format(time.RFC3339),
		}

		// Convert message to JSON
		msgJSON, err := json.Marshal(msg)
		if err != nil {
			fmt.Printf("Error marshaling message: %v\n", err)
			continue
		}

		// Send message to SQS
		_, err = sqsClient.SendMessage(context.TODO(), &sqs.SendMessageInput{
			QueueUrl:    aws.String(queueURL),
			MessageBody: aws.String(string(msgJSON)),
		})
		if err != nil {
			fmt.Printf("Error sending message: %v\n", err)
			continue
		}

		fmt.Printf("Sent message: %s\n", string(msgJSON))

		// Random sleep between 0.1 and 3 seconds
		sleepTime := 100 + r.Intn(2900) // 100ms to 3000ms
		time.Sleep(time.Duration(sleepTime) * time.Millisecond)
	}
}
