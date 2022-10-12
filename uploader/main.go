package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	cp "github.com/otiai10/copy"
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

	// Putting the objects in order so all Dirs come before all Files
	allObjects = append(allObjects, allDirs...)
	allObjects = append(allObjects, allFiles...)

	for _, oo := range allObjects[1:] {
		// See if oo still exists (its parent could have been moved)
		_, err := os.Stat(oo)
		if err != nil {
			fmt.Printf("Error stating object %v:", err)
			continue
		}
		dstPath := strings.Replace(oo, inputPath, outputPath, 1)
		fmt.Printf("Copying %s to %s\n", oo, dstPath)
		err = cp.Copy(oo, dstPath)
		if err != nil {
			fmt.Printf("Error moving %s to %s: %v", oo, dstPath, err)
			return
		}
	}

	fmt.Printf("Done copying all objects. Final /outputs contents:\n")
	err = filepath.WalkDir(outputPath,
		func(path string, d os.DirEntry, err error) error {
			fmt.Println(path)
			return nil
		})
	if err != nil {
		fmt.Printf("Error walking output path: %v", err)
	}
	return
}
