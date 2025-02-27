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
	"fmt"
	engine_docker "github.com/bacalhau-project/bacalhau/pkg/executor/docker/models"
	bacalhau_models "github.com/bacalhau-project/bacalhau/pkg/models"
	"k8s.io/apimachinery/pkg/selection"
)

func CreateJobSpec(ctx context.Context, jobStruct *jobv1.BacalhauJob) (*bacalhau_models.Job, error) {
	parameters := []string{}
	workingDirectory := ""
	environmentVariables := []string{}

	engineSpec, err := engine_docker.NewDockerEngineBuilder(jobStruct.Spec.Image).
		WithParameters(parameters...).
		WithWorkingDirectory(workingDirectory).
		WithEntrypoint(jobStruct.Spec.Entrypoint...).
		WithEnvironmentVariables(environmentVariables...).
		Build()

	if err != nil {
		return nil, fmt.Errorf("failed to create engine spec: %w", err)
	}

	name := jobStruct.Name + "-" + utils.RandomString(6)

	job := &bacalhau_models.Job{
		ID:          utils.GenerateID(),
		Name:        name,
		Type:        parseJobType(jobStruct),
		Count:       jobStruct.Spec.Count,
		Constraints: parseContraints(jobStruct),
		Tasks: []*bacalhau_models.Task{
			{
				Name:   name,
				Engine: engineSpec,
				Publisher: &bacalhau_models.SpecConfig{
					Type: bacalhau_models.PublisherLocal,
				},
				//ResourcesConfig: &bacalhau_models.ResourcesConfig{
				//	CPU:    strconv.Itoa(1),
				//	Memory: strconv.Itoa(128),
				//	GPU:    strconv.Itoa(0),
				//	Disk:   strconv.Itoa(50),
				//},
			},
		},
	}

	return job, nil
}

func parseContraints(jobStruct *jobv1.BacalhauJob) []*bacalhau_models.LabelSelectorRequirement {
	requirements := make([]*bacalhau_models.LabelSelectorRequirement, 0)

	for _, constraint := range jobStruct.Spec.Constraints {
		requirement := &bacalhau_models.LabelSelectorRequirement{
			Key:      constraint.Key,
			Operator: selection.Operator(constraint.Operator),
			Values:   constraint.Values,
		}
		requirements = append(requirements, requirement)
	}
	return requirements
}

func parseJobType(jobStruct *jobv1.BacalhauJob) string {
	jobType := jobStruct.Spec.Type
	switch jobType {
	case "batch", "ops":
		return jobType
	}
	return "batch"
}
