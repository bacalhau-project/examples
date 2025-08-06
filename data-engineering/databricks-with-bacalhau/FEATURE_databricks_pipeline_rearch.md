# Feature Improve Databricks Pipeline for Demo

I'm looking to demonstrate the functionality of a remote data pipeline period. Right now we have sensors which generate log lines
which are not very interesting period. First I want to take a that flat log find and convert it into structured logging before I move it period. And I want to
add a second demo step around adding metadata around that transformation so that we can always get it back about the job ID that I ran on it period. Third I
want to then push a data model to enforce verification of data that moved Period. Fourth, I want to send raw data to one bucket and aggregated data on a
permanent data basis to a second bucket, and emergency data to a third bucket. Period. And fourth, I want to strip CPS location down to 100 meters period Our
point is to execute each one of these things one at a time and then demonstrate that this kind of things had happened so that we can show how expanding and
improving your data pipelines will happen period Similarly in the Applying Data Model we should show how this will stop things that normally break data
pipelines such as negative numbers or strings catch strings where things are not supposed to be period Let's build a thorough To Do list on how to transform
the various jobs we have in place today into this new field. Format and this new pattern period Let's also as part of that spec build out a simple UI that
demonstrates by querying Databricks to show that things are actually changing period Your goal is to produce a very thorough detailed spec around this. where
each change can be smoke tested locally before deploying or officially changing it but then ultimately removing old functionality that is no longer necessary.