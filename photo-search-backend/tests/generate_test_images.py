#!/usr/bin/env python3
"""Generate test images for iOS integration testing"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_test_image(filename, width=800, height=600, color=(100, 150, 200), text=""):
    """Create a simple test image with text"""
    img = Image.new('RGB', (width, height), color)
    draw = ImageDraw.Draw(img)
    
    # Add some shapes to make it visually distinct
    draw.rectangle([50, 50, 200, 200], fill=(255, 100, 100))
    draw.ellipse([width-250, 50, width-50, 250], fill=(100, 255, 100))
    draw.polygon([(width//2, height-200), (width//2-100, height-50), (width//2+100, height-50)], fill=(100, 100, 255))
    
    # Add text if provided
    if text:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
        except:
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
    
    img.save(filename, 'JPEG', quality=90)
    print(f"Created: {filename}")

if __name__ == "__main__":
    output_dir = "tests/test_images"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create test images with different colors and content
    test_images = [
        ("test_festival.jpg", (200, 50, 50), "节日"),
        ("test_landscape.jpg", (50, 150, 50), "风景"),
        ("test_person.jpg", (50, 50, 200), "人物"),
        ("test_building.jpg", (150, 100, 50), "建筑"),
        ("test_food.jpg", (200, 150, 50), "美食"),
    ]
    
    for filename, color, text in test_images:
        filepath = os.path.join(output_dir, filename)
        create_test_image(filepath, color=color, text=text)
    
    print(f"\nCreated {len(test_images)} test images in {output_dir}/")
