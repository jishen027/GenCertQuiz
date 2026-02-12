# Test Data

This directory contains sample files for testing the ingestion pipeline.

## How to Use

1. **Manual Testing via API:**
```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@sample_textbook.pdf" \
  -F "source_type=textbook"
```

2. **CLI Testing:**
```bash
# Test PDF parser only
python backend/services/pdf_parser.py test-data/sample_textbook.pdf

# Test embedder (requires running database)
python backend/services/embedder.py

# Test vision service with an image
python backend/services/vision.py test-data/sample_diagram.png
```

## Sample Files Needed

Place your test files here:
- `sample_textbook.pdf` - A certification study guide PDF (10-20 pages recommended)
- `sample_questions.json` - Sample exam questions in JSON format
- `sample_diagram.png` - A technical diagram for vision testing

## Expected Output

After successful ingestion via the API, you should receive:
```json
{
  "chunks_processed": 150,
  "embeddings_created": 150,
  "images_processed": 5,
  "message": "Successfully ingested sample_textbook.pdf"
}
```
