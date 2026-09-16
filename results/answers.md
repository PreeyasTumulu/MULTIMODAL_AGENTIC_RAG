# Answer leaderboard

Generated from `results/answers.jsonl` by `analyst.answer_eval`. Never edit by hand.

> **acc** the true figure at any printed scale; growth within 1 point.
> **wrong** answered but incorrect - the column that matters.
> **cited** a citation names the benchmark's single anchor element, so it is strict.
> **refusal** on generated unanswerable questions.

| run | llm | k | acc | value | growth | wrong | cited | false refusal | refusal | calls/q | tokens/q | p50 s | bench | git |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b-k10-e70492 | `groq/openai/gpt-oss-120b` | 10 | 0.386 | 0.382 | 0.400 | 0.614 | 0.295 | 0.000 | 1.000 | 1.9 | 2594 | 5.5 | `2c4aedf3` | `bcafe64-dirty` |
| llama3.2-k10-2d390e | `ollama/llama3.2` | 10 | 0.227 | 0.235 | 0.200 | 0.568 | 0.318 | 0.204 | 1.000 | 2.1 | 2909 | 4.6 | `2c4aedf3` | `d85d168-dirty` |
