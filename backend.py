import asyncio
import os
import random
import time
import sys
import logging
from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import uvicorn
from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.workflow import Context
from llama_index.llms.google_genai import GoogleGenAI
from toolbox_llamaindex import ToolboxClient
from prompts import DVD_RENTAL_PROMPT

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s',
)

# Create a logger for our app
logger = logging.getLogger('dvd_rental_assistant')
logger.setLevel(logging.INFO)

# Normal traceback limit
sys.tracebacklimit = 10


#For more complex prompts, I use the following:
#prompt=DVD_RENTAL_PROMPT

#For simpler prompts, I use the following:
prompt=''''
You are a helpful DVD rental assistant. Your job is to:
1. Help customers find movies using search-films-by-title
2. Check if movies are available using get-film-availability
3. Show movie details with get-film-details
4. Format responses with emojis: 🎬 for titles, ⭐ for ratings, 💲 for prices
5. Always end with a friendly follow-up question
'''

app = FastAPI(title="DVD Rental Assistant API", description="API for DVD rental operations powered by Google Gemini")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your frontend domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Try to connect to the Toolbox
        client = ToolboxClient("http://127.0.0.1:5000")
        tools = client.load_toolset()
        return {"status": "healthy", "toolbox_connected": True}
    except Exception as e:
        return {"status": "unhealthy", "toolbox_connected": False, "error": str(e)}

# Store user contexts
user_contexts = {}

# Rate limiting configuration
RATE_LIMIT_BASE_DELAY = 5  # Increased from 3 to 5 seconds
MAX_RETRIES = 5  # Increased from 3 to 5
REQUEST_COOLDOWN = 2  # Cooldown period between requests

async def run_with_retry(agent, query, ctx, max_retries=MAX_RETRIES):
    """Run the agent with exponential backoff retry for rate limit errors"""
    retry_count = 0
    
    while True:
        try:
            # Add a small cooldown between requests
            await asyncio.sleep(REQUEST_COOLDOWN)
            return await agent.run(user_msg=query, ctx=ctx)
        except Exception as e:
            # Check for rate limit errors only
            if "429 Too Many Requests" in str(e) and retry_count < max_retries:
                retry_count += 1
                # Exponential backoff with jitter
                delay = RATE_LIMIT_BASE_DELAY * (2 ** retry_count) + random.uniform(1.0, 2.0)
                logger.info(f"Rate limit hit (attempt {retry_count}/{max_retries}), retrying in {delay:.1f} seconds...")
                await asyncio.sleep(delay)
            else:
                # For other errors or max retries exceeded, raise but with cleaner message
                if "429 Too Many Requests" in str(e):
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded after {retry_count} retries. Please wait a few minutes before trying again."
                    )
                else:
                    # Extract only the essential error message
                    error_msg = str(e).split('\n')[-1] if '\n' in str(e) else str(e)
                    raise HTTPException(status_code=500, detail=f"Error: {error_msg}")

def get_agent():
    llm = GoogleGenAI(
        model="gemini-1.5-pro",
        vertexai_config={"project": "vertex-ai-experminent", "location": "us-central1"},
    )
    
    client = ToolboxClient("http://127.0.0.1:5000")
    tools = client.load_toolset()

    return AgentWorkflow.from_tools_or_functions(
        tools,
        llm=llm,
        system_prompt=prompt,
    )

class ChatRequest(BaseModel):
    message: str
    user_id: str = "user"

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    user_id = request.user_id
    message = request.message
    
    logger.info(f"Received message from user {user_id}: {message}")
    
    # Create or retrieve user context
    if user_id not in user_contexts:
        agent = get_agent()
        user_contexts[user_id] = {"agent": agent, "context": Context(agent)}
        logger.info(f"Created new context for user {user_id}")
    
    agent = user_contexts[user_id]["agent"]
    ctx = user_contexts[user_id]["context"]
    
    try:
        # Add a small delay to reduce rate limit issues
        await asyncio.sleep(1)
        logger.info(f"Processing request from user {user_id}")
        response = await run_with_retry(agent, message, ctx)
        logger.info(f"Successfully processed request from user {user_id}")
        return ChatResponse(response=str(response))
    except Exception as e:
        logger.error(f"Error processing request from user {user_id}: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/reset-context/{user_id}")
async def reset_context(user_id: str):
    if user_id in user_contexts:
        del user_contexts[user_id]
        logger.info(f"Reset context for user {user_id}")
        return {"status": "success", "message": f"Context for user {user_id} has been reset"}
    raise HTTPException(status_code=404, detail=f"No context found for user {user_id}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
