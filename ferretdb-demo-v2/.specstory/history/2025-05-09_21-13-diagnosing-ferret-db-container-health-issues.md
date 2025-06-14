<!-- Generated by SpecStory -->

# Diagnosing Ferret DB Container Health Issues (2025-05-09 14:13:26)

_**User**_

why is the ferret db container unhealthy? how do i diagnose it?

---

_**Assistant**_



---

The `ferretdb` container is marked as unhealthy if its healthcheck fails. According to your `docker-compose.yml` file, the healthcheck command is:

`curl -f http://localhost:8088/debug/livez`

This command checks if the FerretDB liveness probe endpoint is responding successfully. If this command fails (e.g., returns a non-2xx HTTP status code or times out), Docker will mark the container as unhealthy.

Here's how you can diagnose the issue:

1.  **Check FerretDB container logs**:
    I'll provide you with the command to view the logs for the `ferret-demo-ferretdb` container. This is often the first place to look for errors or reasons why the service might not be starting correctly.
    

---

```bash
docker logs ferret-demo-ferretdb
```

```
2025-05-09T21:10:17.496Z        INFO    ferretdb/main.go:351    Starting FerretD
B 
v2.1.0  {"branch":"unknown","buildEnvironment":{"-buildmode":"exe","-compiler":"
gc","-trimpath":"true","CGO_ENABLED":"0","GOARCH":"arm64","GOARM64":"v8.0","GOOS
":"linux","go.runtime":"go1.24.2","go.version":"go1.24.2","vcs":"git","vcs.modif
ied":"true","vcs.revision":"05ed2b952c612533cb12c1ff1a0319a4e7f2e4b5","vcs.time"
:"2025-04-03T15:34:04Z"},"commit":"05ed2b952c612533cb12c1ff1a0319a4e7f2e4b5","de
vBuild":false,"dirty":true,"package":"docker","uuid":"093432f2-fb68-47bb-9cb7-69
dcee7a1a50","version":"v2.1.0"}
              2025-05-09T21:10:17.496Z        INFO    ferretdb/main.go:361    ma
xprocs: Leaving 
GOMAXPROCS=12: CPU quota undefined
  2025-05-09T21:10:17.499Z        INFO    telemetry/reporter.go:167       The te
leme
try state is undecided; the first report will be sent in 1h0m0s. Read more about
 FerretDB telemetry and how to opt out at https://beacon.ferretdb.com     {"name
":"telemetry"}
      2025-05-09T21:10:17.500Z        INFO    clientconn/listener.go:102      Li
stening 
on TCP [::]:27017       {"name":"listener"}
  2025-05-09T21:10:17.500Z        INFO    debug/debug.go:234      Starting debug
 ser
ver on http://[::]:8088/debug   {"name":"debug"}
  2025-05-09T21:10:17.500Z        INFO    debug/debug.go:239      http://[::]:80
88/d
ebug/archive - Zip archive with debugging information   {"name":"debug"}
  2025-05-09T21:10:17.500Z        INFO    debug/debug.go:239      http://[::]:80
88/d
ebug/events - /x/net/trace events       {"name":"debug"}
  2025-05-09T21:10:17.500Z        INFO    debug/debug.go:239      http://[::]:80
88/d
ebug/graphs - Visualize metrics {"name":"debug"}
  2025-05-09T21:10:17.500Z        INFO    debug/debug.go:239      http://[::]:80
88/d
ebug/livez - Liveness probe     {"name":"debug"}
  2025-05-09T21:10:17.500Z        INFO    debug/debug.go:239      http://[::]:80
88/d
ebug/metrics - Metrics in Prometheus format     {"name":"debug"}
  2025-05-09T21:10:17.500Z        INFO    debug/debug.go:239      http://[::]:80
88/d
ebug/pprof - Runtime profiling data for pprof   {"name":"debug"}
  2025-05-09T21:10:17.500Z        INFO    debug/debug.go:239      http://[::]:80
88/d
ebug/readyz - Readiness probe   {"name":"debug"}
  2025-05-09T21:10:17.500Z        INFO    debug/debug.go:239      http://[::]:80
88/d
ebug/requests - /x/net/trace requests   {"name":"debug"}
  2025-05-09T21:10:17.500Z        INFO    debug/debug.go:239      http://[::]:80
88/d
ebug/vars - Expvar package metrics      {"name":"debug"}
  
```

---

    The logs for `ferret-demo-ferretdb` don't show any obvious errors. It seems to be starting up and listening.

2.  **Manually run the healthcheck command inside the container**:
    This will tell you exactly what response the healthcheck is getting. I'll provide the command to do this.
    

---

```bash
docker exec ferret-demo-ferretdb curl -f http://localhost:8088/debug/livez
```

```
daaronch@M2-Max ~/c/b/ferretdb-demo-v2 (main)> docker exec ferret-demo-ferretdb cu

OCI runtime exec failed: exec failed: unable to start container process: exec: "cu
rl": executable file not found in $PATH: unknown
daaronch@M2-Max ~/c/b/ferretdb-demo-v2 (main) [126]>
```

---

    It appears the `curl` command is not available inside the `ferret-demo-ferretdb` container. This is why the healthcheck is failing.

    The `ferretdb` image `ghcr.io/bacalhau-project/examples/ferretdb-demo-ferretdb:2504162218` likely doesn't include `curl`.

    To fix this, you have a couple of options:
    *   **Modify the Docker image**: Add `curl` to the `ferretdb` Docker image. This is the most robust solution.
    *   **Change the healthcheck command**: Use a command that is available in the image, for example, `wget` if that's available, or a built-in FerretDB command if one exists for health checking. However, without knowing the image contents, `curl` or `wget` are standard.
    *   **Remove the healthcheck**: This is not recommended for production but can be a temporary workaround if you just want to get the service running.

    Given the current image, the easiest immediate fix without rebuilding the image (if `wget` is available) would be to change the healthcheck. If `wget` is not available, you might need to find an alternative way to check the service's health from within the container or rebuild the image.

    Let's check if `wget` is available.
    

