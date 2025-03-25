package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/Azure/azure-sdk-for-go/sdk/data/azcosmos"
	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/sqs"
	"github.com/charmbracelet/bubbles/table"
	"github.com/joho/godotenv"

	"github.com/aws/aws-sdk-go/aws/session"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/mattn/go-isatty"
)

const (
	// Default values - can be overridden by environment variables
	DEFAULT_POLL_INTERVAL = 100 * time.Millisecond // Interval between SQS polls
	DEFAULT_MAX_MESSAGES  = 10                     // Maximum allowed by SQS
	DEFAULT_WS_BATCH_SIZE = 100                    // Messages to batch for websocket
	DEFAULT_NUM_WORKERS   = 5                      // Concurrent polling workers
	DEFAULT_BUFFER_SIZE   = 1000                   // Channel buffer size for messages

	// Default values for SQS operations
	DEFAULT_MAX_RETRY_ATTEMPTS  = 5                      // Maximum number of retry attempts
	DEFAULT_INITIAL_RETRY_DELAY = 100 * time.Millisecond // Starting delay for exponential backoff
	DEFAULT_MAX_RETRY_DELAY     = 5 * time.Second        // Maximum retry delay
	DEFAULT_SQS_VISIBILITY      = 30                     // Default visibility timeout for SQS
	DEFAULT_SQS_WAIT_TIME       = 0                      // Default wait time for SQS polling
)

type Message struct {
	Id          string `json:"id,omitempty"` // Used for Cosmos DB
	VMName      string `json:"vm_name"`
	ContainerID string `json:"container_id"`
	IconName    string `json:"icon_name"`
	Color       string `json:"color"`
	Timestamp   string `json:"timestamp"`
	Region      string `json:"region,omitempty"`     // Used for Cosmos DB partitioning
	Type        string `json:"type,omitempty"`       // Document type for Cosmos DB
	EventTime   int64  `json:"event_time,omitempty"` // Unix timestamp for sorting
}

type model struct {
	table              table.Model
	lastPoll           time.Time
	queueURL           string
	queueSize          int64
	totalProcessed     uint64
	messages           []Message
	hub                *Hub
	showConfirmClear   bool
	sqsClient          *sqs.SQS
	ctx                context.Context
	cancel             context.CancelFunc
	lastQueueCheck     time.Time
	logs               []string
	maxLogs            int
	messageChan        chan Message
	updateLock         sync.Mutex
	cosmosClient       *azcosmos.Client
	cosmosContainer    *azcosmos.ContainerClient
	cosmosBatchSize    int
	cosmosEnabled      bool
	cosmosMessagesLock sync.Mutex
	cosmosMessages     []Message
	cosmosWriteTimer   *time.Timer
	messageCount       int64
	messageCountLock   sync.Mutex
	lastCountLog       time.Time

	// Configuration from environment
	pollInterval      time.Duration
	maxMessages       int64
	wsBatchSize       int
	numWorkers        int
	bufferSize        int
	maxRetryAttempts  int
	initialRetryDelay time.Duration
	maxRetryDelay     time.Duration
	sqsVisibility     int64
	sqsWaitTime       int64
}

type tickMsg time.Time

// messageProcessor handles batching of messages for efficient websocket updates
type messageProcessor struct {
	messages    []Message
	lastUpdate  time.Time
	updateLock  sync.Mutex
	batchSize   int
	maxInterval time.Duration
}

func newMessageProcessor(batchSize int, maxInterval time.Duration) *messageProcessor {
	return &messageProcessor{
		messages:    make([]Message, 0, batchSize),
		batchSize:   batchSize,
		maxInterval: maxInterval,
	}
}

func (mp *messageProcessor) add(msg Message) ([]Message, bool) {
	mp.updateLock.Lock()
	defer mp.updateLock.Unlock()

	mp.messages = append(mp.messages, msg)

	shouldUpdate := len(mp.messages) >= mp.batchSize ||
		(len(mp.messages) > 0 && time.Since(mp.lastUpdate) >= mp.maxInterval)

	if shouldUpdate {
		batch := mp.messages
		mp.messages = make([]Message, 0, mp.batchSize)
		mp.lastUpdate = time.Now()
		return batch, true
	}

	return nil, false
}

func (m *model) Init() tea.Cmd {
	return tea.Tick(POLL_INTERVAL, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func (m *model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmd tea.Cmd
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "q", "ctrl+c":
			m.cancel()
			return m, tea.Quit
		case "c":
			if !m.showConfirmClear {
				m.showConfirmClear = true
				return m, nil
			}
		case "p":
			if err := purgeQueue(m.ctx, m, m.sqsClient, m.queueURL); err != nil {
				m.addLog("Error purging queue: %v", err)
			}
			return m, nil
		case "t":
			cutoff := time.Now().Add(-1 * time.Hour)
			go clearQueueBefore(m.ctx, m, m.sqsClient, m.queueURL, cutoff)
			return m, nil
		case "y":
			if m.showConfirmClear {
				m.showConfirmClear = false
				m.addLog("Starting queue clear operation...")
				go clearQueue(m.ctx, m, m.sqsClient, m.queueURL)
				return m, nil
			}
		case "n":
			if m.showConfirmClear {
				m.showConfirmClear = false
				return m, nil
			}
		}

	case tickMsg:
		select {
		case <-m.ctx.Done():
			return m, tea.Quit
		default:
			// Display updates are handled by the message channel
			return m, m.Init()
		}
	}

	m.table, cmd = m.table.Update(msg)
	return m, cmd
}

func (m model) View() string {
	if m.showConfirmClear {
		return "⚠️  Are you sure you want to clear the queue? This cannot be undone.\nPress 'y' to confirm or 'n' to cancel\n"
	}

	var s strings.Builder

	s.WriteString("\n🔄 SQS Queue Monitor (Optimized)\n\n")
	s.WriteString(fmt.Sprintf(
		"Queue Status:\n"+
			"  Total Messages in Queue: %d\n"+
			"  Messages Processed: %d\n"+
			"  Last Poll: %s\n"+
			"  Queue URL: %s\n"+
			"  Region: %s\n",
		m.queueSize,
		m.totalProcessed,
		m.lastPoll.Format("15:04:05.000"),
		m.queueURL,
		os.Getenv("AWS_REGION"),
	))

	if m.cosmosEnabled {
		s.WriteString(fmt.Sprintf(
			"Cosmos DB Status:\n"+
				"  Status: Connected\n"+
				"  Database: %s\n"+
				"  Container: %s\n"+
				"  Batch Size: %d\n\n",
			os.Getenv("COSMOS_DATABASE"),
			os.Getenv("COSMOS_CONTAINER"),
			m.cosmosBatchSize,
		))
	} else {
		s.WriteString("\nCosmos DB: Not configured\n\n")
	}

	if len(m.messages) > 0 {
		s.WriteString(fmt.Sprintf("Recent Messages (%d):\n", len(m.messages)))
		s.WriteString(m.table.View())
		s.WriteString("\n")
	} else {
		s.WriteString("No messages in current batch\n\n")
	}

	s.WriteString("\nControls:\n")
	s.WriteString("'c' - Clear queue gradually\n")
	s.WriteString("'p' - Purge entire queue instantly\n")
	s.WriteString("'t' - Clear messages older than 1 hour\n")
	s.WriteString("'q' - Quit\n")

	s.WriteString("\nOperation Logs (last 10):\n")
	s.WriteString("──────────────────────────────────────────────────────────\n")

	startIdx := len(m.logs)
	if startIdx > 10 {
		startIdx = len(m.logs) - 10
	}
	for _, log := range m.logs[startIdx:] {
		s.WriteString(log + "\n")
	}

	return s.String()
}

