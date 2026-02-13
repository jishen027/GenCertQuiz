"""
Vision service using Claude Vision API for diagram and image description.
"""
import os
from typing import Optional


class VisionService:
    """Extract technical details from images using Claude Vision"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o"
    ):
        """
        Initialize the vision service.
        
        Args:
            api_key: OpenAI API key (defaults to env var)
            model: OpenAI model with vision capabilities (default: gpt-4o)
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not provided")
        
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def describe_diagram(
        self,
        image_base64: str,
        image_format: str = "png",
        context: Optional[str] = None
    ) -> str:
        """
        Generate detailed description of a diagram or technical image.
        
        Args:
            image_base64: Base64-encoded image data
            image_format: Image format (png, jpeg, etc.)
            context: Optional context about the image source
            
        Returns:
            Detailed text description of the image
        """
        # Build prompt
        prompt = """You are analyzing a technical diagram or image from a certification study guide. 
Extract and describe ALL technical details, including:
- Architecture components and their relationships
- Data flows and connections
- Labels, text, and annotations
- Key concepts being illustrated
- Any AWS/cloud services shown (if applicable)

Be thorough and precise. This description will be used to generate exam questions."""
        
        if context:
            prompt += f"\n\nContext: {context}"
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{image_base64}"
                                }
                            }
                        ],
                    }
                ],
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise RuntimeError(f"Failed to describe image: {str(e)}")
    
    async def batch_describe(
        self,
        images: list[dict],
        context: Optional[str] = None
    ) -> list[str]:
        """
        Describe multiple images.
        
        Args:
            images: List of dicts with 'data' (base64) and 'format' keys
            context: Optional context for all images
            
        Returns:
            List of descriptions
        """
        import asyncio
        
        tasks = [
            self.describe_diagram(
                img['data'],
                img.get('format', 'png'),
                context
            )
            for img in images
        ]
        
        return await asyncio.gather(*tasks)


# CLI interface for testing
if __name__ == "__main__":
    import sys
    import asyncio
    import base64
    from pathlib import Path
    from dotenv import load_dotenv
    
    load_dotenv()
    
    async def main():
        if len(sys.argv) < 2:
            print("Usage: python vision.py <path_to_image>")
            sys.exit(1)
        
        # Read and encode image
        image_path = Path(sys.argv[1])
        image_data = base64.b64encode(image_path.read_bytes()).decode('utf-8')
        image_format = image_path.suffix.lstrip('.')
        
        # Describe the image
        service = VisionService()
        description = await service.describe_diagram(image_data, image_format)
        
        print("=" * 80)
        print("IMAGE DESCRIPTION:")
        print("=" * 80)
        print(description)
        print("=" * 80)
    
    asyncio.run(main())
