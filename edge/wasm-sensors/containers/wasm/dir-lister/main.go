package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	// Define command line flags
	dir := flag.String("dir", "/app", "Directory to list contents of")
	flag.Parse()

	// List directory contents
	entries, err := os.ReadDir(*dir)
	if err != nil {
		fmt.Printf("Error reading directory: %v\n", err)
		os.Exit(1)
	}

	for i, entry := range entries {
		info, err := entry.Info()
		if err != nil {
			continue
		}

		// Format file size
		var sizeStr string
		if info.IsDir() {
			sizeStr = "<DIR>"
		} else {
			sizeStr = fmt.Sprintf("%d bytes", info.Size())
		}

		// Format permissions
		perms := info.Mode().String()

		if i > 0 {
			fmt.Print(" | ")
		}
		fmt.Printf("%s %s %s %s", perms, info.ModTime().Format("2006-01-02 15:04:05"), sizeStr, entry.Name())
	}
	fmt.Println()
} 