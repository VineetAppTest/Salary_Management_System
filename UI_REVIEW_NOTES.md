# V18 UI Review Notes

Issues addressed:
- Login button contrast fixed with high-contrast white text on dark blue button.
- Button hover/focus contrast fixed.
- Header/top text cropping reduced using safer line-height and spacing.
- Mobile spacing improved.
- Sidebar hiding made less disruptive.
- Cards and buttons made larger and more touch-friendly.
- Top navigation and role cards refined for mobile and desktop.

Streamlit workarounds used:
- Avoid left-sidebar dependency.
- Route with session_state.
- Keep navigation inside the main page.
- Use CSS-contained cards.
- Avoid aggressive negative margins or tight line-height.
