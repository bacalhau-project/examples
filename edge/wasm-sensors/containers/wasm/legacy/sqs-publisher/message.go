package main

import (
	"math/rand"
	"os"
	"time"
)

// Initialize random seed
func init() {
	rand.Seed(time.Now().UnixNano())
}

var (
	emojis = []string{
		"🚀", "💻", "🖥️", "💾", "📡", "🌐", "🔌", "⚡", "🔋", "💡",
		"🛠️", "🔧", "⚙️", "🔨", "📱", "📲", "🖱️", "⌨️", "🖨️", "🧮",
		"🎮", "🎲", "🎯", "🎪", "🎭", "🎨", "🧩", "🎸", "🎹", "🎺",
	}
)

// Message structure for events
type Message struct {
	JobID       string `json:"job_id"`
	ExecutionID string `json:"execution_id"`
	IconName    string `json:"icon_name"`
	Timestamp   string `json:"timestamp"`
	Color       string `json:"color"`
	Sequence    int    `json:"sequence"`
}

// MessageGenerator is the standard implementation of Generator
type MessageGenerator struct {
	Emojis      []string
	jobID       string
	executionID string
	counter     int
}

// NewMessageGenerator creates a new MessageGenerator
func NewMessageGenerator() *MessageGenerator {
	return &MessageGenerator{
		jobID:       os.Getenv("BACALHAU_JOB_ID"),
		executionID: os.Getenv("BACALHAU_EXECUTION_ID"),
	}
}

// getRandomIcon selects an emoji from the list (random or fixed based on randomOff)
func (g *MessageGenerator) getRandomIcon(randomOff bool) string {
	if randomOff {
		// Always return the first emoji when randomness is off
		return emojis[0]
	}

	// Use true random selection when randomOff is false
	return emojis[rand.Intn(len(emojis))]
}

// GetMessage creates a new message
func (g *MessageGenerator) GetMessage(config RuntimeConfig) Message {
	g.counter++
	return Message{
		JobID:       g.jobID,
		ExecutionID: g.executionID,
		IconName:    g.getRandomIcon(config.RandomOff),
		Timestamp:   time.Now().UTC().Format(time.RFC3339),
		Color:       config.Color,
		Sequence:    g.counter,
	}
}
