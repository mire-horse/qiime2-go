
# Dockerfile for QIIME2-go platform

# Use the official QIIME2 image as the base
FROM quay.io/qiime2/core:2023.5

# Install additional dependencies
RUN pip install flask==2.3.2 werkzeug==2.3.4 pandas==2.0.0

# Set the working directory
WORKDIR /app

# Copy the application files
COPY app.py /app/
COPY templates /app/templates/
COPY static /app/static/

# Create required directories
RUN mkdir -p /app/uploads /app/exports

# Expose the port
EXPOSE 5000

# Command to run the application
CMD ["python", "app.py"]