func (m *model) startMessageWorker(workerID int) {
	mp := newMessageProcessor(WS_BATCH_SIZE, 500*time.Millisecond)
	m.addLog("Worker %d started", workerID)

	// Use a counter to limit frequent error logging
	errorCount := 0
	maxErrorLogging := 5

	// Track credential errors separately to avoid excessive logging
	lastCredentialErrorTime := time.Time{}
	credentialErrorInterval := 60 * time.Second

	for {
		select {
		case <-m.ctx.Done():
			m.addLog("Worker %d shutting down", workerID)
			return
		default:
			messages, err := receiveMessages(m.ctx, m.sqsClient, m.queueURL, m.maxMessages, m.sqsWaitTime, m.sqsVisibility, m.maxRetryAttempts, m.initialRetryDelay, m.maxRetryDelay)
			if err != nil {
				isCredentialError := strings.Contains(err.Error(), "InvalidClientTokenId") ||
					strings.Contains(err.Error(), "security token")

				// Log credential errors with rate limiting
				if isCredentialError {
					if time.Since(lastCredentialErrorTime) > credentialErrorInterval {
						m.addLog("Worker %d authentication error: AWS credentials are invalid or expired", workerID)
						lastCredentialErrorTime = time.Now()
					}
					// Use a longer backoff for credential errors
					time.Sleep(5 * time.Second)
					continue
				}

				// For other non-transient errors, log with rate limiting
				if !isTransientError(err) {
					if errorCount < maxErrorLogging {
						m.addLog("Worker %d error receiving messages: %v", workerID, err)
						errorCount++

						if errorCount == maxErrorLogging {
							m.addLog("Worker %d: Too many errors, suppressing further error logs", workerID)
						}
					}
				}

				// Use exponential backoff for errors
				backoffDuration := calculateBackoff(1, m.maxRetryAttempts, m.initialRetryDelay, m.maxRetryDelay)
				time.Sleep(backoffDuration)
				continue
			}

			// Reset error counter on success
			errorCount = 0

			if len(messages) > 0 {
				m.updateLock.Lock()
				m.lastPoll = time.Now()
				m.totalProcessed += uint64(len(messages))
				m.messages = messages // Update the messages slice for display
				m.updateLock.Unlock()

				// Increment message count for periodic logging
				m.incrementMessageCount(len(messages))

				m.addLog("Worker %d received %d messages", workerID, len(messages))

				// Process messages in batches for efficient updates
				for _, msg := range messages {
					// Send to Cosmos DB if enabled
					if m.cosmosEnabled {
						m.addMessageToCosmosBatch(msg)
					}

					// Send to WebSocket UI
					if batch, shouldUpdate := mp.add(msg); shouldUpdate {
						if err := m.sendWebSocketUpdate(batch); err != nil {
							m.addLog("Error sending websocket update: %v", err)
						} else {
							m.addLog("Sent websocket update with %d messages", len(batch))
						}
					}
				}
			}

			// Small sleep to prevent tight polling
			time.Sleep(POLL_INTERVAL / 2)
		}
	}
}

func (m *model) sendWebSocketUpdate(messages []Message) error {
	update := struct {
		Messages  []Message `json:"messages"`
		LastPoll  string    `json:"last_poll"`
		QueueSize int       `json:"queue_size"`
	}{
		Messages:  messages,
		LastPoll:  m.lastPoll.Format("15:04:05.000"),
		QueueSize: int(m.queueSize),
	}

	jsonData, err := json.Marshal(update)
	if err != nil {
		return fmt.Errorf("failed to marshal update: %v", err)
	}

	m.hub.broadcast <- jsonData
	return nil
}

func isTransientError(err error) bool {
	if err == nil {
		return false
	}
	errStr := err.Error()
	return strings.Contains(errStr, "no such host") ||
		strings.Contains(errStr, "connection refused") ||
		strings.Contains(errStr, "timeout")
}

// calculateBackoff implements exponential backoff for retries
func calculateBackoff(attempt, maxAttempts int, initialDelay, maxDelay time.Duration) time.Duration {
	if attempt >= maxAttempts {
		return maxDelay
	}

	// Add jitter to avoid thundering herd problem
	jitter := time.Duration(rand.Int63n(100)) * time.Millisecond
	backoff := initialDelay*time.Duration(1<<uint(attempt)) + jitter

	if backoff > maxDelay {
		return maxDelay
	}

	return backoff
}

// receiveMessages retrieves messages from SQS with retry logic
func receiveMessages(ctx context.Context, sqsClient *sqs.SQS, queueURL string, maxMessages, waitTime, visibilityTimeout int64, maxRetryAttempts int, initialRetryDelay, maxRetryDelay time.Duration) ([]Message, error) {
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	default:
	}

	// Check if it's a FIFO queue
	isFifoQueue := strings.HasSuffix(queueURL, ".fifo")

	input := &sqs.ReceiveMessageInput{
		QueueUrl:            aws.String(queueURL),
		MaxNumberOfMessages: aws.Int64(maxMessages),
		WaitTimeSeconds:     aws.Int64(waitTime),
		VisibilityTimeout:   aws.Int64(visibilityTimeout),
		AttributeNames: []*string{
			aws.String("All"),
		},
		MessageAttributeNames: []*string{
			aws.String("All"),
		},
	}

	// Add FIFO specific attributes
	if isFifoQueue {
		input.ReceiveRequestAttemptId = aws.String(fmt.Sprintf("attempt-%d", time.Now().UnixNano()))
	}

	// Use retry with exponential backoff for receiving messages
	var result *sqs.ReceiveMessageOutput
	var err error

	for attempt := 0; attempt < maxRetryAttempts; attempt++ {
		result, err = sqsClient.ReceiveMessageWithContext(ctx, input)
		if err == nil {
			break // Success
		}

		if !isTransientError(err) {
			return nil, fmt.Errorf("failed to receive messages: %v", err)
		}

		// Only retry on transient errors
		backoffDuration := calculateBackoff(attempt, maxRetryAttempts, initialRetryDelay, maxRetryDelay)
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(backoffDuration):
			// Continue with retry
		}
	}

	// If we exhausted all retries
	if err != nil {
		return nil, fmt.Errorf("failed to receive messages after %d attempts: %v", maxRetryAttempts, err)
	}

	if len(result.Messages) == 0 {
		return nil, nil
	}

	sort.Slice(result.Messages, func(i, j int) bool {
		iTime, _ := strconv.ParseInt(*result.Messages[i].Attributes["SentTimestamp"], 10, 64)
		jTime, _ := strconv.ParseInt(*result.Messages[j].Attributes["SentTimestamp"], 10, 64)
		return iTime < jTime
	})

	var messages []Message
	var deleteEntries []*sqs.DeleteMessageBatchRequestEntry

	for i, msg := range result.Messages {
		var message Message
		if err := json.Unmarshal([]byte(*msg.Body), &message); err != nil {
			log.Printf("Error unmarshaling message: %v", err)
			continue
		}
		messages = append(messages, message)

		entry := &sqs.DeleteMessageBatchRequestEntry{
			Id:            aws.String(strconv.Itoa(i)),
			ReceiptHandle: msg.ReceiptHandle,
		}
		deleteEntries = append(deleteEntries, entry)
	}

	if len(deleteEntries) > 0 {
		deleteInput := &sqs.DeleteMessageBatchInput{
			QueueUrl: aws.String(queueURL),
			Entries:  deleteEntries,
		}

		// Retry deletion a few times if needed
		for attempt := 0; attempt < maxRetryAttempts; attempt++ {
			_, err := sqsClient.DeleteMessageBatchWithContext(ctx, deleteInput)
			if err == nil {
				break // Success
			}

			// Only retry on transient errors
			if !isTransientError(err) {
				log.Printf("Error batch deleting messages: %v", err)
				break
			}

			backoffDuration := calculateBackoff(attempt, maxRetryAttempts, initialRetryDelay, maxRetryDelay)
			select {
			case <-ctx.Done():
				return messages, nil // Return messages even if deletion failed
			case <-time.After(backoffDuration):
				// Continue with retry
			}
		}
	}

	return messages, nil
}

