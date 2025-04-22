package pkg

import (
	"os"
	"time"
)

// Message structure for events
type Message struct {
	JobID             string `json:"job_id"`
	ExecutionID       string `json:"execution_id"`
	IconName          string `json:"icon_name"`
	Timestamp         string `json:"timestamp"`
	Color             string `json:"color"`
	Sequence          int    `json:"sequence"`
	Region            string `json:"region"`
	JobSubmissionTime int64  `json:"job_submission_time"`
	Hostname          string `json:"hostname"`
}

// MessageGenerator is the standard implementation of Generator
type MessageGenerator struct {
	jobID       string
	executionID string
	hostname    string
	counter     int
}

// NewMessageGenerator creates a new MessageGenerator
func NewMessageGenerator() *MessageGenerator {
	return &MessageGenerator{
		jobID:       os.Getenv("BACALHAU_JOB_ID"),
		executionID: os.Getenv("BACALHAU_EXECUTION_ID"),
		hostname:    os.Getenv("HOSTNAME"),
	}
}

// GetMessage creates a new message
func (g *MessageGenerator) GetMessage(config RuntimeConfig) Message {
	g.counter++
	return Message{
		JobID:             g.jobID,
		ExecutionID:       g.executionID,
		IconName:          supportedEmojis[config.EmojiIdx],
		Timestamp:         time.Now().UTC().Format(time.RFC3339),
		Color:             config.Color,
		Sequence:          g.counter,
		Region:            config.Region,
		JobSubmissionTime: config.SubmissionTime.Unix(),
		Hostname:          g.hostname,
	}
}
