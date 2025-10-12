# arXiv Daily Summarizer - Language Configuration

## Configuration

The system supports three language modes for emails:

### Setting Language

Set the `EMAIL_LANGUAGE` environment variable:

```bash
# Chinese only (default)
export EMAIL_LANGUAGE=zh

# English only
export EMAIL_LANGUAGE=en

# Bilingual (both Chinese and English)
export EMAIL_LANGUAGE=both
```

Or in GitHub Secrets, add:
- Key: `EMAIL_LANGUAGE`
- Value: `zh`, `en`, or `both`

## Language Modes

### 1. Chinese Mode (`zh`) - DEFAULT
- Email title, labels, and UI in Chinese
- AI summary in Chinese
- This is the default if EMAIL_LANGUAGE is not set

### 2. English Mode (`en`)
- Email title, labels, and UI in English
- AI summary in English

### 3. Bilingual Mode (`both`)
- Email title and labels in English (primary)
- AI summary in BOTH Chinese AND English
- Chinese summary appears first, then English summary
- Useful for bilingual readers

## Examples

### Chinese Email
```
标题: arXiv 每日论文推送
日期提醒: 论文日期提醒
摘要: AI 摘要 (中文)
```

### English Email
```
Title: arXiv Daily Paper Digest
Date Notice: Date Notice
Summary: AI Summary (English)
```

### Bilingual Email
```
Title: arXiv Daily Paper Digest
Date Notice: Date Notice
Summary: 
  🇨🇳 中文摘要
  [Chinese summary text]
  
  🇬🇧 English Summary
  [English summary text]
```

## Testing Locally

```bash
# Test Chinese
export EMAIL_LANGUAGE=zh
python fetch_papers.py

# Test English
export EMAIL_LANGUAGE=en
python fetch_papers.py

# Test Bilingual
export EMAIL_LANGUAGE=both
python fetch_papers.py
```

## Note

- Bilingual mode takes longer as it generates TWO summaries per paper
- Bilingual mode may use more API quota
- Default is Chinese (`zh`) if not specified
