"""
Simple Bedrock Client - Just calls AWS Bedrock, no complications
Assumes you've already done: aws sso login --profile <your-profile>
"""

import boto3
import json
import logging
import os

logger = logging.getLogger(__name__)

# Global client - created once, reused forever
_bedrock_runtime = None

def get_bedrock_runtime():
    """Get or create Bedrock runtime client (uses your existing AWS session)"""
    global _bedrock_runtime

    if _bedrock_runtime is None:
        import time
        # Just create a simple client - uses default credential chain (your SSO session)
        region = os.getenv("AWS_REGION", "us-east-1")
        logger.info(f"🔧 Creating Bedrock runtime client in {region}")

        start = time.time()
        _bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
        end = time.time()

        logger.info(f"✅ Bedrock client created in {end - start:.2f} seconds")

    return _bedrock_runtime


def call_claude(prompt: str, model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
                temperature: float = 0.2, max_tokens: int = 300) -> str:
    """
    Call Claude via Bedrock - simple and direct

    Args:
        prompt: The prompt to send to Claude
        model_id: Claude model ID
        temperature: Sampling temperature
        max_tokens: Max tokens in response

    Returns:
        Claude's text response
    """
    client = get_bedrock_runtime()

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }
        ]
    })

    response = client.invoke_model(
        modelId=model_id,
        body=body
    )

    response_body = json.loads(response['body'].read())
    return response_body['content'][0]['text']
