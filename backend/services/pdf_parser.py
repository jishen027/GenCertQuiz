"""
PDF parsing service using PyMuPDF (fitz) for reliable cross-platform extraction.
"""
import asyncio
from pathlib import Path
from typing import Dict, List, Any
import base64
import io
import fitz  # PyMuPDF


class PDFParser:
    """Parse PDF documents and extract text and images"""
    
    def __init__(self):
        pass
    
    async def parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text and images from PDF.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dict containing:
                - chunks: List of text chunks with metadata
                - images: List of base64-encoded images
                - metadata: Document-level metadata
        """
        # Run PDF conversion in thread pool (it's CPU-bound)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._convert_pdf,
            file_path
        )
        return result
    
    def _convert_pdf(self, file_path: str) -> Dict[str, Any]:
        """Synchronous PDF conversion (runs in thread pool)"""
        try:
            doc = fitz.open(file_path)
            chunks = []
            images = []
            
            # Extract text and images from each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text with blocks
                text_blocks = page.get_text("blocks")
                for block_idx, block in enumerate(text_blocks):
                    # block format: (x0, y0, x1, y1, "text", block_no, block_type)
                    if len(block) >= 5:
                        text_content = block[4].strip()
                        if text_content:
                            chunks.append({
                                'content': text_content,
                                'page': page_num + 1,
                                'type': 'text_block',
                                'metadata': {
                                    'source_page': page_num + 1,
                                    'block_index': block_idx,
                                    'bbox': [block[0], block[1], block[2], block[3]]
                                }
                            })
                
                # Extract images
                image_list = page.get_images(full=True)
                for img_idx, img_info in enumerate(image_list):
                    try:
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        # Convert to base64
                        img_data = base64.b64encode(image_bytes).decode('utf-8')
                        images.append({
                            'data': img_data,
                            'page': page_num + 1,
                            'format': image_ext
                        })
                    except Exception as e:
                        print(f"Warning: Failed to extract image {img_idx} on page {page_num + 1}: {e}")
            
            # Document metadata
            metadata = {
                'filename': Path(file_path).name,
                'total_pages': len(doc),
                'total_chunks': len(chunks),
                'total_images': len(images)
            }
            
            doc.close()
            
            return {
                'chunks': chunks,
                'images': images,
                'metadata': metadata
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to parse PDF: {str(e)}")


# CLI interface for testing
if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python pdf_parser.py <path_to_pdf>")
        sys.exit(1)
    
    async def main():
        parser = PDFParser()
        result = await parser.parse_pdf(sys.argv[1])
        
        # Print summary (not full content to avoid overwhelming terminal)
        print(json.dumps({
            'metadata': result['metadata'],
            'sample_chunks': result['chunks'][:3] if result['chunks'] else [],
            'image_count': len(result['images'])
        }, indent=2))
    
    asyncio.run(main())