// loadConfiguration loads and validates runtime configuration
func loadConfiguration() (time.Duration, int64, int, int, int, int, time.Duration, time.Duration, int64, int64, error) {
	// Load POLL_INTERVAL from environment or use default
	pollIntervalStr := os.Getenv("POLL_INTERVAL")
	var pollInterval time.Duration
	if pollIntervalStr != "" {
		var err error
		pollInterval, err = time.ParseDuration(pollIntervalStr)
		if err != nil {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("invalid POLL_INTERVAL format (e.g. 100ms, 1s): %v", err)
		}
		if pollInterval < 10*time.Millisecond {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("POLL_INTERVAL too small (min 10ms)")
		}
	} else {
		pollInterval = DEFAULT_POLL_INTERVAL
	}

	// Load MAX_MESSAGES from environment or use default
	maxMessagesStr := os.Getenv("MAX_MESSAGES")
	var maxMessages int64 = DEFAULT_MAX_MESSAGES
	if maxMessagesStr != "" {
		var err error
		maxMessages64, err := strconv.ParseInt(maxMessagesStr, 10, 64)
		if err != nil {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("invalid MAX_MESSAGES value: %v", err)
		}
		if maxMessages64 < 1 || maxMessages64 > 10 {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("MAX_MESSAGES must be between 1 and 10")
		}
		maxMessages = maxMessages64
	}

	// Load WS_BATCH_SIZE from environment or use default
	wsBatchSizeStr := os.Getenv("WS_BATCH_SIZE")
	var wsBatchSize int = DEFAULT_WS_BATCH_SIZE
	if wsBatchSizeStr != "" {
		var err error
		wsBatchSize, err = strconv.Atoi(wsBatchSizeStr)
		if err != nil {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("invalid WS_BATCH_SIZE value: %v", err)
		}
		if wsBatchSize < 1 {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("WS_BATCH_SIZE must be at least 1")
		}
	}

	// Load NUM_WORKERS from environment or use default
	numWorkersStr := os.Getenv("NUM_WORKERS")
	var numWorkers int = DEFAULT_NUM_WORKERS
	if numWorkersStr != "" {
		var err error
		numWorkers, err = strconv.Atoi(numWorkersStr)
		if err != nil {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("invalid NUM_WORKERS value: %v", err)
		}
		if numWorkers < 1 {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("NUM_WORKERS must be at least 1")
		}
	}

	// Load BUFFER_SIZE from environment or use default
	bufferSizeStr := os.Getenv("BUFFER_SIZE")
	var bufferSize int = DEFAULT_BUFFER_SIZE
	if bufferSizeStr != "" {
		var err error
		bufferSize, err = strconv.Atoi(bufferSizeStr)
		if err != nil {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("invalid BUFFER_SIZE value: %v", err)
		}
		if bufferSize < 10 {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("BUFFER_SIZE must be at least 10")
		}
	}

	// Load MAX_RETRY_ATTEMPTS from environment or use default
	maxRetryAttemptsStr := os.Getenv("MAX_RETRY_ATTEMPTS")
	var maxRetryAttempts int = DEFAULT_MAX_RETRY_ATTEMPTS
	if maxRetryAttemptsStr != "" {
		var err error
		maxRetryAttempts, err = strconv.Atoi(maxRetryAttemptsStr)
		if err != nil {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("invalid MAX_RETRY_ATTEMPTS value: %v", err)
		}
		if maxRetryAttempts < 1 {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("MAX_RETRY_ATTEMPTS must be at least 1")
		}
	}

	// Load INITIAL_RETRY_DELAY from environment or use default
	initialRetryDelayStr := os.Getenv("INITIAL_RETRY_DELAY")
	var initialRetryDelay time.Duration = DEFAULT_INITIAL_RETRY_DELAY
	if initialRetryDelayStr != "" {
		var err error
		initialRetryDelay, err = time.ParseDuration(initialRetryDelayStr)
		if err != nil {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("invalid INITIAL_RETRY_DELAY format (e.g. 100ms, 1s): %v", err)
		}
		if initialRetryDelay < 10*time.Millisecond {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("INITIAL_RETRY_DELAY too small (min 10ms)")
		}
	}

	// Load MAX_RETRY_DELAY from environment or use default
	maxRetryDelayStr := os.Getenv("MAX_RETRY_DELAY")
	var maxRetryDelay time.Duration = DEFAULT_MAX_RETRY_DELAY
	if maxRetryDelayStr != "" {
		var err error
		maxRetryDelay, err = time.ParseDuration(maxRetryDelayStr)
		if err != nil {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("invalid MAX_RETRY_DELAY format (e.g. 1s, 5s): %v", err)
		}
		if maxRetryDelay < 100*time.Millisecond {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("MAX_RETRY_DELAY too small (min 100ms)")
		}
	}

	// Load SQS_VISIBILITY_TIMEOUT from environment or use default
	sqsVisibilityStr := os.Getenv("SQS_VISIBILITY_TIMEOUT")
	var sqsVisibility int64 = DEFAULT_SQS_VISIBILITY
	if sqsVisibilityStr != "" {
		var err error
		sqsVisibility, err = strconv.ParseInt(sqsVisibilityStr, 10, 64)
		if err != nil {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("invalid SQS_VISIBILITY_TIMEOUT value: %v", err)
		}
		if sqsVisibility < 0 {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("SQS_VISIBILITY_TIMEOUT must be non-negative")
		}
	}

	// Load SQS_WAIT_TIME from environment or use default
	sqsWaitTimeStr := os.Getenv("SQS_WAIT_TIME")
	var sqsWaitTime int64 = DEFAULT_SQS_WAIT_TIME
	if sqsWaitTimeStr != "" {
		var err error
		sqsWaitTime, err = strconv.ParseInt(sqsWaitTimeStr, 10, 64)
		if err != nil {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("invalid SQS_WAIT_TIME value: %v", err)
		}
		if sqsWaitTime < 0 || sqsWaitTime > 20 {
			return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, fmt.Errorf("SQS_WAIT_TIME must be between 0 and 20 seconds")
		}
	}

	return pollInterval, maxMessages, wsBatchSize, numWorkers, bufferSize, maxRetryAttempts, initialRetryDelay, maxRetryDelay, sqsVisibility, sqsWaitTime, nil
}

