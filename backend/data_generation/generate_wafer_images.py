#!/usr/bin/env python3
"""
Generate synthetic wafer defect maps with various defect patterns.
Creates thumbnails for MongoDB and full-resolution images for S3 storage.
"""

import os
import json
import numpy as np
import base64
from io import BytesIO
from PIL import Image, ImageDraw
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
import random
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class S3ImageUploader:
    """Handles S3 uploads for wafer images."""
    
    def __init__(self):
        """Initialize S3 client from environment variables."""
        self.s3_bucket_uri = os.getenv("S3_BUCKET_URI", "")
        self.s3_client = None
        self.bucket_name = None
        self.prefix = ""
        
        if self.s3_bucket_uri:
            self._parse_s3_uri()
            self._init_s3_client()
    
    def _parse_s3_uri(self):
        """Parse S3 URI to extract bucket name and prefix."""
        if self.s3_bucket_uri.startswith("s3://"):
            # Remove s3:// prefix
            path = self.s3_bucket_uri[5:]
            parts = path.split("/", 1)
            self.bucket_name = parts[0]
            self.prefix = parts[1] if len(parts) > 1 else ""
            if self.prefix and not self.prefix.endswith("/"):
                self.prefix += "/"
        else:
            # Assume it's just a bucket name
            self.bucket_name = self.s3_bucket_uri
    
    def _init_s3_client(self):
        """Initialize S3 client."""
        try:
            self.s3_client = boto3.client('s3')
            # Test connection
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"✓ Connected to S3 bucket: {self.bucket_name}")
        except ClientError as e:
            print(f"⚠ Warning: Could not connect to S3 bucket '{self.bucket_name}': {e}")
            print("  Full-resolution images will not be uploaded to S3")
            self.s3_client = None
        except Exception as e:
            print(f"⚠ Warning: S3 initialization failed: {e}")
            self.s3_client = None
    
    def upload_image(self, image: Image.Image, key: str) -> Optional[str]:
        """
        Upload image to S3.
        
        Args:
            image: PIL Image object
            key: S3 object key (filename)
            
        Returns:
            S3 URL if successful, None otherwise
        """
        if not self.s3_client:
            return None
        
        try:
            # Convert image to bytes
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            buffer.seek(0)
            
            # Full S3 key with prefix
            full_key = f"{self.prefix}wafer_images/{key}"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=full_key,
                Body=buffer,
                ContentType='image/png',
                Metadata={
                    'generated': datetime.now().isoformat(),
                    'type': 'wafer_defect_map'
                }
            )
            
            # Return S3 URL
            return f"s3://{self.bucket_name}/{full_key}"
            
        except ClientError as e:
            print(f"  ⚠ Failed to upload {key} to S3: {e}")
            return None
        except Exception as e:
            print(f"  ⚠ Unexpected error uploading to S3: {e}")
            return None


