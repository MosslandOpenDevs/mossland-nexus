# Contributing to Moss Nexus

First off, thank you for considering contributing to Moss Nexus! It's people like you that make Moss Nexus such a great tool.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Style Guidelines](#style-guidelines)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

## Code of Conduct

This project and everyone participating in it is governed by our commitment to providing a welcoming and inclusive environment. By participating, you are expected to uphold this standard. Please be respectful and constructive in all interactions.

### Our Standards

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

### Prerequisites

Before you begin, ensure you have:

- Python 3.11 or higher
- Docker Desktop installed
- Ollama installed
- Git configured with your name and email
- A GitHub account

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/mossland-nexus.git
   cd mossland-nexus
   ```
3. Add the upstream remote:
   ```bash
   git remote add upstream https://github.com/mossland/mossland-nexus.git
   ```

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates.

When creating a bug report, include:

- **Clear title** describing the issue
- **Steps to reproduce** the behavior
- **Expected behavior** vs **actual behavior**
- **Environment details**:
  - OS version (e.g., macOS Sequoia 15.2)
  - Python version
  - Chip (e.g., M4 Pro)
  - RAM
- **Logs** (if applicable)
- **Screenshots** (if applicable)

### Suggesting Features

Feature suggestions are welcome! Please include:

- **Clear description** of the feature
- **Use case** - why is this feature needed?
- **Proposed implementation** (if you have ideas)
- **Alternatives considered**

### Code Contributions

Good first issues are labeled with `good first issue`. These are great starting points for new contributors.

Areas where we especially welcome contributions:

- **New document loaders** (DOCX, HTML, etc.)
- **Additional LLM providers** (local alternatives)
- **Performance optimizations**
- **Test coverage**
- **Documentation improvements**
- **Internationalization**

## Development Setup

### 1. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-asyncio black isort mypy ruff
```

### 3. Set Up Pre-commit Hooks (Optional)

```bash
pip install pre-commit
pre-commit install
```

### 4. Start Services

```bash
# Start Qdrant
docker-compose up -d

# Ensure Ollama is running
ollama serve
```

### 5. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

## Style Guidelines

### Python Code Style

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line length**: 100 characters max
- **Imports**: Use `isort` for sorting
- **Formatting**: Use `black` for code formatting
- **Type hints**: Required for public functions
- **Docstrings**: Google style docstrings

```python
def process_document(
    file_path: str,
    chunk_size: int = 800,
    overlap: int = 100
) -> list[Document]:
    """
    Process a document file and return chunks.

    Args:
        file_path: Path to the document file.
        chunk_size: Size of each chunk in characters.
        overlap: Overlap between chunks.

    Returns:
        List of Document chunks with metadata.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If chunk_size is less than overlap.
    """
    ...
```

### Linting Commands

```bash
# Format code
black src/ tests/
isort src/ tests/

# Check types
mypy src/

# Lint
ruff check src/
```

### Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(bot): add slash command support for Discord

fix(ingest): handle UTF-8 encoding errors in PDF files

docs(readme): add Korean translation section
```

## Pull Request Process

### 1. Create a Branch

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/issue-number-description
```

### 2. Make Your Changes

- Write clean, documented code
- Add tests for new functionality
- Update documentation if needed
- Ensure all tests pass

### 3. Commit Your Changes

```bash
git add .
git commit -m "feat(scope): description"
```

### 4. Push and Create PR

```bash
git push origin feat/your-feature-name
```

Then create a Pull Request on GitHub.

### 5. PR Requirements

Your PR should:

- [ ] Have a clear title and description
- [ ] Reference related issues (e.g., "Fixes #123")
- [ ] Pass all CI checks
- [ ] Have no merge conflicts
- [ ] Include tests for new features
- [ ] Update documentation if needed

### 6. Code Review

- Address reviewer feedback promptly
- Be open to suggestions
- Explain your decisions when asked

## Project Structure

```
mossland-nexus/
├── src/
│   ├── __init__.py      # Package init
│   ├── config.py        # Configuration management
│   ├── ingest.py        # Document ingestion
│   ├── rag_chain.py     # RAG pipeline
│   └── bot.py           # Discord bot
├── tests/               # Test files
│   ├── test_ingest.py
│   ├── test_rag_chain.py
│   └── test_bot.py
├── docs/                # Documentation
├── data/                # Document storage
└── main.py              # Entry point
```

## Community

### Getting Help

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and ideas
- **X (Twitter)**: [@TheMossland](https://x.com/TheMossland)

### Recognition

Contributors will be recognized in:
- The project README
- Release notes
- Our community highlights

---

Thank you for contributing to Moss Nexus! 🌿
