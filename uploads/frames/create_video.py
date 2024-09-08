import os

# Open (or create) filelist.txt in write mode
with open("filelist.txt", "w") as filelist:
    # List all files in the current directory
    for filename in sorted(os.listdir()):
        # Check if the file is an image (by extension)
        if filename.endswith(".jpg") or filename.endswith(".png"):  # Add more extensions if needed
            # Write the required line to the filelist.txt
            filelist.write(f"file '{filename}'\n")