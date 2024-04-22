function createOrUpdateNodeContainer(nodeContainerID, nodeData) {
    // Check if the camera box already exists
    var nodeContainer = document.getElementById(nodeContainerID);

    // If the camera box doesn't exist, create it
    if (!nodeContainer) {
        let nodeContainerTemplateURL = '/static/node_container_template.html';
        // Get from the nodeContainerTemplateURL and await the response until it is received
        $.get(nodeContainerTemplateURL, function (data) {
            if (document.getElementById(nodeContainerID)) {
                // Node container already exists, update the container if it's not null and return
                if (nodeData) {
                    updateNodeContainer(nodeContainer, nodeData);
                }
                return;
            }
            // Convert the response to a jQuery object
            let rawTemplateBody = domParser.parseFromString(data, 'text/html');
            let nodeDiv = rawTemplateBody.querySelector('#node-container-ID_NOT_SET');
            nodeDiv.id = nodeContainerID;
            // Generate a random sample location
            const sampleLocations = ["Front Street", "4th and Pine", "Main Square", "Broad Ave", "Oakwood Blvd", "Sunset Drive", "Harbor View", "Willow Park", "Maple Lane", "Riverfront"];
            const randomLocation = sampleLocations[Math.floor(Math.random() * sampleLocations.length)];

            // Find the camera location element and set the text to the random location
            $(nodeDiv.querySelector(".camera-location")).text(`Camera - ${randomLocation}`);
            $('#all-nodes').append(nodeDiv);
        }).then(() => {
            // Get the newly created node container
            updateNodeContainer(nodeContainerID, nodeData);
        });
    } else {
        // Update the existing node container
        updateNodeContainer(nodeContainerID, nodeData);
    }
}
function updateNodeContainer(nodeContainerID, nodeData) {
    if (!nodeContainerID || !nodeData) {
        console.error('Invalid parameters:', nodeContainerID, nodeData);
        return;
    }

    const nc = $("#" + nodeContainerID);
    const videoFeed = nc.find(".video-feed");
    const currentVideoFeedSrc = videoFeed.attr("src");
    if (currentVideoFeedSrc !== nodeData.video_feed) {
        videoFeed.attr("src", nodeData.video_feed);
    }

    nc.find(".hostname").text(nodeData.hostname);
    nc.find(".node-id").text(nodeData.hashCode);

    nc.find(".model-name").text(nodeData.model_weights);

    const dataToDisplay = [
        'external_ip',
        'region',
        'zone',
        'source_video_path',
        'model_weights',
        'confidence_threshold',
        'skip_frames',
        'last_inference_time',
        'config_last_update'
    ];

    dataToDisplay.forEach(dataElement => {
        let dataElementCSSName = dataElement.replace(/_/g, '-');
        const element = nc.find("." + dataElementCSSName);
        let dataToDisplayElement = nodeData[dataElement];
        if (dataElement === 'source_video_path') {
            dataToDisplayElement = nodeData[dataElement].split('/').pop();
        }
        element.text(dataToDisplayElement);

        // Highlight the field if it has changed
        eText = element.text();
        dText = dataToDisplayElement;

        if (eText && dText && (eText.toString() !== dText.toString())) {
            element.addClass('updated');
            setTimeout(() => {
                element.removeClass('updated');
            }, 1000);
        }
    });

    // Define detection classes with their respective IDs and descriptions
    const vehicleClasses = {
        2: { label: "Cars", count: 0, icon: "fa-car", element: ".car-count" },
        7: { label: "Trucks", count: 0, icon: "fa-truck", element: ".truck-count" }
    };

    // Populate detections from node data
    var detections = [];
    Object.values(nodeData.total_detections || {}).forEach(detection => detections.push(detection));

    // Process and classify detections
    detections.forEach(function (detection) {
        let vehicleClass = vehicleClasses[detection.class_id];
        if (vehicleClass) {
            vehicleClass.count++;
        }
    });

    // Update the detection count elements
    Object.values(vehicleClasses).forEach(function (vc) {
        const countElement = nc.find(vc.element);
        countElement.text(vc.count);

        // Highlight the count if it has changed
        if (countElement.text() !== vc.count.toString()) {
            countElement.addClass('updated');
            setTimeout(() => {
                countElement.removeClass('updated');
            }, 1000);
        }
    });
}