package main

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
)

func main() {
	// Get files to download from FILE env variable
	u, urlSet := os.LookupEnv("URL")
	if !urlSet {
		fmt.Printf("URL env variable is not set. Please do so with the -e URL=<URL> flag.\n")
		return
	}

	uu, err := url.Parse(u)
	if err != nil {
		fmt.Printf("URL is not valid. %s", err)
	}

	// Create the file
	out, err := os.Create("test")
	if err != nil {
		fmt.Printf("Error creating file. %s", err)
		return
	}
	defer out.Close()

	// Get the data
	resp, err := http.Get(uu.String())

	if err != nil {
		fmt.Printf("Error while downloading file: %s ", err)
		return
	}
	defer resp.Body.Close()

	// Check server response
	if resp.StatusCode != http.StatusOK {
		fmt.Printf("Bad status code: %s", resp.Status)
	}

	// Writer the body to file
	_, err = io.Copy(out, resp.Body)
	if err != nil {
		fmt.Printf("Error while downloading file: %s ", err)
		return
	}

	return
}
