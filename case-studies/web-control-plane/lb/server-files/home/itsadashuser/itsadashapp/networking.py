
def execute_refresh(url):
    print(f"Refreshing {url}")

    # Test to add a schema if it's not there
    if not url.startswith("http"):
        url = f"http://{url}"

    # Test to make sure the URL is working
    try:
        r = requests.get(url)
    except requests.exceptions.RequestException as e:
        print(f"URL not working: {e}")
        return None

    # Test to see if the endpoint is returning JSON
    try:
        r.json()
    except ValueError as e:
        print(f"{url} not returning JSON: {e}")
        return None

    out = []
    bad = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONNECTIONS) as executor:
        future_to_url = (
            executor.submit(load_url, url, TIMEOUT) for i in range(NUM_REQUESTS)
        )

        for future in concurrent.futures.as_completed(future_to_url):
            try:
                data = future.result()
                out.append(data)
            except Exception as exc:
                data = str(type(exc))
                bad.append(data)

    print(f"Good: {len(out)}")
    print(f"Bad: {len(bad)}")

    # Print line break
    print()

    # Collect all the IPs - make them unique
    ips = set()
    for o in out:
        ips.add(o["ip"])

    # Print the unique IPs, separated by a newline
    print(f"Unique IPs: {len(ips)}")
    print("\n".join(ips))

    return ips