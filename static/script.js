document.addEventListener("DOMContentLoaded", function() {
    // Show file name when a file is selected
    document.getElementById('file-input').addEventListener('change', function(event) {
        const fileName = event.target.files[0].name; // Get the selected file name
        document.getElementById('file-name').textContent = fileName; // Display the file name
        document.getElementById('file-name-container').classList.remove('hidden'); // Show the file name container
    });

    // Show loading message and handle form submission
    document.getElementById('upload-form').addEventListener('submit', function(event) {
        event.preventDefault(); // Prevent default form submission

        // Show loading message
        document.getElementById('loading-message-container').classList.remove('hidden');

        //Animate the dots in the loading message
        let loadingMessage = document.getElementById('loading-message');
        let dotCount = 0;
        const maxDots = 3;
        const loadingInterval = setInterval(function() {
            loadingMessage.textContent = `Please wait, your video is being processed${'.'.repeat(dotCount)}`;
            dotCount = (dotCount + 1) % (maxDots + 1); // Cycle through 0 to 3 dots
        }, 500); // Update every half second

        const formData = new FormData(this);
        fetch('/process_video', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById('loading-message-container').classList.add('hidden'); // Hide loading message
            document.getElementById('file-name-container').classList.add('hidden'); // Hide file name container
            if (data.error) {
                document.getElementById('result').innerText = `Error: ${data.error}`;
            } else {
                document.getElementById('result').innerHTML = `Video processed successfully! <a href="${data.trailer_url}" target="_blank">View Shortened Video</a>`;
            }
            document.getElementById('result').classList.remove('hidden'); // Show result container
        })
        .catch(error => {
            document.getElementById('loading-message-container').classList.add('hidden'); // Hide loading message
            document.getElementById('result').innerText = `Error: ${error}`;
            document.getElementById('result').classList.remove('hidden'); // Show result container
        });
    });

    // Handle showing the processed videos panel
    const showVideosButton = document.getElementById('show-videos-button');
    const videoPanel = document.getElementById('processed-videos-panel');
    const videoList = document.getElementById('video-list');

    showVideosButton.addEventListener('click', function() {
        // Fetch processed videos from the server
        fetch('/get_processed_videos')
        .then(response => response.json())
        .then(data => {
            // Clear any existing video links
            videoList.innerHTML = '';

            // Add video links to the list
            data.videos.forEach(video => {
                const listItem = document.createElement('li');
                listItem.innerHTML = `<a href="${video.url}" target="_blank">${video.filename}</a>`;
                videoList.appendChild(listItem);
            });

            // Show the video panel
            videoPanel.classList.toggle('hidden');
        })
        .catch(error => {
            console.error('Error fetching processed videos:', error);
        });
    });
});