---

```bash
docker exec ferret-demo-ferretdb wget --spider -q -O - http://localhost:8088/debug/livez
```

```
daaronch@M2-Max ~/c/b/ferretdb-demo-v2 (main) [126]> docker exec ferret-demo-ferre
                                                     /livez
OCI runtime exec failed: exec failed: unable to start container process: exec: "wg
et": executable file not found in $PATH: unknown
daaronch@M2-Max ~/c/b/ferretdb-demo-v2 (main) [126]>
```

---

    `wget` is also not available in the container.

    This means the healthcheck in your `docker-compose.yml` for the `ferretdb` service cannot work as `curl` is not present in the image `ghcr.io/bacalhau-project/examples/ferretdb-demo-ferretdb:2504162218`.

    **Recommendations:**

    1.  **Best Solution: Rebuild the Docker image for FerretDB**
        *   Modify the Dockerfile for `ghcr.io/bacalhau-project/examples/ferretdb-demo-ferretdb:2504162218` to include `curl` (e.g., by adding `RUN apt-get update && apt-get install -y curl` for Debian-based images, or `RUN apk add --no-cache curl` for Alpine-based images).
        *   Push the updated image and use that in your `docker-compose.yml`.

    2.  **Alternative: Use a different healthcheck mechanism if possible**
        *   FerretDB might offer a command-line tool within the container that can check its status. You'd need to consult the FerretDB documentation or explore the container's file system to see if such a tool exists.

    3.  **Temporary Workaround: Disable the healthcheck**
        *   If you urgently need the service to run and are not concerned about its health status for now, you can comment out or remove the `healthcheck` section for the `ferretdb` service in your `docker-compose.yml`. This is not recommended for long-term or production use.

    Since I cannot modify the Docker image for you, would you like me to:
    *   Show you how to comment out the healthcheck in `docker-compose.yml` as a temporary measure?
    *   Help you find the Dockerfile for this image so you can add `curl`? (This might involve searching on GitHub if it's an open-source project).
    *   Search for FerretDB documentation on alternative healthcheck methods?

---

_**User**_

show me how to make the port available externally so i can test it.

---

_**Assistant**_



---

The `ferretdb` service in your `docker-compose.yml` file already exposes its internal port `27017` to port `27217` on your host machine. You can see this in the `ports` section:

```yaml
  ferretdb:
    # ... other configurations ...
    ports:
      - "27217:27017"  # Host port 27217 maps to container port 27017
    # ... other configurations ...
```

This configuration means that after you run `docker-compose up -d`, you should be able to connect to FerretDB from your host machine (the machine where Docker is running) using an address like `mongodb://localhost:27217` or `mongodb://127.0.0.1:27217`.

If you'd like to use the standard MongoDB port `27017` directly on your host machine (so you can connect to `mongodb://localhost:27017`), you would change the mapping from `"27217:27017"` to `"27017:27017"`.

I can make this change for you in your `docker-compose.yml` file. This will map port `27017` of the container to port `27017` of your host machine.

Would you like me to proceed with changing `27217:27017` to `27017:27017`?

Keep in mind that if you have another service (like a local MongoDB instance) already using port `27017` on your host, this will cause a port conflict. The current mapping to `27217` avoids this common issue.

---

_**User**_

this is distroless, but we want to have a healthcheck in it. we could install and use curl, but if there's an easier way to check localhost:8088/debug/livez for 200 response, that's better.

---

_**Assistant**_



---

<details>
            <summary>Searched web "FerretDB CLI health check localhost:8088/debug/livez" • **2** results</summary>
        
| Title | URL |
|-------|-----|
| Localhost:8088 is not working | https://forum.inductiveautomation.com/t/localhost-8088-is-not-working/75243 |
| FerretDB releases v1.23.0 with improved observability | https://blog.ferretdb.io/ferretdb-releases-v123-improved-observability/ |

</details>

---

The web search was very fruitful!

A recent FerretDB blog post ("FerretDB releases v1.23.0 with improved observability") mentions:
"Similarly, all Docker images now include a `HEALTHCHECK` instruction that behaves like a readiness probe, so that the Docker container is only considered healthy when FerretDB is ready to handle connections."

This implies that newer versions of FerretDB images (v1.23.0+) come with a built-in `HEALTHCHECK` in their Dockerfile. Your current image is `ghcr.io/ferretdb/ferretdb:2.1.0`. While this version number seems older than v1.23.0, the blog post was published on July 26, 2024, but references FerretDB v2.2.0, v2.1.0, etc., in its sidebar for *2025*. This is a bit confusing regarding versioning and dates, but the key is that the FerretDB team is aware of the need for healthchecks and has started incorporating them.

The image `ghcr.io/ferretdb/ferretdb:2.1.0` (which your `local_copies_of_docker_images/ferretdb/Dockerfile` is based on) might already have a `HEALTHCHECK` instruction defined. If it does, you might not need to specify one in your `docker-compose.yml` at all, or you could align your `docker-compose.yml` healthcheck with the one built into the image.

Let's inspect the base image `ghcr.io/ferretdb/ferretdb:2.1.0` to see if it has a `HEALTHCHECK` defined and what command it uses. I'll use a docker command to inspect the image.


---



---



---



---