def generate_wafer_map(
    pattern_type: str = "random",
    defect_rate: float = 0.05,
    wafer_size: int = 25,
    die_size: int = 20,
    s3_uploader: Optional[S3ImageUploader] = None,
    wafer_id: str = "W_0001"
) -> Dict[str, Any]:
    """
    Generate a synthetic wafer ink map with defect patterns.
    Creates both thumbnail for MongoDB and full-resolution for S3.
    
    Args:
        pattern_type: Type of defect pattern (clustered, edge, random, systematic)
        defect_rate: Base defect rate for random patterns
        wafer_size: Number of dies in each dimension (25x25 grid)
        die_size: Size of each die in pixels
        s3_uploader: Optional S3 uploader instance
        wafer_id: Wafer ID for S3 key naming
        
    Returns:
        Dictionary containing thumbnail, S3 URL, die map, and statistics
    """
    image_size = wafer_size * die_size
    
    # Create image
    img = Image.new('RGB', (image_size, image_size), 'white')
    draw = ImageDraw.Draw(img)
    
    # Generate die map (1 = pass, 0 = fail)
    die_map = np.ones((wafer_size, wafer_size))
    
    # Create defect pattern
    if pattern_type == "clustered":
        # Create 1-3 clusters of defects
        num_clusters = np.random.randint(1, 4)
        for _ in range(num_clusters):
            cluster_x = np.random.randint(3, wafer_size - 7)
            cluster_y = np.random.randint(3, wafer_size - 7)
            cluster_size = np.random.randint(3, 8)
            
            for i in range(max(0, cluster_x - cluster_size//2), 
                          min(wafer_size, cluster_x + cluster_size//2)):
                for j in range(max(0, cluster_y - cluster_size//2), 
                              min(wafer_size, cluster_y + cluster_size//2)):
                    # Higher defect probability near cluster center
                    distance = np.sqrt((i - cluster_x)**2 + (j - cluster_y)**2)
                    prob = max(0, 1 - distance / cluster_size) * 0.9
                    if np.random.random() < prob:
                        die_map[i][j] = 0
    
    elif pattern_type == "edge":
        # Edge defects - more common near wafer edge
        center = wafer_size / 2
        for i in range(wafer_size):
            for j in range(wafer_size):
                distance_from_center = np.sqrt((i - center)**2 + (j - center)**2)
                if distance_from_center > wafer_size * 0.35:  # Near edge
                    if np.random.random() < 0.3:
                        die_map[i][j] = 0
    
    elif pattern_type == "systematic":
        # Systematic pattern - regular defects
        step = np.random.randint(3, 6)
        offset = np.random.randint(0, step)
        for i in range(offset, wafer_size, step):
            for j in range(offset, wafer_size, step):
                if np.random.random() < 0.7:
                    die_map[i][j] = 0
    
    else:  # random
        # Random defects across wafer
        defect_mask = np.random.random((wafer_size, wafer_size)) < defect_rate
        die_map[defect_mask] = 0
    
    # Draw wafer circle background
    center_x, center_y = image_size / 2, image_size / 2
    wafer_radius = (wafer_size * die_size) / 2 - 10
    draw.ellipse(
        [(center_x - wafer_radius, center_y - wafer_radius),
         (center_x + wafer_radius, center_y + wafer_radius)],
        outline='gray',
        width=2
    )
    
    # Draw dies on image
    defect_locations = []
    for i in range(wafer_size):
        for j in range(wafer_size):
            x = j * die_size
            y = i * die_size
            
            # Check if within circular wafer boundary
            die_center_x = x + die_size/2
            die_center_y = y + die_size/2
            if np.sqrt((die_center_x - center_x)**2 + 
                      (die_center_y - center_y)**2) < wafer_radius:
                
                # Determine die color
                if die_map[i][j] == 1:
                    color = '#90EE90'  # Light green for pass
                else:
                    color = '#FF6B6B'  # Light red for fail
                    defect_locations.append({'x': j, 'y': i})
                
                # Draw die
                draw.rectangle(
                    [x + 1, y + 1, x + die_size - 2, y + die_size - 2],
                    fill=color,
                    outline='#333333'
                )
    
    # Add wafer ID text
    draw.text((10, 10), f"Pattern: {pattern_type.upper()}", fill='black')
    draw.text((10, 30), f"ID: {wafer_id}", fill='black')
    
    # Create thumbnail (150x150)
    thumbnail = img.copy()
    thumbnail.thumbnail((150, 150), Image.Resampling.LANCZOS)
    
    # Convert thumbnail to base64 for MongoDB
    thumb_buffer = BytesIO()
    thumbnail.save(thumb_buffer, format='PNG')
    thumb_base64 = base64.b64encode(thumb_buffer.getvalue()).decode()
    
    # Upload full-resolution image to S3 if uploader available
    s3_url = None
    if s3_uploader:
        s3_key = f"{wafer_id}_{pattern_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        s3_url = s3_uploader.upload_image(img, s3_key)
    
    # Calculate statistics
    total_dies = int(np.sum(die_map >= 0))  # Count all valid dies
    failed_dies = int(np.sum(die_map == 0))
    yield_percentage = (1 - failed_dies / max(total_dies, 1)) * 100
    
    result = {
        "thumbnail_base64": thumb_base64,  # Small thumbnail for MongoDB
        "thumbnail_size": "150x150",
        "die_map": die_map.tolist(),
        "pattern_type": pattern_type,
        "defect_locations": defect_locations,
        "statistics": {
            "total_dies": total_dies,
            "failed_dies": failed_dies,
            "yield_percentage": round(yield_percentage, 2)
        }
    }
    
    # Add S3 URL if upload was successful
    if s3_url:
        result["full_image_url"] = s3_url
        result["full_image_size"] = f"{image_size}x{image_size}"
    else:
        # Fallback: store full image as base64 if S3 not available
        full_buffer = BytesIO()
        img.save(full_buffer, format='PNG')
        result["full_image_base64"] = base64.b64encode(full_buffer.getvalue()).decode()
        result["full_image_size"] = f"{image_size}x{image_size}"
    
    return result


def generate_wafer_defects_data(
    count: int = 100,
    anomaly_timestamps: List[Dict] = None,
    s3_uploader: Optional[S3ImageUploader] = None
) -> List[Dict[str, Any]]:
    """
    Generate wafer defect data with correlations to sensor anomalies.
    Uses hybrid storage: thumbnails in MongoDB, full images in S3.
    
    Args:
        count: Number of wafer maps to generate
        anomaly_timestamps: List of anomaly events from sensor data
        s3_uploader: Optional S3 uploader for full-resolution images
        
    Returns:
        List of wafer defect records
    """
    patterns = ["clustered", "edge", "random", "systematic"]
    pattern_weights = [0.3, 0.2, 0.4, 0.1]  # Clustered more common for particle issues
    
    wafer_defects = []
    base_time = datetime.now() - timedelta(days=30)
    
    for i in range(count):
        # Determine pattern type
        # If there was a recent anomaly, increase chance of clustered defects
        pattern = np.random.choice(patterns, p=pattern_weights)
        
        # Generate wafer ID
        wafer_id = f"W_{i+1:04d}"
        
        # Generate wafer map with S3 upload
        wafer_data = generate_wafer_map(
            pattern_type=pattern,
            s3_uploader=s3_uploader,
            wafer_id=wafer_id
        )
        
        # Create timestamp (distributed over 30 days)
        hours_offset = (i * 30 * 24) // count  # Distribute evenly
        timestamp = base_time + timedelta(hours=hours_offset)
        
        # Determine equipment and process context
        equipment_id = np.random.choice(["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "LITHO_01"])
        
        # Create defect description based on pattern
        if pattern == "clustered":
            description = f"Clustered particle defects observed in quadrant {np.random.choice(['upper-right', 'lower-left', 'center'])}, likely contamination from {equipment_id.split('_')[0]} process"
        elif pattern == "edge":
            description = f"Edge die failures detected, possible handling damage or process uniformity issue in {equipment_id}"
        elif pattern == "systematic":
            description = f"Systematic pattern defects, potential reticle or stepper issue in {equipment_id}"
        else:
            description = f"Random defects across wafer, baseline yield loss from {equipment_id.split('_')[0]} process"
        
        # Determine severity based on yield
        yield_pct = wafer_data["statistics"]["yield_percentage"]
        if yield_pct < 85:
            severity = "high"
        elif yield_pct < 92:
            severity = "medium"
        else:
            severity = "low"
        
        # Create wafer defect record with hybrid storage
        ink_map = {
            "thumbnail_base64": wafer_data["thumbnail_base64"],
            "thumbnail_size": wafer_data["thumbnail_size"],
            "format": "PNG"
        }
        
        # Add full image reference (S3 URL or base64 fallback)
        if "full_image_url" in wafer_data:
            ink_map["full_image_url"] = wafer_data["full_image_url"]
            ink_map["full_image_size"] = wafer_data["full_image_size"]
        elif "full_image_base64" in wafer_data:
            ink_map["full_image_base64"] = wafer_data["full_image_base64"]
            ink_map["full_image_size"] = wafer_data["full_image_size"]
        
        record = {
            "wafer_id": wafer_id,
            "lot_id": f"LOT_2025_{(i // 25 + 1):03d}",
            "inspection_timestamp": timestamp.isoformat() + "Z",
            "ink_map": ink_map,
            "defect_summary": {
                "total_dies": wafer_data["statistics"]["total_dies"],
                "failed_dies": wafer_data["statistics"]["failed_dies"],
                "yield_percentage": wafer_data["statistics"]["yield_percentage"],
                "defect_pattern": pattern,
                "severity": severity
            },
            "die_map": wafer_data["die_map"],
            "defects": [
                {
                    "type": "particle" if pattern == "clustered" else "process",
                    "location": loc,
                    "size_um": round(np.random.uniform(0.1, 2.0), 2),
                    "confidence": round(np.random.uniform(0.85, 0.99), 2)
                }
                for loc in wafer_data["defect_locations"][:10]  # Limit to 10 defects
            ],
            "description": description,
            "process_context": {
                "last_process_step": equipment_id.split("_")[0],
                "equipment_used": [equipment_id],
                "slurry_batch": f"SB_2025_{np.random.randint(1, 51):03d}",
                "clean_cycle": np.random.randint(100, 200)
            }
        }
        
        wafer_defects.append(record)
    
    return wafer_defects


def main():
    """Generate and save wafer defect data with hybrid storage."""
    print("Generating wafer defect images and data...")
    print("Using hybrid storage: thumbnails in MongoDB, full images in S3")
    
    # Initialize S3 uploader if configured
    s3_uploader = S3ImageUploader()
    if not s3_uploader.s3_client:
        print("⚠ S3 not configured. Full images will be stored as base64 in MongoDB")
    
    # Load anomaly events if available
    try:
        with open("anomaly_events.json", 'r') as f:
            anomaly_events = json.load(f)
    except FileNotFoundError:
        anomaly_events = []
    
    # Generate wafer defect data with S3 support
    wafer_defects = generate_wafer_defects_data(
        count=100, 
        anomaly_timestamps=anomaly_events,
        s3_uploader=s3_uploader
    )
    
    # Save wafer defect data
    output_file = "wafer_defects.json"
    with open(output_file, 'w') as f:
        json.dump(wafer_defects, f, indent=2)
    
    print(f"✓ Generated {len(wafer_defects)} wafer defect records")
    print(f"✓ Saved to {output_file}")
    
    # Print statistics
    patterns = {}
    total_yield = 0
    high_severity_count = 0
    s3_uploaded = 0
    
    for wafer in wafer_defects:
        pattern = wafer["defect_summary"]["defect_pattern"]
        patterns[pattern] = patterns.get(pattern, 0) + 1
        total_yield += wafer["defect_summary"]["yield_percentage"]
        if wafer["defect_summary"]["severity"] == "high":
            high_severity_count += 1
        if "full_image_url" in wafer.get("ink_map", {}):
            s3_uploaded += 1
    
    print("\nStatistics:")
    print(f"  - Average yield: {total_yield/len(wafer_defects):.1f}%")
    print(f"  - High severity defects: {high_severity_count}")
    print(f"  - Images uploaded to S3: {s3_uploaded}/{len(wafer_defects)}")
    print(f"  - Pattern distribution:")
    for pattern, count in patterns.items():
        print(f"    - {pattern}: {count} ({count/len(wafer_defects)*100:.1f}%)")
    
    # Sample records
    print(f"\nSample wafer defects (first 3):")
    for wafer in wafer_defects[:3]:
        print(f"  - {wafer['wafer_id']}: {wafer['defect_summary']['defect_pattern']} "
              f"pattern, {wafer['defect_summary']['yield_percentage']:.1f}% yield")


if __name__ == "__main__":
    main()