# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# build-essential for compiling some python packages
# libpq-dev for postgres support (if needed by some drivers, though asyncpg is pure python mostly but might need it)
RUN apt-get update && apt-get install -y \
  build-essential \
  libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .

# The context is ./backend, so we are already inside the backend directory.
# But wait, looking at the previous file list of `backend`:
# It contains `main.py`, `services/`, etc.
# If I COPY . ., I copy everything in `backend/` to `/app/`.
# So I don't need `COPY backend/ ./backend/`.


COPY . .

# Install dependencies using pip
# We install with [standard] extras if defined, or just the package
RUN pip install --no-cache-dir .

# Expose port
EXPOSE 8000

# Run the application
# Specify host 0.0.0.0 for docker access
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