func initialModel(ctx context.Context, queueURL string, sqsClient *sqs.SQS, hub *Hub) model {
	// Load configuration from environment
	pollInterval, maxMessages, wsBatchSize, numWorkers, bufferSize, maxRetryAttempts, initialRetryDelay, maxRetryDelay, sqsVisibility, sqsWaitTime, err := loadConfiguration()
	if err != nil {
		log.Printf("Warning: Error loading configuration: %v, using defaults", err)
		pollInterval = DEFAULT_POLL_INTERVAL
		maxMessages = DEFAULT_MAX_MESSAGES
		wsBatchSize = DEFAULT_WS_BATCH_SIZE
		numWorkers = DEFAULT_NUM_WORKERS
		bufferSize = DEFAULT_BUFFER_SIZE
		maxRetryAttempts = DEFAULT_MAX_RETRY_ATTEMPTS
		initialRetryDelay = DEFAULT_INITIAL_RETRY_DELAY
		maxRetryDelay = DEFAULT_MAX_RETRY_DELAY
		sqsVisibility = DEFAULT_SQS_VISIBILITY
		sqsWaitTime = DEFAULT_SQS_WAIT_TIME
	}

	// Validate queue exists and permissions
	// This is just a validation check - we'll continue even if it fails
	_, err = sqsClient.GetQueueAttributes(&sqs.GetQueueAttributesInput{
		QueueUrl: aws.String(queueURL),
		AttributeNames: []*string{
			aws.String("QueueArn"),
		},
	})
	if err != nil {
		log.Printf("Warning: Could not validate queue: %v", err)
		log.Printf("Make sure the queue exists and you have the correct permissions")
		log.Printf("Queue URL: %s", queueURL)
		log.Printf("Region: %s", os.Getenv("AWS_REGION"))
		log.Printf("Application will continue but may not function correctly until valid credentials are provided")
	}

	columns := []table.Column{
		{Title: "VM Name", Width: 15},
		{Title: "Container", Width: 12},
		{Title: "Icon", Width: 8},
		{Title: "Color", Width: 8},
		{Title: "Timestamp", Width: 30},
	}

	t := table.New(
		table.WithColumns(columns),
		table.WithFocused(true),
		table.WithHeight(10),
	)

	modelCtx, cancel := context.WithCancel(ctx)
	m := model{
		table:            t,
		queueURL:         queueURL,
		hub:              hub,
		lastPoll:         time.Now(),
		sqsClient:        sqsClient,
		ctx:              modelCtx,
		cancel:           cancel,
		lastQueueCheck:   time.Time{},
		maxLogs:          1000,
		logs:             make([]string, 0, 1000),
		messageChan:      make(chan Message, bufferSize),
		cosmosEnabled:    false,
		cosmosBatchSize:  100,
		cosmosMessages:   make([]Message, 0, 100),
		messageCount:     0,
		lastCountLog:     time.Now(),

		// Configuration
		pollInterval:      pollInterval,
		maxMessages:       maxMessages,
		wsBatchSize:       wsBatchSize,
		numWorkers:        numWorkers,
		bufferSize:        bufferSize,
		maxRetryAttempts:  maxRetryAttempts,
		initialRetryDelay: initialRetryDelay,
		maxRetryDelay:     maxRetryDelay,
		sqsVisibility:     sqsVisibility,
		sqsWaitTime:       sqsWaitTime,
	}

	// Add initial logs
	m.addLog("Starting SQS Queue Monitor...")
	m.addLog("Queue URL: %s", queueURL)
	m.addLog("Region: %s", os.Getenv("AWS_REGION"))
	m.addLog("Configuration: poll=%v, workers=%d, maxMsg=%d, wsBatch=%d, retry=%d, visibility=%ds",
		pollInterval, numWorkers, maxMessages, wsBatchSize, maxRetryAttempts, sqsVisibility)

	if strings.HasSuffix(queueURL, ".fifo") {
		m.addLog("FIFO queue detected - using FIFO-specific handling")
	}

	// Initialize Cosmos DB client if config is provided
	if client, enabled, err := initCosmosClient(modelCtx); err != nil {
		m.addLog("Failed to initialize Cosmos DB client: %v", err)
	} else if enabled {
		m.cosmosClient = client
		m.cosmosEnabled = true
		m.addLog("Cosmos DB client initialized successfully")

		// Get container
		if container, err := getCosmosContainer(client, modelCtx); err != nil {
			m.addLog("Failed to get Cosmos DB container: %v", err)
			m.cosmosEnabled = false
		} else {
			m.cosmosContainer = container
			m.addLog("Connected to Cosmos DB container %s in database %s",
				os.Getenv("COSMOS_CONTAINER"), os.Getenv("COSMOS_DATABASE"))
		}
	}

	// Set batch size from environment if provided
	if batchSizeStr := os.Getenv("COSMOS_BATCH_SIZE"); batchSizeStr != "" {
		if batchSize, err := strconv.Atoi(batchSizeStr); err == nil && batchSize > 0 {
			m.cosmosBatchSize = batchSize
			m.addLog("Cosmos DB batch size set to %d", batchSize)
		}
	}

	// Start multiple polling workers
	for i := 0; i < NUM_WORKERS; i++ {
		workerID := i
		go m.startMessageWorker(workerID)
	}

	// Start background queue size checker
	go m.backgroundQueueSizeChecker()

	// Start a background goroutine to periodically flush cosmos messages
	if m.cosmosEnabled {
		go func() {
			ticker := time.NewTicker(5 * time.Second)
			defer ticker.Stop()

			for {
				select {
				case <-modelCtx.Done():
					// Flush any remaining messages before shutdown
					m.flushCosmosBatch()
					return
				case <-ticker.C:
					m.flushCosmosBatch()
				}
			}
		}()
	}

	return m
}

