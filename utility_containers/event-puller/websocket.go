package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gorilla/websocket"
)

var (
	// Logger for WebSocket operations
	wsLogger *log.Logger
)

func init() {
	// Clear the debug.log file on startup
	os.Truncate("debug.log", 0)

	// Open the log file in append mode
	logFile, err := os.OpenFile("debug.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatal("Failed to open log file:", err)
	}

	// Create a new logger that writes to the file
	wsLogger = log.New(logFile, "", log.LstdFlags|log.Lmicroseconds)
}

const (
	// Time allowed to write a message to the peer
	writeWait = 10 * time.Second

	// Time allowed to read the next pong message from the peer
	pongWait = 60 * time.Second

	// Send pings to peer with this period (must be less than pongWait)
	pingPeriod = (pongWait * 9) / 10

	// Maximum message size allowed from peer
	maxMessageSize = 4096

	// Buffer size for client send channel
	clientBufferSize = 1024
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins for demo
	},
}

// Message from client
type ClientMessage struct {
	Action string `json:"action"`
}

func (c *Client) readPump(m *model) {
	defer func() {
		wsLogger.Printf("WebSocket readPump defer: Unregistering client and closing connection")
		wsLogger.Printf("WebSocket readPump state: LocalAddr=%s, RemoteAddr=%s",
			c.conn.LocalAddr().String(), c.conn.RemoteAddr().String())
		c.hub.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadLimit(maxMessageSize)
	c.conn.SetReadDeadline(time.Now().Add(pongWait))
	c.conn.SetPongHandler(func(string) error {
		wsLogger.Printf("WebSocket pong received, resetting read deadline")
		wsLogger.Printf("WebSocket pong state: LocalAddr=%s, RemoteAddr=%s",
			c.conn.LocalAddr().String(), c.conn.RemoteAddr().String())
		c.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				wsLogger.Printf("WebSocket read error: %v", err)
				wsLogger.Printf("WebSocket close code: %s", c.conn.RemoteAddr().String())
				wsLogger.Printf("WebSocket state: %+v", c.conn)
				wsLogger.Printf("WebSocket error state: LocalAddr=%s, RemoteAddr=%s",
					c.conn.LocalAddr().String(), c.conn.RemoteAddr().String())
			} else {
				wsLogger.Printf("WebSocket normal closure: %v", err)
			}
			break
		}

		wsLogger.Printf("WebSocket received message: %s", string(message))
		wsLogger.Printf("WebSocket message state: LocalAddr=%s, RemoteAddr=%s",
			c.conn.LocalAddr().String(), c.conn.RemoteAddr().String())

		// Parse the command
		var cmd struct {
			Command   string `json:"command"`
			BatchSize int    `json:"batch_size,omitempty"`
		}
		if err := json.Unmarshal(message, &cmd); err != nil {
			wsLogger.Printf("Error parsing WebSocket command: %v", err)
			continue
		}

		// Handle the command
		if err := m.handleWebSocketCommand(cmd); err != nil {
			wsLogger.Printf("Error handling WebSocket command: %v", err)
			// Send error response back to client
			response := struct {
				Error string `json:"error"`
			}{
				Error: err.Error(),
			}
			if responseData, err := json.Marshal(response); err == nil {
				c.send <- responseData
			}
		}
	}
}

func (c *Client) writePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		wsLogger.Printf("WebSocket writePump defer: Stopping ticker and closing connection")
		ticker.Stop()
		c.hub.unregister <- c
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			if !ok {
				wsLogger.Printf("WebSocket send channel closed, sending close message")
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			w, err := c.conn.NextWriter(websocket.TextMessage)
			if err != nil {
				wsLogger.Printf("WebSocket write error: %v", err)
				return
			}
			w.Write(message)

			// Add queued messages to the current websocket message
			n := len(c.send)
			wsLogger.Printf("WebSocket queued messages: %d", n)
			for i := 0; i < n; i++ {
				w.Write([]byte{'\n'})
				w.Write(<-c.send)
			}

			if err := w.Close(); err != nil {
				wsLogger.Printf("WebSocket writer close error: %v", err)
				return
			}
		case <-ticker.C:
			wsLogger.Printf("WebSocket sending ping")
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				wsLogger.Printf("WebSocket ping error: %v", err)
				return
			}
		}
	}
}

func serveWs(hub *Hub, w http.ResponseWriter, r *http.Request, m *model) {
	wsLogger.Printf("WebSocket connection request from %s", r.RemoteAddr)
	wsLogger.Printf("WebSocket headers: %+v", r.Header)
	wsLogger.Printf("WebSocket protocol: %s", r.Header.Get("Sec-WebSocket-Protocol"))
	wsLogger.Printf("WebSocket version: %s", r.Header.Get("Sec-WebSocket-Version"))

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		wsLogger.Printf("Error upgrading connection: %v", err)
		return
	}

	client := &Client{
		hub:  hub,
		conn: conn,
		send: make(chan []byte, clientBufferSize),
	}

	wsLogger.Printf("WebSocket connection established for %s", r.RemoteAddr)
	wsLogger.Printf("WebSocket connection details: LocalAddr=%s, RemoteAddr=%s",
		conn.LocalAddr().String(), conn.RemoteAddr().String())

	// Set larger buffer sizes and timeouts
	conn.SetReadLimit(maxMessageSize)
	conn.SetReadDeadline(time.Now().Add(pongWait))
	conn.SetPongHandler(func(string) error {
		wsLogger.Printf("WebSocket pong received from %s", r.RemoteAddr)
		conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	// Register the client before starting the pumps
	wsLogger.Printf("Registering WebSocket client for %s", r.RemoteAddr)
	client.hub.register <- client

	// Start the pumps in separate goroutines
	wsLogger.Printf("Starting WebSocket pumps for %s", r.RemoteAddr)
	go client.writePump()
	go client.readPump(m)
}
