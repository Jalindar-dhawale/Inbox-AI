import os, sys
from pathlib import Path
TEST_DB=Path(__file__).parent/"test.db"
os.environ["DATABASE_PATH"]=str(TEST_DB)
os.environ["SESSION_SECRET"]="test-secret"
os.environ["TOKEN_ENCRYPTION_KEY"]="Z0FBQUFBQnY0QnVVRUt3WFpNZm40M3BOczhuN09WZFNZSDZxTXdGTzVfME9kOD0="
os.environ["LLM_PROVIDER"]="rules"
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