func main() {
	// Set up logging immediately
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)
	log.SetOutput(os.Stderr)
	log.Println("Starting event-puller application...")

	// Print some system information
	log.Println("System information:")
	log.Printf("  Working directory: %s", getWorkingDirectory())
	log.Printf("  Container: %t", runningInContainer())
	log.Printf("  UID/GID: %d/%d", os.Getuid(), os.Getgid())

	// Initialize random seed for jitter
	rand.Seed(time.Now().UnixNano())
	log.Println("Random seed initialized")

	// Load environment configuration with better error handling
	log.Println("Loading environment configuration...")
	if err := loadEnvConfig(); err != nil {
		log.Printf("CRITICAL ERROR: Environment configuration failed: %v", err)
		log.Fatalf("\nEnvironment configuration error: %v\n", err)
	}
	log.Println("Environment configuration loaded successfully")

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM, syscall.SIGQUIT)
	log.Println("Signal handlers configured")

	queueURL := os.Getenv("SQS_QUEUE_URL")
	region := os.Getenv("AWS_REGION")

	// Configure AWS Session with optimized settings
	awsConfig := &aws.Config{
		Region: aws.String(region),
		HTTPClient: &http.Client{
			Transport: &http.Transport{
				MaxIdleConns:        100,
				MaxIdleConnsPerHost: 100,
				IdleConnTimeout:     90 * time.Second,
			},
			Timeout: 10 * time.Second,
		},
	}

	sess, err := session.NewSession(awsConfig)
	if err != nil {
		log.Fatalf("Failed to create AWS session: %v\n", err)
	}

	sqsClient := sqs.New(sess)
	hub := newHub()
	go hub.run()

	m := initialModel(ctx, queueURL, sqsClient, hub)

	// Configure websocket server with optimized settings
	server := &http.Server{
		Addr:    ":8080",
		Handler: http.DefaultServeMux,
	}

	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		// Direct access to model instance
		serveWs(hub, w, r, &m)
	})

	// First check if we have a dashboard directory, use it if it exists
	if _, err := os.Stat("dashboard/out"); err == nil {
		// Serve Next.js static export
		m.addLog("Serving Next.js dashboard from dashboard/out directory")
		http.Handle("/", http.FileServer(http.Dir("dashboard/out")))
	} else if _, err := os.Stat("static"); err == nil {
		// Fall back to the old static HTML if dashboard isn't built
		m.addLog("Serving static HTML dashboard from static directory")
		http.Handle("/", http.FileServer(http.Dir("static")))
	} else {
		m.addLog("No dashboard found, serving minimal status page")
		http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "text/html")
			w.Write([]byte(`
				<html>
					<head>
						<title>Event Puller</title>
						<meta http-equiv="refresh" content="5">
						<style>
							body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
							.status { padding: 10px; border-radius: 4px; margin: 10px 0; }
							.running { background-color: #d4edda; color: #155724; }
							.error { background-color: #f8d7da; color: #721c24; }
						</style>
					</head>
					<body>
						<h1>Event Puller</h1>
						<div class="status running">
							<h3>Service Status: Running</h3>
							<p>Event Puller is running but no dashboard is available.</p>
							<p>Connect to the WebSocket API at ws://` + r.Host + `/ws</p>
							<p>or use the Terminal UI on the server.</p>
						</div>
						<p>Page auto-refreshes every 5 seconds</p>
					</body>
				</html>
			`))
		})
	}

	// Handle CLI actions via HTTP for dashboard communication
	http.HandleFunc("/api/actions", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		var action struct {
			Action string `json:"action"`
		}

		if err := json.NewDecoder(r.Body).Decode(&action); err != nil {
			http.Error(w, "Invalid JSON", http.StatusBadRequest)
			return
		}

		switch action.Action {
		case "clearQueue":
			go clearQueue(m.ctx, &m, m.sqsClient, m.queueURL)
			w.WriteHeader(http.StatusAccepted)
			json.NewEncoder(w).Encode(map[string]string{"status": "queue clear started"})
		case "purgeQueue":
			err := purgeQueue(m.ctx, &m, m.sqsClient, m.queueURL)
			if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			w.WriteHeader(http.StatusOK)
			json.NewEncoder(w).Encode(map[string]string{"status": "queue purged"})
		default:
			http.Error(w, "Unknown action", http.StatusBadRequest)
		}
	})

	go func() {
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			m.addLog("WebSocket server error: %v", err)
		}
	}()

	go func() {
		sig := <-sigChan
		m.addLog("Received signal %v, initiating shutdown...", sig)
		cancel()

		// Graceful shutdown of HTTP server
		shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer shutdownCancel()

		if err := server.Shutdown(shutdownCtx); err != nil {
			m.addLog("Error during server shutdown: %v", err)
		}
	}()

	// Check if we're running in a headless environment
	isHeadless := os.Getenv("TERM") == "" || os.Getenv("TERM") == "dumb" || !isatty.IsTerminal(os.Stdout.Fd())

	if isHeadless {
		log.Println("Running in headless mode - terminal UI disabled")
		log.Println("Web interface is now available at http://localhost:8080")
		log.Println("Press Ctrl+C to stop the application")
		m.addLog("Running in headless mode - terminal UI disabled")
		
		// Create /app/healthy file to indicate service is running
		healthFile := "/app/healthy"
		if err := os.WriteFile(healthFile, []byte("ok"), 0644); err != nil {
			log.Printf("Warning: Could not create health file at %s: %v", healthFile, err)
		} else {
			log.Printf("Created health file at %s", healthFile)
		}
		
		// In headless mode, just keep the program running
		<-m.ctx.Done()
		
		// Remove health file on exit
		if err := os.Remove(healthFile); err != nil && !os.IsNotExist(err) {
			log.Printf("Warning: Could not remove health file at %s: %v", healthFile, err)
		}
	} else {
		// In terminal mode, run the bubbletea program
		p := tea.NewProgram(&m, tea.WithAltScreen())
		if _, err := p.Run(); err != nil {
			log.Fatalf("Error running program: %v\n", err)
		}
	}
}

