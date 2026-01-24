# Check Review Console - Landing Page

Marketing landing page for Check Review Console, the check exception processing platform for community banks.

## Quick Start

1. Open `index.html` in a browser — no build step required
2. Or serve locally: `npx serve .`

## Structure

```
├── index.html          # Main landing page
├── css/
│   └── custom.css      # Custom style overrides
├── js/
│   └── form.js         # Form validation & submission
└── assets/
    └── images/         # Screenshots and graphics
```

## Setup Checklist

- [ ] Replace Formspree placeholder with your form ID
- [ ] Add product screenshots to `assets/images/`
- [ ] Update hero screenshot placeholder
- [ ] Configure analytics (Plausible/Fathom)
- [ ] Deploy to Cloudflare Pages or Netlify

## Form Setup

1. Create a free account at [Formspree](https://formspree.io)
2. Create a new form and get your form ID
3. Replace `YOUR_FORM_ID` in `index.html` with your ID

## Deployment

### Cloudflare Pages
1. Connect this repo to Cloudflare Pages
2. Set build output directory to `/`
3. No build command needed

### Netlify
1. Connect this repo to Netlify
2. Publish directory: `/`
3. No build command needed

## Tech Stack

- HTML5
- Tailwind CSS (via CDN)
- Vanilla JavaScript
