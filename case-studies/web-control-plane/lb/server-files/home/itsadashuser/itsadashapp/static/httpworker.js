// a simple worker for use in the browser (as Web Worker)

importScripts('/static/workerpool.min.js');

function performAPICall(raw_url) {
    url = `http://${raw_url}/json`
    // Create a new Promise to encapsulate the asynchronous API call
    return new Promise((resolve, reject) => {
        // Perform the API call using fetch or any other suitable method
        fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        })
            .then(response => {
                if (response.ok) {
                    // Resolve the Promise with the response data
                    resolve(response.json());
                } else {
                    // Reject the Promise with an error message
                    reject('API call failed with status: ' + response.status);
                }
            })
            .catch(error => {
                // Reject the Promise with any error that occurs during the API call
                reject(error);
            });
    });
}

function eventLoop() {
    while (true) {
        for (var i = 0; i < batchSize - 1; i++) {
            requestLoop();
        }
        window.setTimeout(requestLoop, intervalTime);
        if (stopLoop) {
            break;
        }
    }
}
// create a worker and register public functions
workerpool.worker({
    performAPICall: performAPICall,
    eventLoop: eventLoop,
});