func loadEnvConfig() error {
	// Enable standard logging to see diagnostics
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)
	log.SetOutput(os.Stderr)

	log.Println("Starting environment configuration...")
	envFile := os.Getenv("ENV_FILE")
	var envSource string

	if envFile != "" {
		log.Printf("ENV_FILE specified: %s", envFile)
		// Check if file exists
		if _, err := os.Stat(envFile); err != nil {
			log.Printf("ERROR: ENV_FILE '%s' does not exist or is not readable: %v", envFile, err)
			// Print directory contents for debugging
			dir := filepath.Dir(envFile)
			log.Printf("Contents of directory %s:", dir)
			files, _ := os.ReadDir(dir)
			for _, file := range files {
				log.Printf("  %s", file.Name())
			}
			return fmt.Errorf("specified ENV_FILE '%s' does not exist or is not readable: %v", envFile, err)
		}

		// Try to read file content
		content, err := os.ReadFile(envFile)
		if err != nil {
			log.Printf("ERROR: Failed to read ENV_FILE '%s': %v", envFile, err)
			return fmt.Errorf("error reading specified env file '%s': %v", envFile, err)
		}
		log.Printf("ENV_FILE content length: %d bytes", len(content))

		// Try to load env file
		if err := godotenv.Load(envFile); err != nil {
			log.Printf("ERROR: Failed to parse ENV_FILE '%s': %v", envFile, err)
			return fmt.Errorf("error loading specified env file '%s': %v", envFile, err)
		}
		log.Printf("Successfully loaded environment from ENV_FILE: %s", envFile)
		envSource = fmt.Sprintf("Environment loaded from specified ENV_FILE: %s", envFile)
	} else {
		log.Println("No ENV_FILE specified, looking for .env in current directory")
		if _, err := os.Stat(".env"); err != nil {
			log.Printf("ERROR: No ENV_FILE specified and no .env file found in current directory")
			log.Println("Current directory contents:")
			files, _ := os.ReadDir(".")
			for _, file := range files {
				log.Printf("  %s", file.Name())
			}
			return fmt.Errorf("no ENV_FILE specified and no .env file found in current directory")
		}
		if err := godotenv.Load(); err != nil {
			log.Printf("ERROR: Failed to load default .env file: %v", err)
			return fmt.Errorf("error loading default .env file: %v", err)
		}
		log.Println("Successfully loaded environment from default .env file")
		envSource = "Environment loaded from default .env file in current directory"
	}

	required := []string{"SQS_QUEUE_URL", "AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"}
	var missing []string

	log.Println("Checking for required environment variables...")
	for _, env := range required {
		if os.Getenv(env) == "" {
			log.Printf("Missing required environment variable: %s", env)
			missing = append(missing, env)
		} else {
			log.Printf("Found required environment variable: %s = %s", env, os.Getenv(env))
		}
	}

	if len(missing) > 0 {
		log.Printf("ERROR: Missing %d required environment variables", len(missing))
		return fmt.Errorf("\nMissing required environment variables in %s:\n%s\n\nPlease ensure all required variables are set in your environment file",
			strings.TrimPrefix(envSource, "Environment loaded from "),
			strings.Join(missing, "\n"))
	}

	// Log all configuration settings
	log.Println("Configuration settings:")
	
	// Required settings
	log.Printf("  SQS_QUEUE_URL = %s", os.Getenv("SQS_QUEUE_URL"))
	log.Printf("  AWS_REGION = %s", os.Getenv("AWS_REGION"))
	log.Printf("  AWS_ACCESS_KEY_ID = %s", os.Getenv("AWS_ACCESS_KEY_ID"))
	log.Printf("  AWS_SECRET_ACCESS_KEY = %s", os.Getenv("AWS_SECRET_ACCESS_KEY"))
	
	// Optional queue settings with defaults
	pollInterval := os.Getenv("POLL_INTERVAL")
	if pollInterval == "" {
		pollInterval = fmt.Sprintf("%v", DEFAULT_POLL_INTERVAL)
		log.Printf("  POLL_INTERVAL = %s (default)", pollInterval)
	} else {
		log.Printf("  POLL_INTERVAL = %s (user-defined)", pollInterval)
	}
	
	maxMessages := os.Getenv("MAX_MESSAGES")
	if maxMessages == "" {
		maxMessages = fmt.Sprintf("%d", DEFAULT_MAX_MESSAGES)
		log.Printf("  MAX_MESSAGES = %s (default)", maxMessages)
	} else {
		log.Printf("  MAX_MESSAGES = %s (user-defined)", maxMessages)
	}
	
	numWorkers := os.Getenv("NUM_WORKERS")
	if numWorkers == "" {
		numWorkers = fmt.Sprintf("%d", DEFAULT_NUM_WORKERS)
		log.Printf("  NUM_WORKERS = %s (default)", numWorkers)
	} else {
		log.Printf("  NUM_WORKERS = %s (user-defined)", numWorkers)
	}
	
	wsBatchSize := os.Getenv("WS_BATCH_SIZE")
	if wsBatchSize == "" {
		wsBatchSize = fmt.Sprintf("%d", DEFAULT_WS_BATCH_SIZE)
		log.Printf("  WS_BATCH_SIZE = %s (default)", wsBatchSize)
	} else {
		log.Printf("  WS_BATCH_SIZE = %s (user-defined)", wsBatchSize)
	}
	
	bufferSize := os.Getenv("BUFFER_SIZE")
	if bufferSize == "" {
		bufferSize = fmt.Sprintf("%d", DEFAULT_BUFFER_SIZE)
		log.Printf("  BUFFER_SIZE = %s (default)", bufferSize)
	} else {
		log.Printf("  BUFFER_SIZE = %s (user-defined)", bufferSize)
	}
	
	maxRetryAttempts := os.Getenv("MAX_RETRY_ATTEMPTS")
	if maxRetryAttempts == "" {
		maxRetryAttempts = fmt.Sprintf("%d", DEFAULT_MAX_RETRY_ATTEMPTS)
		log.Printf("  MAX_RETRY_ATTEMPTS = %s (default)", maxRetryAttempts)
	} else {
		log.Printf("  MAX_RETRY_ATTEMPTS = %s (user-defined)", maxRetryAttempts)
	}
	
	initialRetryDelay := os.Getenv("INITIAL_RETRY_DELAY")
	if initialRetryDelay == "" {
		initialRetryDelay = fmt.Sprintf("%v", DEFAULT_INITIAL_RETRY_DELAY)
		log.Printf("  INITIAL_RETRY_DELAY = %s (default)", initialRetryDelay)
	} else {
		log.Printf("  INITIAL_RETRY_DELAY = %s (user-defined)", initialRetryDelay)
	}
	
	maxRetryDelay := os.Getenv("MAX_RETRY_DELAY")
	if maxRetryDelay == "" {
		maxRetryDelay = fmt.Sprintf("%v", DEFAULT_MAX_RETRY_DELAY)
		log.Printf("  MAX_RETRY_DELAY = %s (default)", maxRetryDelay)
	} else {
		log.Printf("  MAX_RETRY_DELAY = %s (user-defined)", maxRetryDelay)
	}
	
	sqsVisibility := os.Getenv("SQS_VISIBILITY_TIMEOUT")
	if sqsVisibility == "" {
		sqsVisibility = fmt.Sprintf("%d", DEFAULT_SQS_VISIBILITY)
		log.Printf("  SQS_VISIBILITY_TIMEOUT = %s (default)", sqsVisibility)
	} else {
		log.Printf("  SQS_VISIBILITY_TIMEOUT = %s (user-defined)", sqsVisibility)
	}
	
	sqsWaitTime := os.Getenv("SQS_WAIT_TIME")
	if sqsWaitTime == "" {
		sqsWaitTime = fmt.Sprintf("%d", DEFAULT_SQS_WAIT_TIME)
		log.Printf("  SQS_WAIT_TIME = %s (default)", sqsWaitTime)
	} else {
		log.Printf("  SQS_WAIT_TIME = %s (user-defined)", sqsWaitTime)
	}

	// Check if Cosmos DB is enabled
	if os.Getenv("COSMOS_ENDPOINT") != "" && os.Getenv("COSMOS_KEY") != "" &&
		os.Getenv("COSMOS_DATABASE") != "" && os.Getenv("COSMOS_CONTAINER") != "" {
		log.Println("Cosmos DB integration enabled:")
		log.Printf("  COSMOS_ENDPOINT = %s", os.Getenv("COSMOS_ENDPOINT"))
		log.Printf("  COSMOS_KEY = %s", os.Getenv("COSMOS_KEY"))
		log.Printf("  COSMOS_DATABASE = %s", os.Getenv("COSMOS_DATABASE"))
		log.Printf("  COSMOS_CONTAINER = %s", os.Getenv("COSMOS_CONTAINER"))
		
		cosmosBatchSize := os.Getenv("COSMOS_BATCH_SIZE")
		if cosmosBatchSize == "" {
			cosmosBatchSize = "100" // Default
			log.Printf("  COSMOS_BATCH_SIZE = %s (default)", cosmosBatchSize)
		} else {
			log.Printf("  COSMOS_BATCH_SIZE = %s (user-defined)", cosmosBatchSize)
		}
		
		azureRegion := os.Getenv("AZURE_REGION")
		if azureRegion == "" {
			azureRegion = "unknown" // Default
			log.Printf("  AZURE_REGION = %s (default)", azureRegion)
		} else {
			log.Printf("  AZURE_REGION = %s (user-defined)", azureRegion)
		}
	} else {
		log.Println("Cosmos DB integration disabled. Set COSMOS_ENDPOINT, COSMOS_KEY, COSMOS_DATABASE, and COSMOS_CONTAINER to enable")
	}

	log.Println("Environment configuration completed successfully")
	return nil
}

