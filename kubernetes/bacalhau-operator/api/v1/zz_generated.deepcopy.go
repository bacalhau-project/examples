//go:build !ignore_autogenerated

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

// Code generated by controller-gen. DO NOT EDIT.

package v1

import (
	"k8s.io/apimachinery/pkg/runtime"
)

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *BacalhauJob) DeepCopyInto(out *BacalhauJob) {
	*out = *in
	out.TypeMeta = in.TypeMeta
	in.ObjectMeta.DeepCopyInto(&out.ObjectMeta)
	in.Spec.DeepCopyInto(&out.Spec)
	in.Status.DeepCopyInto(&out.Status)
	if in.Executions != nil {
		in, out := &in.Executions, &out.Executions
		*out = make([]ExecutionHistory, len(*in))
		for i := range *in {
			(*in)[i].DeepCopyInto(&(*out)[i])
		}
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new BacalhauJob.
func (in *BacalhauJob) DeepCopy() *BacalhauJob {
	if in == nil {
		return nil
	}
	out := new(BacalhauJob)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyObject is an autogenerated deepcopy function, copying the receiver, creating a new runtime.Object.
func (in *BacalhauJob) DeepCopyObject() runtime.Object {
	if c := in.DeepCopy(); c != nil {
		return c
	}
	return nil
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *BacalhauJobConstraint) DeepCopyInto(out *BacalhauJobConstraint) {
	*out = *in
	if in.Values != nil {
		in, out := &in.Values, &out.Values
		*out = make([]string, len(*in))
		copy(*out, *in)
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new BacalhauJobConstraint.
func (in *BacalhauJobConstraint) DeepCopy() *BacalhauJobConstraint {
	if in == nil {
		return nil
	}
	out := new(BacalhauJobConstraint)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *BacalhauJobList) DeepCopyInto(out *BacalhauJobList) {
	*out = *in
	out.TypeMeta = in.TypeMeta
	in.ListMeta.DeepCopyInto(&out.ListMeta)
	if in.Items != nil {
		in, out := &in.Items, &out.Items
		*out = make([]BacalhauJob, len(*in))
		for i := range *in {
			(*in)[i].DeepCopyInto(&(*out)[i])
		}
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new BacalhauJobList.
func (in *BacalhauJobList) DeepCopy() *BacalhauJobList {
	if in == nil {
		return nil
	}
	out := new(BacalhauJobList)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyObject is an autogenerated deepcopy function, copying the receiver, creating a new runtime.Object.
func (in *BacalhauJobList) DeepCopyObject() runtime.Object {
	if c := in.DeepCopy(); c != nil {
		return c
	}
	return nil
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *BacalhauJobSpec) DeepCopyInto(out *BacalhauJobSpec) {
	*out = *in
	in.Raw.DeepCopyInto(&out.Raw)
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new BacalhauJobSpec.
func (in *BacalhauJobSpec) DeepCopy() *BacalhauJobSpec {
	if in == nil {
		return nil
	}
	out := new(BacalhauJobSpec)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *BacalhauJobStatus) DeepCopyInto(out *BacalhauJobStatus) {
	*out = *in
	if in.LastPolled != nil {
		in, out := &in.LastPolled, &out.LastPolled
		*out = new(string)
		**out = **in
	}
	if in.Executions != nil {
		in, out := &in.Executions, &out.Executions
		*out = make([]ExecutionHistory, len(*in))
		for i := range *in {
			(*in)[i].DeepCopyInto(&(*out)[i])
		}
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new BacalhauJobStatus.
func (in *BacalhauJobStatus) DeepCopy() *BacalhauJobStatus {
	if in == nil {
		return nil
	}
	out := new(BacalhauJobStatus)
	in.DeepCopyInto(out)
	return out
}

// DeepCopyInto is an autogenerated deepcopy function, copying the receiver, writing into out. in must be non-nil.
func (in *ExecutionHistory) DeepCopyInto(out *ExecutionHistory) {
	*out = *in
	if in.Logs != nil {
		in, out := &in.Logs, &out.Logs
		*out = make([]string, len(*in))
		copy(*out, *in)
	}
}

// DeepCopy is an autogenerated deepcopy function, copying the receiver, creating a new ExecutionHistory.
func (in *ExecutionHistory) DeepCopy() *ExecutionHistory {
	if in == nil {
		return nil
	}
	out := new(ExecutionHistory)
	in.DeepCopyInto(out)
	return out
}
