# Dockerfile
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy and install the Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy our application code from the 'app' folder into the container
COPY ./app /app/app

# Tell Cloud Run which port the application will listen on
EXPOSE 8080

# The command to run the Uvicorn server for our FastAPI application.
# It points to the 'app' variable inside the 'app/chain.py' file.
CMD ["uvicorn", "app.chain:app", "--host", "0.0.0.0", "--port", "8080"]