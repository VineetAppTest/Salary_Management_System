# V70 Balloon Confirmations

Updated confirmation behavior:
- Major success / completion messages now use balloon-style indication consistently.
- `set_confirmation()` now defaults to balloon celebration.
- Balloon flag is reset cleanly after rendering.
- Database Health seed/export confirmations also use balloon-style feedback.
- Persistent DB health success message shows balloons; failures do not.
