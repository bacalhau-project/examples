package main

import (
	"fmt"
	"os"

	"github.com/bacalhau-project/many-node-runner/cmd"
)

func main() {
	if err := cmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