func (m *model) updateQueueSize() error {
	attribInput := &sqs.GetQueueAttributesInput{
		QueueUrl: aws.String(m.queueURL),
		AttributeNames: []*string{
			aws.String("ApproximateNumberOfMessages"),
		},
	}

	attribOutput, err := m.sqsClient.GetQueueAttributes(attribInput)
	if err != nil {
		if !isTransientError(err) {
			return fmt.Errorf("error getting queue attributes: %v", err)
		}
		return nil
	}

	if attribOutput.Attributes != nil {
		if count, ok := attribOutput.Attributes["ApproximateNumberOfMessages"]; ok {
			if queueSize, err := strconv.ParseInt(*count, 10, 64); err == nil {
				m.updateLock.Lock()
				m.queueSize = queueSize
				m.lastQueueCheck = time.Now()
				m.updateLock.Unlock()
				m.addLog("Queue size updated: %d messages", queueSize)
			}
		}
	}
	return nil
}

func (m *model) backgroundQueueSizeChecker() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-m.ctx.Done():
			return
		case <-ticker.C:
			if err := m.updateQueueSize(); err != nil {
				m.addLog("Error updating queue size: %v", err)
			}
		}
	}
}

func purgeQueue(ctx context.Context, m *model, sqsClient *sqs.SQS, queueURL string) error {
	m.addLog("Purging queue...")

	// For FIFO queues, we need to wait 60 seconds between purge operations
	if strings.HasSuffix(queueURL, ".fifo") {
		m.addLog("FIFO queue detected - purge operation may take longer")
	}

	_, err := sqsClient.PurgeQueueWithContext(ctx, &sqs.PurgeQueueInput{
		QueueUrl: aws.String(queueURL),
	})
	if err != nil {
		return fmt.Errorf("failed to purge queue: %v", err)
	}
	m.addLog("Queue purge request sent successfully")
	return nil
}

func clearQueue(ctx context.Context, m *model, sqsClient *sqs.SQS, queueURL string) {
	m.addLog("Starting queue clear operation...")
	emptyResponses := 0
	maxEmptyResponses := 3

	// Use multiple workers for queue clearing
	var wg sync.WaitGroup
	deletedCount := &sync.Map{}

	for i := 0; i < NUM_WORKERS; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			localDeleted := 0

			for {
				select {
				case <-ctx.Done():
					deletedCount.Store(workerID, localDeleted)
					return
				default:
					result, err := sqsClient.ReceiveMessage(&sqs.ReceiveMessageInput{
						QueueUrl:            aws.String(queueURL),
						MaxNumberOfMessages: aws.Int64(MAX_MESSAGES),
						WaitTimeSeconds:     aws.Int64(0),
						VisibilityTimeout:   aws.Int64(m.sqsVisibility),
					})
					if err != nil {
						if !isTransientError(err) {
							m.addLog("Worker %d error receiving messages during clear: %v", workerID, err)
						}
						continue
					}

					if len(result.Messages) == 0 {
						emptyResponses++
						if emptyResponses >= maxEmptyResponses {
							deletedCount.Store(workerID, localDeleted)
							return
						}
						time.Sleep(100 * time.Millisecond)
						continue
					}
					emptyResponses = 0

					var entries []*sqs.DeleteMessageBatchRequestEntry
					for i, msg := range result.Messages {
						entries = append(entries, &sqs.DeleteMessageBatchRequestEntry{
							Id:            aws.String(strconv.Itoa(i)),
							ReceiptHandle: msg.ReceiptHandle,
						})
					}

					if len(entries) > 0 {
						_, err = sqsClient.DeleteMessageBatch(&sqs.DeleteMessageBatchInput{
							QueueUrl: aws.String(queueURL),
							Entries:  entries,
						})
						if err != nil {
							if !isTransientError(err) {
								m.addLog("Worker %d error deleting messages during clear: %v", workerID, err)
							}
							continue
						}

						localDeleted += len(entries)
						if localDeleted%1000 == 0 {
							m.addLog("Worker %d has deleted %d messages", workerID, localDeleted)
						}
					}
				}
			}
		}(i)
	}

	wg.Wait()

	// Calculate total deleted messages
	totalDeleted := 0
	deletedCount.Range(func(_, value interface{}) bool {
		totalDeleted += value.(int)
		return true
	})

	m.addLog("Queue clear operation completed. Total messages deleted: %d", totalDeleted)
}

func clearQueueBefore(ctx context.Context, m *model, sqsClient *sqs.SQS, queueURL string, cutoff time.Time) {
	m.addLog("Starting queue clear operation for messages before %s...", cutoff.Format(time.RFC3339))
	emptyResponses := 0
	maxEmptyResponses := 3

	// Use multiple workers for clearing old messages
	var wg sync.WaitGroup
	deletedCount := &sync.Map{}

	for i := 0; i < NUM_WORKERS; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			localDeleted := 0

			for {
				select {
				case <-ctx.Done():
					deletedCount.Store(workerID, localDeleted)
					return
				default:
					result, err := sqsClient.ReceiveMessage(&sqs.ReceiveMessageInput{
						QueueUrl:            aws.String(queueURL),
						MaxNumberOfMessages: aws.Int64(MAX_MESSAGES),
						WaitTimeSeconds:     aws.Int64(0),
						VisibilityTimeout:   aws.Int64(m.sqsVisibility),
						AttributeNames: []*string{
							aws.String("All"),
						},
					})
					if err != nil {
						if !isTransientError(err) {
							m.addLog("Worker %d error receiving messages during clear: %v", workerID, err)
						}
						continue
					}

					if len(result.Messages) == 0 {
						emptyResponses++
						if emptyResponses >= maxEmptyResponses {
							deletedCount.Store(workerID, localDeleted)
							return
						}
						time.Sleep(100 * time.Millisecond)
						continue
					}
					emptyResponses = 0

					var entries []*sqs.DeleteMessageBatchRequestEntry
					for i, msg := range result.Messages {
						if sentTimestamp, ok := msg.Attributes["SentTimestamp"]; ok {
							timestamp, err := strconv.ParseInt(*sentTimestamp, 10, 64)
							if err != nil {
								continue
							}
							messageTime := time.Unix(0, timestamp*int64(time.Millisecond))

							if messageTime.Before(cutoff) {
								entries = append(entries, &sqs.DeleteMessageBatchRequestEntry{
									Id:            aws.String(strconv.Itoa(i)),
									ReceiptHandle: msg.ReceiptHandle,
								})
							}
						}
					}

					if len(entries) > 0 {
						_, err = sqsClient.DeleteMessageBatch(&sqs.DeleteMessageBatchInput{
							QueueUrl: aws.String(queueURL),
							Entries:  entries,
						})
						if err != nil {
							if !isTransientError(err) {
								m.addLog("Worker %d error deleting messages during clear: %v", workerID, err)
							}
							continue
						}

						localDeleted += len(entries)
						if localDeleted%1000 == 0 {
							m.addLog("Worker %d has deleted %d messages older than %s",
								workerID, localDeleted, cutoff.Format(time.RFC3339))
						}
					}
				}
			}
		}(i)
	}

	wg.Wait()

	// Calculate total deleted messages
	totalDeleted := 0
	deletedCount.Range(func(_, value interface{}) bool {
		totalDeleted += value.(int)
		return true
	})

	m.addLog("Queue clear operation completed. Total messages deleted: %d", totalDeleted)
}

