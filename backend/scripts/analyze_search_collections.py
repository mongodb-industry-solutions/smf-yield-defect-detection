#!/usr/bin/env python3
"""
Analyze MongoDB collections for search service optimization
Focuses on search-relevant metrics: schemas, indexes, data quality, and improvement opportunities
"""

import asyncio
import os
import json
from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict, Counter
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv()


class SearchServiceAnalyzer:
    """Analyzes MongoDB collections for search service optimization"""

    def __init__(self):
        self.mongodb_uri = os.getenv("MONGODB_URI")
        self.database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")
        self.client = None
        self.db = None

        # Collections to analyze (used in unified search)
        self.collections = [
            "wafer_defects",
            "historical_knowledge"
        ]

    async def connect(self):
        """Connect to MongoDB"""
        self.client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.client[self.database_name]
        print(f"✓ Connected to MongoDB: {self.database_name}")

    async def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            stats = await self.db.command("collStats", collection_name)
            return {
                "count": stats.get("count", 0),
                "size_mb": round(stats.get("size", 0) / (1024 * 1024), 2),
                "avg_obj_size": stats.get("avgObjSize", 0),
                "total_index_size_mb": round(stats.get("totalIndexSize", 0) / (1024 * 1024), 2),
                "num_indexes": stats.get("nindexes", 0)
            }
        except Exception as e:
            print(f"  ⚠ Error getting stats: {e}")
            return {}

    async def get_indexes(self, collection_name: str) -> List[Dict[str, Any]]:
        """Get all database indexes"""
        try:
            collection = self.db[collection_name]
            indexes = await collection.list_indexes().to_list(length=None)
            return indexes
        except Exception as e:
            return []

    async def get_search_indexes(self, collection_name: str) -> List[Dict[str, Any]]:
        """Get Atlas Search indexes"""
        try:
            result = await self.db.command({
                "aggregate": collection_name,
                "pipeline": [{"$listSearchIndexes": {}}],
                "cursor": {}
            })
            indexes = result.get('cursor', {}).get('firstBatch', [])
            return indexes
        except Exception as e:
            return []

    async def analyze_schema_for_search(self, collection_name: str) -> Dict[str, Any]:
        """Analyze schema focusing on searchable fields"""
        collection = self.db[collection_name]

        # Get sample documents
        documents = await collection.find().limit(100).to_list(length=100)

        if not documents:
            return {"fields": {}, "recommendations": []}

        # Track field information
        field_info = defaultdict(lambda: {
            "count": 0,
            "types": Counter(),
            "sample_values": [],
            "is_searchable": False,
            "is_filterable": False,
            "max_length": 0,
            "is_array": False,
            "is_embedding": False
        })

        def analyze_field(doc, prefix=""):
            """Recursively analyze document fields"""
            for key, value in doc.items():
                if key == "_id":
                    continue

                full_key = f"{prefix}.{key}" if prefix else key
                info = field_info[full_key]
                info["count"] += 1

                if value is None:
                    info["types"]["null"] += 1
                    continue

                # Determine type and characteristics
                if isinstance(value, str):
                    info["types"]["string"] += 1
                    info["max_length"] = max(info["max_length"], len(value))
                    info["is_searchable"] = True
                    info["is_filterable"] = len(value) < 100  # Short strings good for filters

                    if len(info["sample_values"]) < 5:
                        info["sample_values"].append(value[:100])

                elif isinstance(value, (int, float)):
                    info["types"]["number"] += 1
                    info["is_filterable"] = True
                    if len(info["sample_values"]) < 5:
                        info["sample_values"].append(value)

                elif isinstance(value, bool):
                    info["types"]["boolean"] += 1
                    info["is_filterable"] = True

                elif isinstance(value, list):
                    info["types"]["array"] += 1
                    info["is_array"] = True

                    if value:
                        # Check if it's a numeric array (possible embedding)
                        if all(isinstance(x, (int, float)) for x in value[:10]):
                            if len(value) > 100:  # Likely an embedding
                                info["is_embedding"] = True
                                info["embedding_dim"] = len(value)
                        else:
                            # Array of objects or strings
                            info["is_searchable"] = isinstance(value[0], str)

                elif isinstance(value, dict):
                    info["types"]["object"] += 1
                    # Recursively analyze nested objects
                    analyze_field(value, full_key)

                elif isinstance(value, datetime):
                    info["types"]["datetime"] += 1
                    info["is_filterable"] = True

        # Analyze all documents
        for doc in documents:
            analyze_field(doc)

        # Convert to regular dict and calculate percentages
        schema = {}
        for field, info in field_info.items():
            dominant_type = info["types"].most_common(1)[0][0] if info["types"] else "unknown"
            presence_pct = round((info["count"] / len(documents)) * 100, 2)

            schema[field] = {
                "type": dominant_type,
                "presence_pct": presence_pct,
                "is_searchable": info["is_searchable"],
                "is_filterable": info["is_filterable"],
                "is_array": info["is_array"],
                "is_embedding": info["is_embedding"],
                "max_length": info["max_length"],
                "sample_values": info["sample_values"][:3]
            }

            if info["is_embedding"]:
                schema[field]["embedding_dim"] = info.get("embedding_dim", 0)

        return {"fields": schema, "document_count": len(documents)}

    async def analyze_embeddings(self, collection_name: str) -> Dict[str, Any]:
        """Analyze embedding coverage and quality"""
        collection = self.db[collection_name]

        total_docs = await collection.count_documents({})
        docs_with_embeddings = await collection.count_documents({"embedding": {"$exists": True}})

        # Get sample embedding
        sample_doc = await collection.find_one({"embedding": {"$exists": True}})

        if not sample_doc or "embedding" not in sample_doc:
            return {
                "has_embeddings": False,
                "coverage_pct": 0,
                "issues": ["No embeddings found - vector search will not work!"]
            }

        embedding = sample_doc["embedding"]
        issues = []
        warnings = []

        # Check dimensions
        dimensions = len(embedding) if isinstance(embedding, list) else 0
        if dimensions != 1024:
            issues.append(f"Unexpected embedding dimension: {dimensions} (expected 1024 for voyage-multimodal-3)")

        # Check coverage
        coverage_pct = round((docs_with_embeddings / total_docs * 100), 2) if total_docs > 0 else 0
        if coverage_pct < 100:
            warnings.append(f"Only {coverage_pct}% of documents have embeddings - search quality degraded")

        # Check embedding model
        embedding_model = sample_doc.get("embedding_model", "Unknown")
        embedding_type = sample_doc.get("embedding_type", "Unknown")

        if embedding_model != "voyage-multimodal-3":
            warnings.append(f"Embedding model mismatch: {embedding_model} (expected: voyage-multimodal-3)")

        return {
            "has_embeddings": True,
            "dimensions": dimensions,
            "model": embedding_model,
            "type": embedding_type,
            "total_docs": total_docs,
            "docs_with_embeddings": docs_with_embeddings,
            "coverage_pct": coverage_pct,
            "sample_values": embedding[:5] if isinstance(embedding, list) else None,
            "issues": issues,
            "warnings": warnings
        }

    async def check_index_coverage(self, collection_name: str, schema: Dict, text_index: Dict, vector_index: Dict) -> Dict[str, Any]:
        """Check which searchable fields are covered by indexes"""

        # Get searchable and filterable fields from schema
        searchable_fields = [f for f, info in schema.items() if info.get("is_searchable") and not info.get("is_embedding")]
        filterable_fields = [f for f, info in schema.items() if info.get("is_filterable")]

        # Get indexed fields from text search index
        indexed_text_fields = []
        if text_index:
            definition = text_index.get("latestDefinition", text_index.get("definition", {}))
            mappings = definition.get("mappings", {})
            if mappings.get("dynamic"):
                indexed_text_fields = ["ALL_FIELDS (dynamic mapping)"]
            else:
                fields = mappings.get("fields", {})
                indexed_text_fields = list(fields.keys())

        # Get indexed fields from vector search index
        has_vector_index = bool(vector_index)
        vector_index_path = None
        if vector_index:
            definition = vector_index.get("latestDefinition", vector_index.get("definition", {}))
            vector_fields = definition.get("fields", [])
            if vector_fields:
                vector_index_path = vector_fields[0].get("path")

        # Find gaps
        missing_from_text_index = []
        for field in searchable_fields:
            if field not in indexed_text_fields and "ALL_FIELDS" not in str(indexed_text_fields):
                missing_from_text_index.append(field)

        missing_filters = []
        for field in filterable_fields[:10]:  # Check top 10 filterable fields
            if field not in indexed_text_fields and "ALL_FIELDS" not in str(indexed_text_fields):
                missing_filters.append(field)

        return {
            "searchable_fields_count": len(searchable_fields),
            "filterable_fields_count": len(filterable_fields),
            "indexed_text_fields": indexed_text_fields,
            "has_vector_index": has_vector_index,
            "vector_index_path": vector_index_path,
            "missing_from_text_index": missing_from_text_index[:10],  # Limit to 10
            "missing_filter_fields": missing_filters[:5]  # Limit to 5
        }

    async def get_value_distribution(self, collection_name: str, field: str) -> Dict[str, Any]:
        """Get value distribution for a field (useful for understanding filter selectivity)"""
        try:
            collection = self.db[collection_name]

            # Get distinct values with counts
            pipeline = [
                {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 20}
            ]

            results = await collection.aggregate(pipeline).to_list(length=20)

            total_docs = await collection.count_documents({})
            distinct_count = len(results)

            distribution = []
            for r in results:
                value = r["_id"]
                count = r["count"]
                pct = round((count / total_docs * 100), 2) if total_docs > 0 else 0
                distribution.append({"value": value, "count": count, "pct": pct})

            # Calculate selectivity (lower is better for filters)
            selectivity = round((distinct_count / total_docs * 100), 2) if total_docs > 0 else 0

            return {
                "distinct_count": distinct_count,
                "selectivity_pct": selectivity,
                "distribution": distribution
            }
        except Exception as e:
            return {"error": str(e)}

    async def analyze_collection(self, collection_name: str) -> Dict[str, Any]:
        """Comprehensive analysis focused on search optimization"""
        print(f"\n{'='*60}")
        print(f"Analyzing: {collection_name}")
        print(f"{'='*60}")

        # Get basic stats
        print("  → Getting statistics...")
        stats = await self.get_collection_stats(collection_name)

        # Get indexes
        print("  → Analyzing indexes...")
        db_indexes = await self.get_indexes(collection_name)
        search_indexes = await self.get_search_indexes(collection_name)

        # Find text and vector search indexes
        text_index = None
        vector_index = None

        for idx in search_indexes:
            idx_type = idx.get("type", "")
            if "search" in idx_type.lower() and "vector" not in idx_type.lower():
                text_index = idx
            elif "vector" in idx_type.lower():
                vector_index = idx

        # Analyze schema
        print("  → Analyzing schema...")
        schema_analysis = await self.analyze_schema_for_search(collection_name)
        schema = schema_analysis["fields"]

        # Analyze embeddings
        print("  → Analyzing embeddings...")
        embedding_analysis = await self.analyze_embeddings(collection_name)

        # Check index coverage
        print("  → Checking index coverage...")
        index_coverage = await self.check_index_coverage(collection_name, schema, text_index, vector_index)

        # Analyze important filterable fields
        print("  → Analyzing filter fields...")
        filter_analysis = {}

        important_filters = {
            "wafer_defects": ["equipment_id", "defect_summary.defect_pattern", "defect_summary.severity"],
            "historical_knowledge": ["document_type", "metadata.process_area", "metadata.defect_type"]
        }

        if collection_name in important_filters:
            for field in important_filters[collection_name]:
                if field in schema:
                    filter_analysis[field] = await self.get_value_distribution(collection_name, field)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            collection_name, stats, schema, embedding_analysis,
            text_index, vector_index, index_coverage, filter_analysis
        )

        return {
            "collection_name": collection_name,
            "statistics": stats,
            "schema": schema,
            "embedding_analysis": embedding_analysis,
            "text_search_index": text_index,
            "vector_search_index": vector_index,
            "index_coverage": index_coverage,
            "filter_field_analysis": filter_analysis,
            "recommendations": recommendations
        }

    def _generate_recommendations(self, collection_name: str, stats: Dict, schema: Dict,
                                 embedding_analysis: Dict, text_index: Dict, vector_index: Dict,
                                 index_coverage: Dict, filter_analysis: Dict) -> List[Dict[str, str]]:
        """Generate specific recommendations for improving search"""
        recommendations = []

        # Embedding recommendations
        if not embedding_analysis.get("has_embeddings"):
            recommendations.append({
                "priority": "CRITICAL",
                "category": "Embeddings",
                "issue": "No embeddings found in collection",
                "recommendation": f"Run: uv run python scripts/regenerate_wafer_embeddings.py for {collection_name}",
                "impact": "Vector search will fail completely without embeddings"
            })
        elif embedding_analysis.get("coverage_pct", 0) < 100:
            recommendations.append({
                "priority": "HIGH",
                "category": "Embeddings",
                "issue": f"Only {embedding_analysis['coverage_pct']}% of documents have embeddings",
                "recommendation": "Regenerate embeddings for all documents",
                "impact": "Incomplete search results, some documents never returned"
            })

        if embedding_analysis.get("issues"):
            for issue in embedding_analysis["issues"]:
                recommendations.append({
                    "priority": "HIGH",
                    "category": "Embeddings",
                    "issue": issue,
                    "recommendation": "Fix embedding dimension or model mismatch",
                    "impact": "Vector search may return incorrect similarity scores"
                })

        # Text index recommendations
        if not text_index:
            recommendations.append({
                "priority": "CRITICAL",
                "category": "Text Search Index",
                "issue": "No Atlas Search text index found",
                "recommendation": f"Run: uv run python scripts/create_text_search_indexes.py",
                "impact": "Text search mode will fail"
            })
        else:
            # Check for missing fields
            missing = index_coverage.get("missing_from_text_index", [])
            if missing:
                recommendations.append({
                    "priority": "MEDIUM",
                    "category": "Text Search Index",
                    "issue": f"Searchable fields not indexed: {', '.join(missing[:5])}",
                    "recommendation": "Add these fields to text search index definition",
                    "impact": "Cannot search on these fields using text search mode"
                })

            missing_filters = index_coverage.get("missing_filter_fields", [])
            if missing_filters:
                recommendations.append({
                    "priority": "MEDIUM",
                    "category": "Text Search Index",
                    "issue": f"Filter fields not indexed: {', '.join(missing_filters)}",
                    "recommendation": "Add filter fields to text index for efficient filtering",
                    "impact": "Inefficient filtering, slower queries"
                })

        # Vector index recommendations
        if not vector_index:
            recommendations.append({
                "priority": "CRITICAL",
                "category": "Vector Search Index",
                "issue": "No vector search index found",
                "recommendation": f"Run: uv run python scripts/mdb_vector_search_idx_creator.py",
                "impact": "Vector search mode will fail"
            })
        else:
            vector_path = index_coverage.get("vector_index_path")
            if vector_path != "embedding":
                recommendations.append({
                    "priority": "HIGH",
                    "category": "Vector Search Index",
                    "issue": f"Vector index path is '{vector_path}', expected 'embedding'",
                    "recommendation": "Update vector index to use path: 'embedding'",
                    "impact": "Vector search will fail to find documents"
                })

        # Filter selectivity recommendations
        for field, analysis in filter_analysis.items():
            selectivity = analysis.get("selectivity_pct", 0)
            if selectivity < 1:  # Very low cardinality
                recommendations.append({
                    "priority": "LOW",
                    "category": "Query Optimization",
                    "issue": f"Field '{field}' has low cardinality ({selectivity}% unique)",
                    "recommendation": f"This field is excellent for filtering (only {analysis.get('distinct_count')} distinct values)",
                    "impact": "Use this field in compound queries for better performance"
                })

        # Check for fields that should exist but don't
        if collection_name == "historical_knowledge":
            if "equipment_id" in [f for f in schema.keys()]:
                # Check if it's actually populated
                pass  # Equipment ID exists
            else:
                recommendations.append({
                    "priority": "MEDIUM",
                    "category": "Schema",
                    "issue": "Field 'equipment_id' defined in text index but doesn't exist in documents",
                    "recommendation": "Either add equipment_id to documents OR remove from text index definition",
                    "impact": "Text search filters on equipment_id will never match"
                })

            if "document_type" not in [f for f in schema.keys() if "document_type" in f]:
                recommendations.append({
                    "priority": "HIGH",
                    "category": "Schema",
                    "issue": "Missing 'document_type' field used in search filters",
                    "recommendation": "Ensure all knowledge documents have document_type field",
                    "impact": "Cannot filter by document type (rca_report vs troubleshooting_guide)"
                })

        return recommendations

    async def run(self, output_file: str):
        """Run analysis and generate report"""
        await self.connect()

        print("\n" + "="*80)
        print("MONGODB SEARCH SERVICE OPTIMIZATION ANALYSIS")
        print("="*80)

        # Get server info
        server_info = await self.client.server_info()
        db_stats = await self.db.command("dbStats")

        db_info = {
            "database": self.database_name,
            "mongodb_version": server_info.get("version"),
            "size_mb": round(db_stats.get("dataSize", 0) / (1024 * 1024), 2),
            "analyzed_at": datetime.now().isoformat()
        }

        # Analyze collections
        analyses = []
        for collection_name in self.collections:
            try:
                analysis = await self.analyze_collection(collection_name)
                analyses.append(analysis)
            except Exception as e:
                print(f"\n❌ Error analyzing {collection_name}: {e}")
                import traceback
                traceback.print_exc()

        # Generate markdown report
        print("\n" + "="*60)
        print("Generating Report...")
        print("="*60)

        markdown = self._format_report(db_info, analyses)

        # Save report
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(markdown)

        print(f"\n✅ Analysis Complete!")
        print(f"📄 Report saved to: {output_file}")
        print(f"📊 Collections analyzed: {len(analyses)}")

        # Print summary
        total_recommendations = sum(len(a["recommendations"]) for a in analyses)
        critical_issues = sum(len([r for r in a["recommendations"] if r["priority"] == "CRITICAL"]) for a in analyses)

        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Total Recommendations: {total_recommendations}")
        print(f"Critical Issues: {critical_issues}")

        if critical_issues > 0:
            print(f"\n⚠️  {critical_issues} CRITICAL issues found! Check report for details.")

        self.client.close()

    def _format_report(self, db_info: Dict, analyses: List[Dict]) -> str:
        """Format analysis as markdown report"""

        md = f"""# MongoDB Search Service Optimization Analysis

**Generated**: {db_info['analyzed_at']}
**Database**: {db_info['database']}
**MongoDB Version**: {db_info['mongodb_version']}
**Database Size**: {db_info['size_mb']} MB

---

## Executive Summary

This report analyzes MongoDB collections used by the unified search service to identify optimization opportunities, missing indexes, schema issues, and data quality problems.

**Collections Analyzed**: {', '.join([a['collection_name'] for a in analyses])}

"""

        # Overall recommendations summary
        all_recommendations = []
        for analysis in analyses:
            all_recommendations.extend(analysis["recommendations"])

        critical_count = len([r for r in all_recommendations if r["priority"] == "CRITICAL"])
        high_count = len([r for r in all_recommendations if r["priority"] == "HIGH"])
        medium_count = len([r for r in all_recommendations if r["priority"] == "MEDIUM"])

        md += f"""### Issues Found
- 🔴 **Critical**: {critical_count}
- 🟠 **High**: {high_count}
- 🟡 **Medium**: {medium_count}
- 🟢 **Low**: {len(all_recommendations) - critical_count - high_count - medium_count}

---

"""

        # Critical issues first
        if critical_count > 0:
            md += "## 🚨 Critical Issues (Fix Immediately)\n\n"
            for analysis in analyses:
                critical = [r for r in analysis["recommendations"] if r["priority"] == "CRITICAL"]
                if critical:
                    md += f"### {analysis['collection_name']}\n\n"
                    for rec in critical:
                        md += f"**{rec['category']}**: {rec['issue']}\n"
                        md += f"- **Fix**: {rec['recommendation']}\n"
                        md += f"- **Impact**: {rec['impact']}\n\n"

            md += "---\n\n"

        # Detailed analysis for each collection
        for analysis in analyses:
            md += self._format_collection_analysis(analysis)

        return md

    def _format_collection_analysis(self, analysis: Dict) -> str:
        """Format single collection analysis"""

        collection_name = analysis["collection_name"]
        stats = analysis["statistics"]
        schema = analysis["schema"]
        embedding = analysis["embedding_analysis"]
        index_coverage = analysis["index_coverage"]

        md = f"""## Collection: `{collection_name}`

### Overview
- **Documents**: {stats.get('count', 0):,}
- **Size**: {stats.get('size_mb', 0)} MB
- **Avg Document**: {stats.get('avg_obj_size', 0):,} bytes
- **Indexes**: {stats.get('num_indexes', 0)} database + {2 if analysis['text_search_index'] and analysis['vector_search_index'] else 1 if analysis['text_search_index'] or analysis['vector_search_index'] else 0} search

### Embedding Status
"""

        if embedding.get("has_embeddings"):
            coverage = embedding.get("coverage_pct", 0)
            status_icon = "✅" if coverage == 100 else "⚠️"

            md += f"""{status_icon} **Embeddings Configured**
- **Model**: {embedding.get('model', 'Unknown')}
- **Dimensions**: {embedding.get('dimensions', 0)}
- **Type**: {embedding.get('type', 'Unknown')}
- **Coverage**: {embedding.get('docs_with_embeddings', 0):,} / {embedding.get('total_docs', 0):,} ({coverage}%)

"""
            if embedding.get("warnings"):
                md += "**Warnings**:\n"
                for warning in embedding["warnings"]:
                    md += f"- ⚠️ {warning}\n"
                md += "\n"

        else:
            md += "❌ **No embeddings found** - Vector search will not work!\n\n"

        # Index status
        md += "### Search Index Status\n\n"

        # Text search index
        if analysis['text_search_index']:
            text_idx = analysis['text_search_index']
            md += f"✅ **Text Search Index**: `{text_idx.get('name')}`\n"
            md += f"- Status: {text_idx.get('status', 'Unknown')}\n"

            # Show indexed fields
            definition = text_idx.get("latestDefinition", text_idx.get("definition", {}))
            mappings = definition.get("mappings", {})

            if mappings.get("dynamic"):
                md += "- Fields: **Dynamic** (all fields indexed)\n"
            else:
                fields = list(mappings.get("fields", {}).keys())
                md += f"- Fields: {', '.join(f'`{f}`' for f in fields)}\n"
        else:
            md += "❌ **Text Search Index**: Not found\n"

        md += "\n"

        # Vector search index
        if analysis['vector_search_index']:
            vec_idx = analysis['vector_search_index']
            md += f"✅ **Vector Search Index**: `{vec_idx.get('name')}`\n"
            md += f"- Status: {vec_idx.get('status', 'Unknown')}\n"

            definition = vec_idx.get("latestDefinition", vec_idx.get("definition", {}))
            vector_fields = definition.get("fields", [])
            if vector_fields:
                vec_field = vector_fields[0]
                md += f"- Path: `{vec_field.get('path')}`\n"
                md += f"- Dimensions: {vec_field.get('numDimensions')}\n"
                md += f"- Similarity: {vec_field.get('similarity')}\n"
        else:
            md += "❌ **Vector Search Index**: Not found\n"

        md += "\n"

        # Index coverage analysis
        md += "### Index Coverage Analysis\n\n"
        md += f"- Searchable fields in schema: {index_coverage['searchable_fields_count']}\n"
        md += f"- Filterable fields in schema: {index_coverage['filterable_fields_count']}\n"

        missing_text = index_coverage.get("missing_from_text_index", [])
        if missing_text:
            md += f"\n**Missing from text index**:\n"
            for field in missing_text[:10]:
                sample = schema.get(field, {}).get("sample_values", [])
                sample_str = f" (e.g., {sample[0]})" if sample else ""
                md += f"- `{field}`{sample_str}\n"

        md += "\n"

        # Filter field analysis
        if analysis["filter_field_analysis"]:
            md += "### Filter Field Analysis\n\n"
            md += "Cardinality and distribution of key filter fields:\n\n"

            for field, field_analysis in analysis["filter_field_analysis"].items():
                if "error" in field_analysis:
                    continue

                distinct = field_analysis.get("distinct_count", 0)
                selectivity = field_analysis.get("selectivity_pct", 0)

                md += f"#### `{field}`\n"
                md += f"- Distinct values: {distinct}\n"
                md += f"- Selectivity: {selectivity}% (lower is better for filters)\n"

                distribution = field_analysis.get("distribution", [])
                if distribution:
                    md += "\nTop values:\n"
                    md += "| Value | Count | % of Total |\n"
                    md += "|-------|-------|------------|\n"

                    for item in distribution[:10]:
                        value = str(item["value"])[:50]
                        md += f"| `{value}` | {item['count']:,} | {item['pct']}% |\n"

                md += "\n"

        # Schema details
        md += "### Schema Details\n\n"
        md += "Key fields and their search characteristics:\n\n"
        md += "| Field | Type | Presence | Searchable | Filterable | Notes |\n"
        md += "|-------|------|----------|------------|------------|-------|\n"

        # Show important fields first
        important_first = sorted(schema.items(), key=lambda x: (
            not x[1].get("is_embedding"),  # Embeddings first
            not x[1].get("is_searchable"),  # Then searchable
            not x[1].get("is_filterable"),  # Then filterable
            x[0]  # Then alphabetically
        ))

        for field, info in important_first[:30]:  # Limit to 30 most important
            field_type = info.get("type", "unknown")
            presence = f"{info.get('presence_pct', 0)}%"

            searchable = "✓" if info.get("is_searchable") else ""
            filterable = "✓" if info.get("is_filterable") else ""

            notes = []
            if info.get("is_embedding"):
                notes.append(f"🔢 {info.get('embedding_dim', 0)}D vector")
            if info.get("max_length", 0) > 1000:
                notes.append("📝 Long text")
            if info.get("is_array"):
                notes.append("📦 Array")

            notes_str = ", ".join(notes)

            md += f"| `{field}` | {field_type} | {presence} | {searchable} | {filterable} | {notes_str} |\n"

        md += "\n"

        # Recommendations
        if analysis["recommendations"]:
            md += "### Recommendations\n\n"

            # Group by priority
            by_priority = {}
            for rec in analysis["recommendations"]:
                priority = rec["priority"]
                if priority not in by_priority:
                    by_priority[priority] = []
                by_priority[priority].append(rec)

            for priority in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
                if priority in by_priority:
                    icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}[priority]
                    md += f"#### {icon} {priority} Priority\n\n"

                    for rec in by_priority[priority]:
                        md += f"**{rec['category']}**: {rec['issue']}\n"
                        md += f"- Fix: {rec['recommendation']}\n"
                        md += f"- Impact: {rec['impact']}\n\n"

        md += "---\n\n"

        return md


async def main():
    """Main entry point"""
    output_file = "backend/plans/improve_search/mongodb-search-optimization-analysis.md"

    analyzer = SearchServiceAnalyzer()
    await analyzer.run(output_file)


if __name__ == "__main__":
    asyncio.run(main())
