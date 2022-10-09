package main

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path"
	"path/filepath"
	"strings"

	"github.com/filecoin-project/bacalhau/pkg/config"
	"github.com/go-resty/resty/v2"
)

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Get files to download from FILE env variable
	u, urlSet := os.LookupEnv("URL")
	if !urlSet {
		fmt.Printf("URL env variable is not set. Please do so with the -e URL=<URL> flag.\n")
		return
	}
	uu, err := IsURLSupported(u)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing the URL (%s): %+v\n", u, err)
		return
	}

	outputPath := os.Getenv("OUTPUT_PATH")
	if outputPath == "" {
		fmt.Fprintf(os.Stdout, "OUTPUT_PATH env variable is not set. Using /outputs as the download directory in the container.\n")
		outputPath = "/outputs"
	}

	c := resty.New()
	c.SetTimeout(config.GetDownloadURLRequestTimeout())
	c.SetOutputDirectory(outputPath)
	c.SetDoNotParseResponse(true) // We want to stream the response to disk directly

	req := c.R().SetContext(ctx)
	req = req.SetContext(ctx)
	r, err := req.Head(uu.String())
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to get headers from url (%s): %s", uu.String(), err)
		return
	}

	r, err = req.Get(uu.String())
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to get headers from url (%s): %s", uu.String(), err)
		return
	}

	if r.StatusCode() != http.StatusOK {
		fmt.Fprintf(os.Stderr, "non-200 response from URL (%s): %s", uu.String(), r.Status())
		return
	}

	// Create a new file based on the URL
	fmt.Fprintf(os.Stdout, "Starting download from %s to %s\n", uu.String(), path.Join(outputPath, uu.Path))
	fileName := filepath.Base(path.Base(uu.Path))
	filePath := filepath.Join(outputPath, fileName)
	w, err := os.Create(filePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, fmt.Sprintf("failed to create file %s: %s", filePath, err))
		return
	}

	// stream the body to the client without fully loading it into memory
	n, err := io.Copy(w, r.RawBody())
	if err != nil {
		fmt.Fprintf(os.Stderr, fmt.Sprintf("failed to write to file %s: %s", filePath, err))
		return
	}

	if n == 0 {
		fmt.Fprintf(os.Stderr, fmt.Sprintf("no bytes written to file %s", filePath))
		return
	}

	fmt.Fprintf(os.Stdout, "Downloaded %d bytes to %s\n", n, filePath)

	// Closing everything
	err = w.Sync()
	if err != nil {
		fmt.Fprintf(os.Stderr, fmt.Sprintf("failed to sync file %s: %s", filePath, err))
		return
	}
	r.RawBody().Close()
	w.Close()

	return
}

func IsURLSupported(rawURL string) (*url.URL, error) {
	rawURL = strings.Trim(rawURL, " '\"")
	u, err := url.Parse(rawURL)
	if err != nil {
		return nil, fmt.Errorf("invalid URL: %s", err)
	}
	if (u.Scheme != "http") && (u.Scheme != "https") {
		return nil, fmt.Errorf("URLs must begin with 'http' or 'https'. The submitted one began with %s", u.Scheme)
	}

	basePath := path.Base(u.Path)

	// Need to check for both because a bare host
	// Like http://localhost/ gets converted to "." by path.Base
	if basePath == "" || u.Path == "" {
		return nil, fmt.Errorf("URL must end with a file name")
	}

	return u, nil
}
