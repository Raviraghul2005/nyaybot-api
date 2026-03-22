import os
import sys
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
with open(env_path, "a") as f:
    f.write("\nQDRANT_URL=https://708d2e44-fffc-4833-b0f4-d90048d18696.eu-central-1-0.aws.cloud.qdrant.io:6333\n")
    f.write("QDRANT_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.V-ALUKuqSzNKznyb-tcGGKFzZtNYx6QAPcR0Jb3NiVY\n")
print("[+] Secrets appended to .env successfully.")
