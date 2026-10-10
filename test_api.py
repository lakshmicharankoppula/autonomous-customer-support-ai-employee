import os

from dotenv import load_dotenv
from openai import OpenAI


# Load variables from .env
load_dotenv()

# Create connection to OpenAI
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


# Send a simple request
response = client.responses.create(
    model="gpt-5.5-mini",
    input="Say hello and explain in one sentence what an API is."
)


# Print the model's response
print(response.output_text)
