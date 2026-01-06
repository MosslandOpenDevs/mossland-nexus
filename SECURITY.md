# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of Moss Nexus seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### How to Report

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please send an email to the Mossland team with:

1. **Description** of the vulnerability
2. **Steps to reproduce** the issue
3. **Potential impact** of the vulnerability
4. **Suggested fix** (if you have one)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 1 week
- **Resolution Timeline**: Depends on severity

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| Critical | Remote code execution, data breach | 24 hours |
| High | Authentication bypass, privilege escalation | 72 hours |
| Medium | Information disclosure, DoS | 1 week |
| Low | Minor issues | 2 weeks |

## Security Best Practices

### For Operators

#### 1. Environment Configuration

```bash
# Never commit .env file
echo ".env" >> .gitignore

# Set restrictive permissions
chmod 600 .env
```

#### 2. Discord Bot Token

- **Never share** your bot token
- **Regenerate** if exposed
- Use environment variables, not hardcoded values

#### 3. Network Security

```yaml
# docker-compose.yml - Bind Qdrant to localhost only
services:
  qdrant:
    ports:
      - "127.0.0.1:6333:6333"  # Only localhost
```

#### 4. Document Security

- Store sensitive documents outside `data/` folder
- Implement access controls at OS level
- Consider encryption for sensitive content

### For Developers

#### 1. Dependencies

```bash
# Regularly update dependencies
pip install --upgrade -r requirements.txt

# Check for vulnerabilities
pip install safety
safety check
```

#### 2. Input Validation

- Always validate user input from Discord
- Sanitize file paths in document loading
- Limit query length to prevent DoS

#### 3. Logging

- Never log sensitive information (tokens, passwords)
- Use appropriate log levels
- Rotate log files

## Security Architecture

### Data Flow Security

```
┌─────────────────────────────────────────────────────┐
│                  Security Boundaries                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │           External Network                   │   │
│  │  ┌─────────────────────────────────────────┐│   │
│  │  │        Discord API (HTTPS)              ││   │
│  │  │        - Bot token authentication       ││   │
│  │  │        - TLS encryption                 ││   │
│  │  └─────────────────────────────────────────┘│   │
│  └─────────────────────────────────────────────┘   │
│                        │                            │
│                        ▼                            │
│  ┌─────────────────────────────────────────────┐   │
│  │           Local Machine                      │   │
│  │  ┌─────────────────────────────────────────┐│   │
│  │  │  Moss Nexus Application                 ││   │
│  │  │  - Input validation                     ││   │
│  │  │  - Query sanitization                   ││   │
│  │  └─────────────────────────────────────────┘│   │
│  │                     │                        │   │
│  │  ┌────────┬────────┴────────┬────────┐     │   │
│  │  ▼        ▼                 ▼        ▼     │   │
│  │ ┌────┐ ┌──────┐       ┌──────┐ ┌───────┐  │   │
│  │ │data│ │Qdrant│       │Ollama│ │ .env  │  │   │
│  │ │ /  │ │:6333 │       │:11434│ │(secret│  │   │
│  │ └────┘ └──────┘       └──────┘ └───────┘  │   │
│  │ localhost only    localhost only  600 perm │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### What's Protected

| Asset | Protection |
|-------|------------|
| Discord Token | Environment variable, never logged |
| User Queries | Processed locally, not stored |
| Documents | Local filesystem, no cloud upload |
| Embeddings | Stored in local Qdrant only |
| LLM Inference | Local Ollama, no external API |

### What's NOT Protected (v1.0)

- No authentication for CLI access
- No rate limiting on queries
- No encryption at rest for Qdrant data
- No audit logging

## Known Security Considerations

### 1. Prompt Injection

**Risk**: Malicious queries could attempt to manipulate LLM behavior.

**Mitigation**:
- System prompt clearly defines boundaries
- Context is clearly separated from user input
- LLM instructed to only use provided context

### 2. Document Poisoning

**Risk**: Malicious content in documents could affect answers.

**Mitigation**:
- Only ingest trusted documents
- Review documents before adding to `data/`
- Implement content validation (future)

### 3. Discord Bot Permissions

**Risk**: Over-privileged bot could be exploited.

**Mitigation**:
- Request minimal permissions
- Only enable `message_content` intent
- Limit to specific channels if needed

## Security Checklist

### Before Deployment

- [ ] `.env` file has restrictive permissions (600)
- [ ] Discord bot token is not in code
- [ ] Qdrant is bound to localhost only
- [ ] `data/` folder has appropriate permissions
- [ ] Dependencies are up to date
- [ ] No debug mode in production

### Regular Maintenance

- [ ] Update dependencies monthly
- [ ] Rotate Discord bot token annually
- [ ] Review access logs
- [ ] Audit document contents
- [ ] Check for security advisories

## Contact

For security concerns, please contact the Mossland team through official channels:

- **X (Twitter)**: https://x.com/TheMossland
- **GitHub**: https://github.com/mossland
