# Development Guide

This guide covers everything you need to know to develop and extend Moss Nexus.

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Project Structure](#project-structure)
- [Running Locally](#running-locally)
- [Testing](#testing)
- [Debugging](#debugging)
- [Common Development Tasks](#common-development-tasks)
- [Troubleshooting](#troubleshooting)

---

## Development Environment Setup

### Prerequisites

| Tool | Version | Installation |
|------|---------|--------------|
| Python | 3.11+ | `brew install python@3.11` |
| Docker | Latest | [Docker Desktop](https://docker.com/products/docker-desktop) |
| Ollama | Latest | `brew install ollama` |
| Git | Latest | `brew install git` |

### Step-by-Step Setup

#### 1. Clone Repository

```bash
git clone https://github.com/mossland/mossland-nexus.git
cd mossland-nexus
```

#### 2. Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Verify Python version
python --version  # Should show 3.11.x
```

#### 3. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies
pip install pytest pytest-asyncio pytest-cov
pip install black isort mypy ruff
pip install pre-commit ipython
```

#### 4. Environment Configuration

```bash
# Copy template
cp .env.example .env

# Edit configuration
nano .env  # or use your preferred editor
```

**Minimum required settings:**

```env
DISCORD_BOT_TOKEN=your_token_here
OLLAMA_MODEL=llama3.2:3b  # Use smaller model for dev
```

#### 5. Start Services

```bash
# Start Qdrant
docker-compose up -d

# Verify Qdrant is running
curl http://localhost:6333/health

# Start Ollama (in separate terminal)
ollama serve

# Pull development model (smaller, faster)
ollama pull llama3.2:3b
```

#### 6. Verify Installation

```bash
# Check configuration
python main.py config

# Run with smaller model for testing
OLLAMA_MODEL=llama3.2:3b python main.py test
```

---

## Project Structure

```
mossland-nexus/
│
├── main.py                 # CLI entry point
├── requirements.txt        # Production dependencies
├── docker-compose.yml      # Qdrant configuration
├── .env.example           # Environment template
├── .env                   # Local configuration (git-ignored)
│
├── src/                   # Source code
│   ├── __init__.py       # Package initialization
│   ├── config.py         # Pydantic settings
│   ├── ingest.py         # Document ingestion pipeline
│   ├── rag_chain.py      # RAG retrieval & generation
│   ├── api.py            # FastAPI REST API & Web server
│   └── bot.py            # Discord bot interface
│
├── static/               # Web UI assets
│   ├── index.html        # Main chat interface
│   ├── css/
│   │   └── style.css     # UI styles
│   └── js/
│       └── app.js        # Chat logic
│
├── data/                  # Document storage
│   └── *.pdf, *.md, *.txt
│
├── docs/                  # Documentation
│   ├── ARCHITECTURE.md   # System architecture
│   └── DEVELOPMENT.md    # This file
│
├── tests/                 # Test files (to be added)
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_ingest.py
│   └── test_rag_chain.py
│
└── logs/                  # Log files (git-ignored)
```

### Key Files Explained

| File | Purpose |
|------|---------|
| `main.py` | CLI interface, parses commands, calls appropriate modules |
| `src/config.py` | Centralized configuration using Pydantic Settings |
| `src/ingest.py` | Loads documents, chunks them, stores in Qdrant |
| `src/rag_chain.py` | Retrieves relevant docs, generates answers via LLM |
| `src/api.py` | FastAPI server with REST endpoints and Web UI |
| `src/bot.py` | Discord bot commands and event handlers |

---

## Running Locally

### Development Mode

```bash
# Use smaller model for faster iteration
export OLLAMA_MODEL=llama3.2:3b
export LOG_LEVEL=DEBUG

# Run CLI test mode
python main.py test
```

### Web API Server (Development)

```bash
# Run with debug logging
LOG_LEVEL=DEBUG python main.py api

# Access points:
# - Web UI: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - Health: http://localhost:8000/api/health
```

### Discord Bot (Development)

```bash
# Run with debug logging
LOG_LEVEL=DEBUG python main.py bot
```

### Document Ingestion

```bash
# Add test documents
echo "Test document content" > data/test.txt

# Run ingestion
python main.py ingest

# Verify in Qdrant
curl http://localhost:6333/collections/moss_knowledge
```

---

## Testing

### Test Structure

```bash
tests/
├── conftest.py          # Shared fixtures
├── test_config.py       # Configuration tests
├── test_ingest.py       # Ingestion pipeline tests
├── test_rag_chain.py    # RAG chain tests
└── test_bot.py          # Discord bot tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_rag_chain.py

# Run with verbose output
pytest -v

# Run only fast tests (skip slow LLM tests)
pytest -m "not slow"
```

### Writing Tests

```python
# tests/test_rag_chain.py
import pytest
from src.rag_chain import RAGChain, RAGResponse

class TestRAGChain:
    @pytest.fixture
    def rag_chain(self):
        """Create RAG chain instance for testing."""
        return RAGChain()

    def test_query_returns_response(self, rag_chain):
        """Test that query returns RAGResponse object."""
        response = rag_chain.query("What is MOC?")

        assert isinstance(response, RAGResponse)
        assert response.answer is not None
        assert response.query == "What is MOC?"

    @pytest.mark.slow
    def test_query_with_context(self, rag_chain):
        """Test query uses document context."""
        response = rag_chain.query("What is the total supply?")

        # Should reference source documents
        assert len(response.source_documents) > 0
```

### Test Configuration

```python
# tests/conftest.py
import pytest
from unittest.mock import Mock, patch

@pytest.fixture(scope="session")
def mock_ollama():
    """Mock Ollama for faster tests."""
    with patch('src.rag_chain.Ollama') as mock:
        mock.return_value.invoke.return_value = "Mocked response"
        yield mock

@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        {"content": "MOC is the token of Mossland", "source": "test.md"},
        {"content": "Total supply is 500 million", "source": "test.md"},
    ]
```

---

## Debugging

### Enable Debug Logging

```bash
# Via environment variable
LOG_LEVEL=DEBUG python main.py test

# Or in .env file
LOG_LEVEL=DEBUG
```

### Interactive Debugging

```python
# Add breakpoint in code
def query(self, question: str) -> RAGResponse:
    breakpoint()  # Debugger stops here
    ...
```

```bash
# Run with debugger
python -m pdb main.py test
```

### IPython for Exploration

```bash
# Start IPython
ipython

# Import and explore
>>> from src.rag_chain import get_rag_chain
>>> rag = get_rag_chain()
>>> response = rag.query("Test question")
>>> print(response.answer)
```

### Qdrant Inspection

```bash
# List collections
curl http://localhost:6333/collections

# Get collection info
curl http://localhost:6333/collections/moss_knowledge

# Search manually
curl -X POST http://localhost:6333/collections/moss_knowledge/points/search \
  -H "Content-Type: application/json" \
  -d '{"vector": [0.1, 0.2, ...], "limit": 5}'
```

### Ollama Debugging

```bash
# Check available models
ollama list

# Test model directly
ollama run llama3.2:3b "Hello, how are you?"

# Check Ollama logs
tail -f ~/.ollama/logs/server.log
```

---

## Common Development Tasks

### Adding a New Document Loader

```python
# src/ingest.py

from langchain_community.document_loaders import CSVLoader

def _load_documents(self) -> List[Document]:
    documents = []

    # ... existing loaders ...

    # Add CSV loader
    csv_loader = DirectoryLoader(
        str(data_path),
        glob="**/*.csv",
        loader_cls=CSVLoader,
        show_progress=True
    )
    try:
        csv_docs = csv_loader.load()
        documents.extend(csv_docs)
        logger.info(f"CSV documents: {len(csv_docs)}")
    except Exception as e:
        logger.warning(f"CSV load error: {e}")

    return documents
```

### Adding a New Discord Command

```python
# src/bot.py

@bot.command(name="help_kr", help="한국어 도움말을 표시합니다.")
async def help_korean(ctx: commands.Context):
    """Display help message in Korean."""
    embed = discord.Embed(
        title="Moss Nexus 도움말",
        description="사용 가능한 명령어:",
        color=discord.Color.blue()
    )
    embed.add_field(name="!ask [질문]", value="모스랜드에 대해 질문합니다", inline=False)
    embed.add_field(name="!search [검색어]", value="문서를 검색합니다", inline=False)
    embed.add_field(name="!status", value="시스템 상태를 확인합니다", inline=False)

    await ctx.send(embed=embed)
```

### Adding a New API Endpoint

```python
# src/api.py

from pydantic import BaseModel

# Define request/response models
class SummaryRequest(BaseModel):
    document_id: str

class SummaryResponse(BaseModel):
    summary: str
    document_id: str

# Add new endpoint
@app.post("/api/summary", response_model=SummaryResponse)
async def get_document_summary(request: SummaryRequest):
    """
    Generate a summary for a specific document.
    """
    # Your implementation here
    return SummaryResponse(
        summary="Document summary...",
        document_id=request.document_id
    )
```

### Modifying the Web UI

```javascript
// static/js/app.js

// Add new function for custom feature
async function fetchSummary(documentId) {
    const response = await fetch('/api/summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_id: documentId })
    });
    return await response.json();
}
```

```css
/* static/css/style.css */

/* Add custom styles */
.summary-card {
    padding: var(--spacing-md);
    background-color: var(--color-bg);
    border-radius: var(--radius-md);
    border-left: 3px solid var(--color-primary);
}
```

### Modifying the System Prompt

```python
# src/rag_chain.py

SYSTEM_PROMPT_TEMPLATE = """당신은 모스랜드(Mossland)의 커뮤니티 매니저 'Moss Nexus'입니다.

[Your custom rules here]

[Context]
{context}

[Question]
{question}

[Answer]
"""
```

### Adding Configuration Options

```python
# src/config.py

class Settings(BaseSettings):
    # ... existing settings ...

    # New setting
    max_response_length: int = Field(
        default=2000,
        description="Maximum response length in characters"
    )
```

Then use in code:

```python
from src.config import settings

if len(response) > settings.max_response_length:
    response = response[:settings.max_response_length] + "..."
```

---

## Troubleshooting

### Common Issues

#### 1. "ModuleNotFoundError: No module named 'src'"

```bash
# Ensure you're in project root
cd /path/to/mossland-nexus

# Or add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### 2. "MPS backend not available"

```python
# Check MPS availability
import torch
print(torch.backends.mps.is_available())  # Should be True
print(torch.backends.mps.is_built())      # Should be True

# If False, reinstall PyTorch
pip uninstall torch
pip install torch
```

#### 3. "Connection refused" for Qdrant

```bash
# Check if container is running
docker ps | grep qdrant

# If not running, start it
docker-compose up -d

# Check logs
docker-compose logs qdrant
```

#### 4. "Model not found" for Ollama

```bash
# List models
ollama list

# Pull if missing
ollama pull llama3.2:3b

# Check Ollama is running
curl http://localhost:11434/api/tags
```

#### 5. Discord Bot Not Responding

```bash
# Check token is set
echo $DISCORD_BOT_TOKEN

# Verify intents in Discord Developer Portal
# - MESSAGE CONTENT INTENT must be enabled

# Check bot logs
LOG_LEVEL=DEBUG python main.py bot
```

### Performance Issues

#### Slow Embedding Generation

```python
# Use smaller batch size if memory constrained
encode_kwargs={'batch_size': 16}  # Default is 32

# Or use CPU if MPS is problematic
model_kwargs={'device': 'cpu'}
```

#### Slow LLM Response

```bash
# Use smaller model for development
OLLAMA_MODEL=llama3.2:3b python main.py test

# Or reduce context
num_ctx=4096  # Default is 8192
```

---

## IDE Setup

### VS Code

`.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.mypyEnabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "[python]": {
        "editor.codeActionsOnSave": {
            "source.organizeImports": true
        }
    }
}
```

### PyCharm

1. Set Project Interpreter to `./venv/bin/python`
2. Enable Black formatter
3. Configure pytest as test runner

---

## Resources

- [LangChain Python Docs](https://python.langchain.com/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Ollama API Reference](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
