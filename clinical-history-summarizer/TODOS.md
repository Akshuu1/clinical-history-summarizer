# TODOS & Known Rough Edges

## Active
- [ ] Wire frontend to `/extract` API endpoint
- [ ] Add streaming response support for long notes
- [ ] Build evaluation runner (`scripts/evaluate.py`)
- [ ] Hand-label all 15 gold summaries
- [ ] Deploy backend to Render / Railway
- [ ] Deploy frontend to Vercel

## Future (Phase 2+)
- [ ] WhatsApp reminder stub endpoint (`/demo/schedule`)
- [ ] ABDM architecture documentation section in README
- [ ] Add structured logging (replace print with loguru)
- [ ] Add rate-limiting to the `/extract` endpoint
- [ ] Consider streaming the LLM response for UX

## Known limitations (document these in evaluation report)
- Model may hallucinate line numbers that partially match; validator catches this
- Very long notes (>4000 tokens) may need chunking — not yet implemented
- No disambiguation when same medication appears multiple times on different lines
