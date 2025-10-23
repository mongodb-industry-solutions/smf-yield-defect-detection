// Sample wafer document from MongoDB (W_0001 - oldest wafer with embeddings)
// This is pre-loaded to avoid API call delays when showing MongoDB structure

export const SAMPLE_WAFER_MONGO_DATA = {
  "metadata": {
    "document_size_bytes": 34424,
    "embedding_dimensions": 1024,
    "embedding_model": "voyage-multimodal-3",
    "embedding_type": "multimodal",
    "has_die_map": true,
    "die_map_size": "25x25",
    "defect_count": 10,
    "collection_name": "wafer_defects",
    "database_name": "smf-yield-defect"
  },
  "document": {
    "_id": "68c19b53036808d6ab31417c",
    "wafer_id": "W_0001",
    "lot_id": "LOT_2025_001",
    "inspection_timestamp": "2025-08-11T21:05:26.061826Z",
    "ink_map": {
      "thumbnail_size": "150x150",
      "format": "PNG",
      "full_image_url": "s3://ist-manufacturing-semiconductor/wafer/wafer_images/W_0001_edge_20250910_210526.png",
      "full_image_size": "500x500"
    },
    "defect_summary": {
      "total_dies": 625,
      "failed_dies": 112,
      "yield_percentage": 82.08,
      "defect_pattern": "edge",
      "severity": "high"
    },
    "die_map": "[[1.0, 0.0, 1.0, ...], [1.0, 0.0, 0.0, ...], ... (25x25 grid)]",
    "defects": [
      {
        "type": "process",
        "location": { "x": 11, "y": 1 },
        "size_um": 1.04,
        "confidence": 0.98
      },
      {
        "type": "process",
        "location": { "x": 12, "y": 1 },
        "size_um": 0.97,
        "confidence": 0.91
      },
      {
        "type": "process",
        "location": { "x": 15, "y": 1 },
        "size_um": 0.77,
        "confidence": 0.85
      },
      {
        "type": "process",
        "location": { "x": 6, "y": 2 },
        "size_um": 0.24,
        "confidence": 0.99
      },
      {
        "type": "process",
        "location": { "x": 8, "y": 2 },
        "size_um": 1.93,
        "confidence": 0.92
      },
      {
        "type": "process",
        "location": { "x": 18, "y": 2 },
        "size_um": 1.01,
        "confidence": 0.97
      },
      {
        "type": "process",
        "location": { "x": 5, "y": 3 },
        "size_um": 0.81,
        "confidence": 0.9
      },
      {
        "type": "process",
        "location": { "x": 9, "y": 3 },
        "size_um": 0.85,
        "confidence": 0.99
      },
      {
        "type": "process",
        "location": { "x": 11, "y": 3 },
        "size_um": 1.73,
        "confidence": 0.96
      },
      {
        "type": "process",
        "location": { "x": 13, "y": 3 },
        "size_um": 1.48,
        "confidence": 0.96
      }
    ],
    "description": "Edge die failures detected, possible handling damage or process uniformity issue in CMP_TOOL_01",
    "process_context": {
      "last_process_step": "CMP",
      "equipment_used": ["CMP_TOOL_01"],
      "slurry_batch": "SB_2025_018",
      "clean_cycle": 186
    },
    "embedding": [
      0.052978515625, -0.041748046875, 0.00063323974609375, -0.052001953125,
      0.01239013671875, 0.00982666015625, -0.01611328125, -0.0230712890625,
      0.03515625, -0.003143310546875, 0.0159912109375, -0.0296630859375,
      "... (1012 more values - total 1024 dimensions)"
    ],
    "embedding_model": "voyage-multimodal-3",
    "embedding_type": "multimodal",
    "embedding_updated_at": "2025-09-11T18:25:24.785000",
    "embedding_note": "Full 1024-dimensional vector from voyage-multimodal-3 model used for semantic similarity search"
  }
};
