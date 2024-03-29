#!/usr/bin/env bash
rsync -avz --exclude-from=rsync-exclude.txt . itsadashuser@100.104.84.4:/home/itsadashuser/itsadashapp
