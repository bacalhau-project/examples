package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/sqs"
	"github.com/charmbracelet/bubbles/table"
	"github.com/joho/godotenv"

	"github.com/aws/aws-sdk-go/aws/session"
	tea "github.com/charmbracelet/bubbletea"
)

const (
	// Increased polling frequency and batch sizes
	POLL_INTERVAL = 100 * time.Millisecond // Reduced from 500ms
	MAX_MESSAGES  = 10                     // Maximum allowed by SQS
	WS_BATCH_SIZE = 100                    // Increased from 50
	NUM_WORKERS   = 5                      // Number of concurrent polling workers
	BUFFER_SIZE   = 1000                   // Channel buffer size for message processing
)

type Message struct {
	VMName      string `json:"vm_name"`
	ContainerID string `json:"container_id"`
	IconName    string `json:"icon_name"`
	Color       string `json:"color"`
	Timestamp   string `json:"timestamp"`
}

type model struct {
	table            table.Model
	lastPoll         time.Time
	queueURL         string
	queueSize        int64
	totalProcessed   uint64
	messages         []Message
	hub              *Hub
	showConfirmClear bool
	sqsClient        *sqs.SQS
	ctx              context.Context
	cancel           context.CancelFunc
	lastQueueCheck   time.Time
	logs             []string
	maxLogs          int
	messageChan      chan Message
	updateLock       sync.Mutex
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
			"  Region: %s\n\n",
		m.queueSize,
		m.totalProcessed,
		m.lastPoll.Format("15:04:05.000"),
		m.queueURL,
		os.Getenv("AWS_REGION"),
	))

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
	s.WriteString("───���──────────────────────────────────────────\n")

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

	for {
		select {
		case <-m.ctx.Done():
			m.addLog("Worker %d shutting down", workerID)
			return
		default:
			messages, err := receiveMessages(m.ctx, m.sqsClient, m.queueURL)
			if err != nil {
				if !isTransientError(err) {
					m.addLog("Worker %d error receiving messages: %v", workerID, err)
				}
				time.Sleep(POLL_INTERVAL)
				continue
			}

			if len(messages) > 0 {
				m.updateLock.Lock()
				m.lastPoll = time.Now()
				m.totalProcessed += uint64(len(messages))
				m.messages = messages // Update the messages slice for display
				m.updateLock.Unlock()
				m.addLog("Worker %d received %d messages", workerID, len(messages))

				// Process messages in batches for efficient updates
				for _, msg := range messages {
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

func receiveMessages(ctx context.Context, sqsClient *sqs.SQS, queueURL string) ([]Message, error) {
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	default:
	}

	// Check if it's a FIFO queue
	isFifoQueue := strings.HasSuffix(queueURL, ".fifo")

	input := &sqs.ReceiveMessageInput{
		QueueUrl:            aws.String(queueURL),
		MaxNumberOfMessages: aws.Int64(MAX_MESSAGES),
		WaitTimeSeconds:     aws.Int64(0),
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

	result, err := sqsClient.ReceiveMessage(input)
	if err != nil {
		if isTransientError(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to receive messages: %v", err)
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
		_, err := sqsClient.DeleteMessageBatch(deleteInput)
		if err != nil {
			log.Printf("Error batch deleting messages: %v", err)
		}
	}

	return messages, nil
}

func initialModel(ctx context.Context, queueURL string, sqsClient *sqs.SQS, hub *Hub) model {
	// Validate queue exists and permissions
	_, err := sqsClient.GetQueueAttributes(&sqs.GetQueueAttributesInput{
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
		table:          t,
		queueURL:       queueURL,
		hub:            hub,
		lastPoll:       time.Now(),
		sqsClient:      sqsClient,
		ctx:            modelCtx,
		cancel:         cancel,
		lastQueueCheck: time.Time{},
		maxLogs:        1000,
		logs:           make([]string, 0, 1000),
		messageChan:    make(chan Message, BUFFER_SIZE),
	}

	// Add initial logs
	m.addLog("Starting SQS Queue Monitor...")
	m.addLog("Queue URL: %s", queueURL)
	m.addLog("Region: %s", os.Getenv("AWS_REGION"))
	if strings.HasSuffix(queueURL, ".fifo") {
		m.addLog("FIFO queue detected - using FIFO-specific handling")
	}

	// Start multiple polling workers
	for i := 0; i < NUM_WORKERS; i++ {
		workerID := i
		go m.startMessageWorker(workerID)
	}

	// Start background queue size checker
	go m.backgroundQueueSizeChecker()

	return m
}

func main() {
	if err := loadEnvConfig(); err != nil {
		log.Fatalf("\nEnvironment configuration error: %v\n", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM, syscall.SIGQUIT)

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
		serveWs(hub, w, r)
	})
	http.Handle("/", http.FileServer(http.Dir("static")))

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

	p := tea.NewProgram(&m, tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		log.Fatalf("Error running program: %v\n", err)
	}
}

func loadEnvConfig() error {
	envFile := os.Getenv("ENV_FILE")
	var envSource string

	if envFile != "" {
		if _, err := os.Stat(envFile); err != nil {
			return fmt.Errorf("specified ENV_FILE '%s' does not exist or is not readable: %v", envFile, err)
		}
		if err := godotenv.Load(envFile); err != nil {
			return fmt.Errorf("error loading specified env file '%s': %v", envFile, err)
		}
		envSource = fmt.Sprintf("Environment loaded from specified ENV_FILE: %s", envFile)
	} else {
		if _, err := os.Stat(".env"); err != nil {
			return fmt.Errorf("no ENV_FILE specified and no .env file found in current directory")
		}
		if err := godotenv.Load(); err != nil {
			return fmt.Errorf("error loading default .env file: %v", err)
		}
		envSource = "Environment loaded from default .env file in current directory"
	}

	log.SetOutput(io.Discard)
	log.SetFlags(0)

	required := []string{"SQS_QUEUE_URL", "AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"}
	var missing []string

	for _, env := range required {
		if os.Getenv(env) == "" {
			missing = append(missing, env)
		}
	}

	if len(missing) > 0 {
		return fmt.Errorf("\nMissing required environment variables in %s:\n%s\n\nPlease ensure all required variables are set in your environment file",
			strings.TrimPrefix(envSource, "Environment loaded from "),
			strings.Join(missing, "\n"))
	}

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
						VisibilityTimeout:   aws.Int64(30),
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
						VisibilityTimeout:   aws.Int64(30),
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