func (m *model) addLog(format string, args ...interface{}) {
	logMsg := fmt.Sprintf(format, args...)
	timestamp := time.Now().Format("15:04:05.000")
	logLine := fmt.Sprintf("%s %s", timestamp, logMsg)

	m.updateLock.Lock()
	defer m.updateLock.Unlock()

	m.logs = append(m.logs, logLine)
	if len(m.logs) > m.maxLogs {
		m.logs = m.logs[1:]
	}
}

// Initialize Cosmos DB client
func initCosmosClient(ctx context.Context) (*azcosmos.Client, bool, error) {
	endpoint := os.Getenv("COSMOS_ENDPOINT")
	key := os.Getenv("COSMOS_KEY")

	if endpoint == "" || key == "" {
		return nil, false, nil
	}

	cred, err := azcosmos.NewKeyCredential(key)
	if err != nil {
		return nil, false, fmt.Errorf("failed to create key credential: %v", err)
	}

	// Using default client options
	clientOpts := &azcosmos.ClientOptions{}

	client, err := azcosmos.NewClientWithKey(endpoint, cred, clientOpts)
	if err != nil {
		return nil, false, fmt.Errorf("failed to create cosmos client: %v", err)
	}

	return client, true, nil
}

// Get a container client for Cosmos DB
func getCosmosContainer(client *azcosmos.Client, ctx context.Context) (*azcosmos.ContainerClient, error) {
	databaseName := os.Getenv("COSMOS_DATABASE")
	containerName := os.Getenv("COSMOS_CONTAINER")

	if databaseName == "" || containerName == "" {
		return nil, fmt.Errorf("COSMOS_DATABASE and COSMOS_CONTAINER must be set")
	}

	database, err := client.NewDatabase(databaseName)
	if err != nil {
		return nil, fmt.Errorf("failed to get database: %v", err)
	}

	container, err := database.NewContainer(containerName)
	if err != nil {
		return nil, fmt.Errorf("failed to get container: %v", err)
	}

	return container, nil
}

// addMessageToCosmosBatch adds a message to the batch for Cosmos DB
func (m *model) addMessageToCosmosBatch(msg Message) {
	if !m.cosmosEnabled {
		return
	}

	// Add unique ID and timestamp for Cosmos if not present
	if msg.Id == "" {
		msg.Id = fmt.Sprintf("%s-%s-%d", msg.ContainerID, msg.VMName, time.Now().UnixNano())
	}

	if msg.EventTime == 0 {
		msg.EventTime = time.Now().UnixNano()
	}

	// Set the type and region for partitioning
	msg.Type = "event"

	// Use Azure region if available, otherwise default to "unknown"
	if msg.Region == "" {
		msg.Region = os.Getenv("AZURE_REGION")
		if msg.Region == "" {
			msg.Region = "unknown"
		}
	}

	m.cosmosMessagesLock.Lock()
	defer m.cosmosMessagesLock.Unlock()

	m.cosmosMessages = append(m.cosmosMessages, msg)

	// If batch size threshold is reached, trigger immediate write
	if len(m.cosmosMessages) >= m.cosmosBatchSize {
		// Reset timer
		if m.cosmosWriteTimer != nil {
			m.cosmosWriteTimer.Stop()
		}

		// Make a copy of the batch
		batchToWrite := make([]Message, len(m.cosmosMessages))
		copy(batchToWrite, m.cosmosMessages)
		m.cosmosMessages = nil

		// Write the batch asynchronously
		go m.writeCosmosBatch(batchToWrite)
	} else if m.cosmosWriteTimer == nil && len(m.cosmosMessages) > 0 {
		// Start timer for a delayed write if not already running
		m.cosmosWriteTimer = time.AfterFunc(2*time.Second, func() {
			m.flushCosmosBatch()
		})
	}
}

// flushCosmosBatch writes any pending messages to Cosmos DB
func (m *model) flushCosmosBatch() {
	m.cosmosMessagesLock.Lock()

	if len(m.cosmosMessages) == 0 {
		m.cosmosMessagesLock.Unlock()
		return
	}

	// Make a copy of the batch
	batchToWrite := make([]Message, len(m.cosmosMessages))
	copy(batchToWrite, m.cosmosMessages)
	m.cosmosMessages = nil

	// Reset timer
	if m.cosmosWriteTimer != nil {
		m.cosmosWriteTimer.Stop()
		m.cosmosWriteTimer = nil
	}

	m.cosmosMessagesLock.Unlock()

	// Write the batch
	go m.writeCosmosBatch(batchToWrite)
}

// writeCosmosBatch writes a batch of messages to Cosmos DB
func (m *model) writeCosmosBatch(messages []Message) {
	if !m.cosmosEnabled || m.cosmosContainer == nil || len(messages) == 0 {
		return
	}

	startTime := time.Now()
	m.addLog("Writing batch of %d messages to Cosmos DB", len(messages))

	var successCount, errorCount int
	var wg sync.WaitGroup
	var mutex sync.Mutex
	// Use a semaphore to limit concurrent writes
	semaphore := make(chan struct{}, 10)

	for _, msg := range messages {
		wg.Add(1)
		semaphore <- struct{}{} // Acquire semaphore slot

		go func(message Message) {
			defer wg.Done()
			defer func() { <-semaphore }() // Release semaphore slot

			// Convert message to JSON
			jsonData, err := json.Marshal(message)
			if err != nil {
				mutex.Lock()
				errorCount++
				mutex.Unlock()
				m.addLog("Error marshaling message: %v", err)
				return
			}

			// Create the partition key
			partitionKey := azcosmos.NewPartitionKeyString(message.Region)

			// Create the item
			_, err = m.cosmosContainer.CreateItem(m.ctx, partitionKey, jsonData, nil)
			if err != nil {
				mutex.Lock()
				errorCount++
				mutex.Unlock()
				m.addLog("Error writing to Cosmos DB: %v", err)
				return
			}

			mutex.Lock()
			successCount++
			mutex.Unlock()
		}(msg)
	}

	wg.Wait()

	duration := time.Since(startTime)
	m.addLog("Cosmos DB write complete: %d successful, %d failed in %v",
		successCount, errorCount, duration)
}

// Helper functions for debugging

// getWorkingDirectory returns the current working directory
func getWorkingDirectory() string {
	dir, err := os.Getwd()
	if err != nil {
		return fmt.Sprintf("Error getting working directory: %v", err)
	}
	return dir
}

// runningInContainer tries to detect if we're running in a container
func runningInContainer() bool {
	// Check for container-specific files
	_, err1 := os.Stat("/.dockerenv")
	_, err2 := os.Stat("/run/.containerenv")

	// Check for cgroup info that might indicate container
	cgroupContent, err := os.ReadFile("/proc/1/cgroup")
	if err == nil {
		if strings.Contains(string(cgroupContent), "docker") ||
			strings.Contains(string(cgroupContent), "kubepods") {
			return true
		}
	}

	return err1 == nil || err2 == nil
}

func (m *model) incrementMessageCount(count int) {
	m.messageCountLock.Lock()
	defer m.messageCountLock.Unlock()
	m.messageCount += int64(count)

	// Log message count every 5 seconds
	if time.Since(m.lastCountLog) >= 5*time.Second {
		log.Printf("Messages pulled in last 5 seconds: %d (Total: %d)", m.messageCount, m.totalProcessed)
		m.messageCount = 0
		m.lastCountLog = time.Now()
	}
}