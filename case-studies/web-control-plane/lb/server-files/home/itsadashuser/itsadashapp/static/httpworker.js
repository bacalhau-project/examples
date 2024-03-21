self.addEventListener('message', function (e) {
    console.log('Worker: Message received from main thread', e.data);

    var data = {}
    // Perform the asynchronous API call
    performAPICall(`http://${e.data}/json`)
        .then(responseData => {
            // Send the response data back to the main thread
            self.postMessage(responseData);
        })
        .catch(error => {
            // Handle any errors that occur during the API call
            console.error('Error:', error);
        });

    // Send a message back to the main thread
}, false);

function performAPICall(url) {
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