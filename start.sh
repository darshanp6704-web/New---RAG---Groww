#!/bin/bash

# Initialize the vector DB if it is missing or empty
if [ ! -d "data/vector_db" ] || [ -z "$(ls -A data/vector_db 2>/dev/null)" ]; then
    echo "Vector database not found or empty. Initializing database..."
    python src/ingestion/scheduler.py --now
fi

# Start the scheduler in the background
echo "Starting Ingestion Pipeline Scheduler..."
python src/ingestion/scheduler.py &

# Start the Streamlit app in the foreground, binding to the PORT environment variable
echo "Starting Streamlit App..."
streamlit run src/ui/app.py --server.port ${PORT:-8501} --server.address 0.0.0.0
