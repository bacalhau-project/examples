package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/spf13/afero"
)

func main() {
	inputPath := os.Getenv("INPUT_PATH")
	if inputPath == "" {
		fmt.Printf("INPUT_PATH is not set, using '/inputs'\n")
		inputPath = "/inputs"
	}

	outputPath := os.Getenv("OUTPUT_PATH")
	if outputPath == "" {
		fmt.Printf("OUTPUT_PATH is not set, using '/outputs'\n")
		outputPath = "/outputs"
	}
	fs := afero.NewOsFs()
	allObjects := []string{}
	allDirs := []string{}
	allFiles := []string{}

	walker := func(path string, d os.DirEntry, err error) error {
		if path == inputPath {
			return nil
		}
		if d.IsDir() {
			allDirs = append(allDirs, path)
		} else {
			allFiles = append(allFiles, path)
		}

		return nil
	}

	err := filepath.WalkDir(inputPath, walker)
	if err != nil {
		fmt.Printf("Error walking input path: %v", err)
		return
	}

	allObjects = append(allObjects, allDirs...)
	allObjects = append(allObjects, allFiles...)

	remainingObjects := []string{}
	for _, oo := range allObjects {
		if f, err := os.Stat(oo); errors.Is(err, os.ErrNotExist) {
			continue
		} else if f.IsDir() {
			fmt.Printf("Moving %s to %s\n", oo, outputPath)
			err = fs.Rename(oo, strings.Replace(oo, inputPath, outputPath, 1))
			if err != nil {
				fmt.Printf("Error moving %s to %s: %v", oo, outputPath, err)
				return
			}
		} else {
			remainingObjects = append(remainingObjects, oo)
		}
	}

	for _, oo := range remainingObjects {
		if _, err := os.Stat(oo); errors.Is(err, os.ErrNotExist) {
			continue
		} else {
			fmt.Printf("Moving %s to %s\n", oo, outputPath)
			err = fs.Rename(oo, strings.Replace(oo, inputPath, outputPath, 1))
			if err != nil {
				fmt.Printf("Error moving %s to %s: %v", oo, outputPath, err)
				return
			}
		}
	}

	return
}
