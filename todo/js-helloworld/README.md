Javascript stuff

Getting started -

We're going to start with a typical javascript application. In this case:
* Docker - https://docs.docker.com/engine/install/
* Node.js/Deno - https://deno.land/manual@v1.14.2/getting_started/installation (Make sure to setup your environment variables (https://deno.land/manual@v1.14.2/getting_started/setup_your_environment))
* A docker.io account (or other container registry) - https://hub.docker.com/signup

Create a new directory for your application:
```bash
mkdir dataprocessing-js
cd dataprocessing-js
```
and add a file called `index.ts` with the following contents:

```javascript
function sayHello(str: string) {
  return `Hello ${str}!`;
}
 
console.log(sayHello("Bacalhau Typescript Data Science"));
```

That should be enough to get started. Now we can run this with the following command:
```bash
deno run index.ts
```

And output the following:
```bash
Hello Bacalhau Typescript Data Science!
```

Alright, we're cooking!

## Creating a Docker file
To go through this example, we're going to run the application next inside a Docker container. To do that, we need to create a Dockerfile. Create a file called `Dockerfile` with the following contents:

```dockerfile
FROM denoland/deno:latest
WORKDIR /app
USER deno
COPY deps.ts .
RUN deno cache deps.ts
COPY index.ts .
RUN deno cache index.ts
RUN mkdir -p /var/tmp/log
CMD ["deno", "run", "--allow-read", "--allow-write", "index.ts"]
```
**NOTE**: This is not a production ready image - normally, you'd pin to a specific version of Deno, and not use the latest tag.

Now type the following:
```bash
# Build the image - You'll want to use your own organization and image name - Below ours is "bacalhauproject/dataprocessing-js".
# If you use this, it will not work for you, because you don't have access to our organization.
docker build -t bacalhauproject/dataprocessing-helloworld .
```

And run it:
```bash
docker run bacalhauproject/dataprocessing-helloworld
```

You should get exactly what you ran before (`Hello Bacalhau Typescript Data Science`), except now it's running inside a container!

## Uploading to a Container Registry
Docker makes it super easy to upload the container - just run the following command:
```bash
docker push bacalhauproject/dataprocessing-helloworld
```

After that, you're done. Your image is now ready for use!

## Using Bacalhau
Ok, now that we've set up our image and uploaded it to a container registry, we can use it with Bacalhau. first, install the CLI:
```bash
curl -sL https://get.bacalhau.org/install.sh | bash
```

Now, run the image on Bacalhau:
```bash
bacalhau docker run bacalhauproject/dataprocessing-helloworld
```

This should output a UUID (like `a241bf43-2206-4ee9-8be0-209fdb01153d`). This is the ID of the job that was created. You can check the status of the job with the following command:
```bash
bacalhau list
```


This should result in an output like the following:
```bash
 CREATED   ID        JOB                      STATE      VERIFIED  PUBLISHED               
 23:37:35  a241bf43  Docker bacalhauproje...  Published            /ipfs/bafybeiegwb7pa... 
```

Where it says "Published", that means the job is done, and we can get the results. To do that, execute the following command:
```bash
bacalhau get a241bf43-2206-4ee9-8be0-209fdb01153d # Only the first eight characters are needed, but you can use the full UUID too.
```

In your current directory, you will now see a directory and three files:
```

```

The directory is the output of the job, and the three files are the logs. The `stdout` file contains the output of the job, and the `stderr` file contains the error output. The `metadata.json` file contains the metadata of the job. You'll also see a `shard` directory, where the results of the job run on each node are stored separately. Because we only ran this job on one node, you'll only see one here. Finally, you can see the unified output of the job in the `output` directory.

When you type:

```bash
cat output/stdout
```
You should see:

```bash
Hello Bacalhau Typescript Data Science!
```

Awesome!

## Using Bacalhau for More Complicated Javascript

'Hello World' is great, but what if we want to do something more complicated? Let's say we want to run a script that reads a file, does some processing, and writes the results to a file. 

For this example, we'll use the Kaggle NYC Taxi data set - a list of taxi rides in New York City. You can download it from here: https://www.kaggle.com/c/nyc-taxi-trip-duration/data.

The full dataset is pretty reasonably sized (about 6 GB), and we want to split it into a series of separate files. Normally, this is pretty annoying to do locally because it takes time to download, process the data, and then re-upload. Through the magic of Bacalhau, we can do this on the same machine that's storing the data.

First, let's create a new file in the same directory called `deps.ts`. This is a dependency file to list all the modules you'd like to cache. Add the following to it:

```javascript
import { readCSVRows, writeCSV } from "https://deno.land/x/csv@v0.7.5/mod.ts";

export { readCSVRows, writeCSV };
```

Next create `process.ts`. Use the following code:

```javascript
import { readCSVRows, writeCSV } from "./deps.ts"

const filename = './sample_set.csv';
const f = await Deno.open(filename);

const filesToWrite: Map<string, Deno.FsFile> = new Map();

let i = 0
let header: string[] = []; // header row

for await (const row of readCSVRows(f)) {
    const asyncRowGenerator = async function*(r: string[]) {
        yield r;
    }

    if (i === 0) {
        i++;
        header = row;
        continue;
    }
    
    const numPassengers = parseInt(row[6]);
    const fileName = `passengers_${numPassengers}.csv`
    
    let fileWriter = await filesToWrite.get(fileName)!
    if (!fileWriter) {
        fileWriter = await Deno.open(fileName,
            { write: true, create: true, append: true, read: true, truncate: false, mode: 0o666 });
        await writeCSV(fileWriter, asyncRowGenerator(header));
        await filesToWrite.set(fileName, fileWriter)
    }

    await writeCSV(fileWriter, asyncRowGenerator(row));
    i++;
}

for (const file of filesToWrite.values()) {
    file.close();
}
```

This script reads the CSV file, and splits it into multiple files based on the number of passengers in the taxi. For example, if the taxi has 2 passengers, it will be written to a file called `passengers_2.csv`. If it has 3 passengers, it will be written to a file called `passengers_3.csv`, and so on. (This is a bit of a trivial example, but we just wanted to demonstrate how to use streams and process a large file on the node.)

The Kaggle dataset has a sample dataset that's smaller that we'll use to test locally. You can download it from here: 

```bash
curl -O https://dweb.link/ipfs/bafybeiaooaau5imt3prwtuvwykob5rtqqp7me3h6et2tgm7nzptf6acss4
```

Download the file called `train.csv` and put it in the same directory as the `process.ts` file.

Now, let's create a Dockerfile. Create a file called `Dockerfile` (overwriting the previous Dockerfile) in the same directory as the other files, and add the following to it:

```dockerfile
FROM denoland/deno:latest
WORKDIR /app
USER deno
COPY deps.ts .
RUN deno cache deps.ts
COPY index.ts .
RUN deno cache index.ts
RUN mkdir -p /var/tmp/log
CMD ["deno", "run", "--allow-read", "--allow-write", "process.ts"]
```

