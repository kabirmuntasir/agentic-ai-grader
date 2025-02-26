FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p uploads static/output

# Make port 8080 available (Cloud Run default)
EXPOSE 8080

# Command to run the application
CMD streamlit run app.py --server.port 8080 --server.address 0.0.0.0 