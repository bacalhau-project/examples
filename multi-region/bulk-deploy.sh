#!/bin/bash

cd tf || exit
# declare -a regions=( "ca-central-1" "ap-southeast-1" "eu-west-1" "eu-east-1" "us-west-1" )
declare -a regions=( "ca-central-1" )

# If aurgument is create, then execute first statement, else execute second statement
if [ "$1" == "create" ]; then
    for r in "${regions[@]}"
    do
        terraform workspace select -or-create "$r"
        terraform init -upgrade
        terraform apply -auto-approve -var "region=$r" -var-file=.env.json
    done
elif [ "$1" == "destroy" ]; then
    for r in "${regions[@]}"
    do
        terraform workspace select "$r"
        terraform destroy -auto-approve -var "region=$r" -var-file=.env.json
    done
else
    echo "Please specify create or destroy"
fi

