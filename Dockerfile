# Use a lightweight official Python runtime
FROM python:3.11-slim

# Install git since the utility uses it to clone and update repositories
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file if it exists, or install dependencies directly
# (Using httpx, azure-identity, openai, python-dotenv based on application files)
RUN pip install --no-cache-dir httpx azure-identity openai python-dotenv

# Copy the core application files and library directory
COPY tracker.py update.py index.html ./
COPY lib/ ./lib/

# Expose the internal tracking dashboard port
EXPOSE 8080

# Run the tracker daemon which boots both the HTTP server and the sync thread
CMD ["python", "-u", "tracker.py"]