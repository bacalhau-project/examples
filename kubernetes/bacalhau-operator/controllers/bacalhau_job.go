/*
Copyright 2023 - 2025.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

	http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/
package controllers

import (
	jobv1 "bacalhau-operator/api/v1"
	"bacalhau-operator/utils"
	"context"
	"encoding/json"
	"fmt"

	bacalhau_models "github.com/bacalhau-project/bacalhau/pkg/models"
)

func CreateJobSpec(ctx context.Context, jobStruct *jobv1.BacalhauJob) (*bacalhau_models.Job, error) {
	// Parse the raw spec into a Bacalhau job
	job := &bacalhau_models.Job{}
	if err := json.Unmarshal(jobStruct.Spec.Raw.Raw, job); err != nil {
		return nil, fmt.Errorf("failed to parse job spec: %w", err)
	}

	// Set operator-managed fields
	if job.ID == "" {
		job.ID = utils.GenerateID()
	}
	if job.Name == "" {
		job.Name = jobStruct.Name + "-" + utils.RandomString(6)
	}

	return job, nil
}
