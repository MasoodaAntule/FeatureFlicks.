import os
import cv2
import tensorflow as tf
import tensorflow_hub as hub
from flask import Flask, request, jsonify, send_from_directory, redirect
from werkzeug.utils import secure_filename
import heapq
import ffmpeg
from PIL import Image
from flask_cors import CORS
from flask import url_for
import numpy as np
from dotenv import load_dotenv
import mysql.connector

app = Flask(__name__)
CORS(app)  # Enable CORS to handle cross-origin requests

# Load environment variables from the .env file
load_dotenv()

# Access the variables
db_host = os.getenv("DB_HOST")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")

# MySQL database connection
def get_db_connection():
    conn = mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name
    )
    return conn

# Define upload and output directories
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = r"C:\Users\masoo\OneDrive\Desktop\video\uploads"
app.config['OUTPUT_FOLDER'] = r"C:\Users\masoo\OneDrive\Desktop\video\output"
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB max upload size

# Load the pre-trained model
model = hub.load("https://tfhub.dev/tensorflow/efficientdet/d0/1")

# Function to extract frames from the video
def extract_frames(video_path, output_folder, frame_rate=1):
    os.makedirs(output_folder, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    interval = int(fps // frame_rate)
    
    count = 0
    success, image = cap.read()
    extracted_count = 0
    while success:
        if count % interval == 0:
            frame_filename = os.path.join(output_folder, f"frame_{count}.jpg")
            cv2.imwrite(frame_filename, image)
            extracted_count += 1
        success, image = cap.read()
        count += 1
    cap.release()
    return extracted_count

# Function to perform object detection on a frame
def detect_objects(model, frame_path):
    img = Image.open(frame_path).convert('RGB')
    img = img.resize((512, 512))  # Resize to model input size
    img_array = np.array(img, dtype=np.float32)  # Convert to float32 array
    img_array = img_array / 255.0  # Normalize pixel values to [0, 1]
    img_array = np.expand_dims(img_array, axis=0)  # Add batch dimension
    results = model(img_array)
    print("Model output:", results)  # Print the output to inspect
    return results

# Function to score frames based on detected objects
def score_frame(frame_results):
    print("Frame results keys:", frame_results.keys())
    
    detection_scores = frame_results.get('detection_scores', [])
    
    if isinstance(detection_scores, tf.Tensor):
        detection_scores = detection_scores.numpy()
    
    if isinstance(detection_scores, np.ndarray):
        detection_scores = detection_scores.tolist()

    if isinstance(detection_scores, list) and all(isinstance(i, list) for i in detection_scores):
        detection_scores = [score for sublist in detection_scores for score in sublist]
    
    if not isinstance(detection_scores, list):
        raise ValueError("detection_scores should be a list or a NumPy array")
    
    if not detection_scores:
        print("No detection scores found.")
        return 0.0
    
    try:
        detection_scores = [float(score) for score in detection_scores]
    except (ValueError, TypeError) as e:
        print("Error converting scores to float:", e)
        return 0.0
    
    frame_score = float(max(detection_scores))
    
    print(f"Frame Score: {frame_score}")
    
    return frame_score

# Function to select top-scoring frames
def select_top_frames(frame_scores, top_n=5):
    scalar_frame_scores = {k: float(v) for k, v in frame_scores.items()}
    top_frames = heapq.nlargest(top_n, scalar_frame_scores, key=scalar_frame_scores.get)
    return top_frames

def print_filelist(filelist_path):
    try:
        with open(filelist_path, 'r') as f:
            print(f.read())
    except FileNotFoundError:
        print(f"File not found: {filelist_path}")
    except Exception as e:
        print(f"Error reading filelist: {e}")

# Function to create a shortened video from selected frames
def create_shortened_video(frames, output_video_path):
    output_dir = os.path.dirname(output_video_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    filelist_path = os.path.join(output_dir, 'filelist.txt')
    with open(filelist_path, 'w') as f:
        for frame in frames:
            abs_path = os.path.abspath(frame)
            if os.path.exists(abs_path):
                f.write(f"file '{abs_path}'\n")
            else:
                print(f"Frame file not found: {abs_path}")
    
    print("Filelist contents:")
    print_filelist(filelist_path)
    
    try:
        (
            ffmpeg
            .input(filelist_path, format='concat', safe=0)
            .output(output_video_path, vcodec='libx264', pix_fmt='yuv420p')
            .run(cmd=r"C:\ffmpeg\bin\ffmpeg.exe", overwrite_output=True)
        )
    except ffmpeg._run.Error as e:
        print("ffmpeg error:")
        print(e.stderr)
        raise

@app.route('/')
def index():
    return send_from_directory('', 'index.html')

@app.route('/process_video', methods=['POST'])
def process_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file uploaded'}), 400

    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    video_filename = secure_filename(video_file.filename)
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)

    # Check if video has already been processed
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM processed_videos WHERE video_filename = %s", (video_filename,))
    video_record = cursor.fetchone()
    
    if video_record and video_record[2]:  # Check if processed flag is True
        cursor.close()
        conn.close()
        # Redirect to the stored shortened video URL
        return jsonify({'error': 'Video has already been processed'}), 400

    # Save the uploaded file
    video_file.save(video_path)

    # Directory to store extracted frames
    frames_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'frames')
    os.makedirs(frames_folder, exist_ok=True)

    # Extract frames at a specific frame rate
    frame_rate = 3  # Frames per second, adjust as needed
    extracted_count = extract_frames(video_path, frames_folder, frame_rate)

    # Score and store frames
    frame_scores = {}
    for frame_file in sorted(os.listdir(frames_folder)):
        if frame_file.endswith('.jpg'):
            frame_path = os.path.join(frames_folder, frame_file)
            frame_results = detect_objects(model, frame_path)
            frame_scores[frame_path] = score_frame(frame_results)

    # Select top N frames
    top_n_frames = 5  # Number of top frames to select, adjust as needed
    top_frames = select_top_frames(frame_scores, top_n=top_n_frames)

    # Create the shortened video from the top frames
    output_video_path = os.path.join(app.config['OUTPUT_FOLDER'], 'shortened_video.mp4')
    create_shortened_video(list(top_frames), output_video_path)

    # Update or insert record in the database
    shortened_video_url = url_for('output_file', filename=os.path.basename(output_video_path), _external=True)
    cursor.execute(
        "INSERT INTO processed_videos (video_filename, processed, shortened_video_url) VALUES (%s, TRUE, %s)"
        "ON DUPLICATE KEY UPDATE processed = TRUE, shortened_video_url = %s",
        (video_filename, shortened_video_url,shortened_video_url)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        'message': 'Video processed successfully',
        'trailer_url': f'/output/{os.path.basename(output_video_path)}'
    })

@app.route('/output/<filename>')
def output_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
