"""Mock draft copy, ported verbatim from the original frontend prototype
(frontend/src/App.tsx used to hardcode this as `DRAFTS` before the backend
existed). Kept here so the demo stays visually identical to what's already
been built while generate.py's real-LLM TODO gets filled in.

Shape: FIXTURE_DRAFTS[template_id][platform_id] -> list of variant strings.
Every (template, platform) pair has exactly 2 variants so `regenerate_variant`
always has somewhere to cycle to.
"""

FIXTURE_DRAFTS: dict[str, dict[str, list[str]]] = {
    "funding": {
        "twitter": [
            "We raised a $12M Series A led by Northwind, with participation from every investor who backed our seed.\n\nSame team, same problem, a lot more runway. Here's what we're building next ↓",
            "$12M Series A. Led by Northwind.\n\nWe spent two years making one thing work really well. Now we get to make it work for everyone.",
        ],
        "linkedin": [
            "Today we're announcing our $12M Series A, led by Northwind Capital.\n\nWhen we started, the pitch was a single claim: teams shouldn't need three tools and a spreadsheet to ship an announcement. That claim turned into 40,000 posts published through us last quarter.\n\nThis round goes to three places — model quality, integrations, and support. We're hiring across engineering and design.",
            "We've closed a $12M Series A led by Northwind Capital.\n\nThank you to the 900 teams who put their launches in our hands before we'd earned it. You shaped the roadmap more than any investor deck did.\n\nMore on where this goes in the comments.",
        ],
        "discord": [
            "**Series A — $12M** 🎉\n\nWe just closed our Series A led by Northwind. Nothing changes for you today except that we can ship faster and keep the free tier free.\n\nAMA in <#general> at 10am PT.",
            "Big one: we raised $12M. Details in the blog post, but the short version — the roadmap you've been voting on gets built twice as fast now.",
        ],
    },
    "acquisition": {
        "twitter": [
            "We're joining Meridian.\n\nThe product stays. The team stays. The thing we couldn't do alone — distribution — stops being the bottleneck.",
            "Acme has been acquired by Meridian.\n\nNo sunset date, no migration, no price change. Just more people working on the same product.",
        ],
        "linkedin": [
            "Acme is being acquired by Meridian.\n\nWe built this company around a narrow bet: that content pipelines should be auditable, not magical. Meridian made the same bet at a scale we couldn't reach on our own.\n\nFor customers: nothing changes this quarter. Your contracts, your data residency, and your support contacts stay exactly as they are.\n\nTo the team — all 34 of you — thank you. This one's yours.",
            "Some news: Acme is joining Meridian.\n\nI want to be direct about what this means. The product continues. The team continues. What changes is that we stop spending half our energy on things that aren't the product.\n\nDetails and FAQ in the first comment.",
        ],
        "discord": [
            "**We're joining Meridian.**\n\nWhat this means for you: nothing breaks, nothing gets deprecated, your workspace stays where it is.\n\nWe'll do a live Q&A Thursday — post questions in <#ask-anything> and we'll answer the hard ones first.",
            "Acme → Meridian. It's official.\n\nSelf-hosted builds keep shipping. Free tier stays. Ask us anything in the thread.",
        ],
    },
    "launch": {
        "twitter": [
            "Sources are live.\n\nDrop in a URL, pick a template, get platform-native drafts you can actually edit. No autoposting until you say so.",
            "New: point it at any link and get a Twitter, LinkedIn, and Discord draft in one pass.\n\nEverything is a preview until you approve it.",
        ],
        "linkedin": [
            "We're launching Sources today.\n\nThe problem we kept hearing: announcements live in five places — a blog post, a changelog, a deck, a thread someone wrote at midnight. Rewriting them by hand is where the message drifts.\n\nSources takes the links you already have and generates one draft per platform, each shaped for how people actually read there. You approve each one individually. Nothing publishes on its own.\n\nAvailable now on every plan.",
            "Sources is out.\n\nAdd the links. Pick a template. Review three drafts side by side. Approve the ones that sound like you.\n\nThat's the whole product. We think that's the point.",
        ],
        "discord": [
            "**Sources is live** ✨\n\nPaste a URL in the left panel, hit Generate, and you'll get a draft per platform. Regenerate as many times as you want — nothing posts until you approve.\n\nBug reports to <#feedback>, we're reading everything today.",
            "Shipped: Sources.\n\nURL in, drafts out, you stay in control of what goes live. Try it and tell us where it's wrong.",
        ],
    },
    "custom": {
        "twitter": [
            "Draft generated from your custom template.\n\nSwap this copy for whatever the pipeline returns — tone, length, and hashtags all come from the template you pasted.",
            "Custom template, variant 2.\n\nShorter, punchier, no hashtags. Regenerate again to keep cycling.",
        ],
        "linkedin": [
            "Draft generated from your custom template.\n\nThe structure here follows whatever you pasted above: opening hook, two supporting paragraphs, and a closing line with a single call to action.\n\nEdit freely — this is a preview, not a commitment.",
            "Custom template, variant 2.\n\nSame inputs, different shape: one paragraph, one concrete number, one ask. Useful when the announcement is small and you don't want to oversell it.",
        ],
        "discord": [
            "**Custom draft**\n\nCommunity tone, light formatting, one clear next step. Everything between the markers comes from your template.",
            "Custom draft, variant 2 — shorter, with the link up top and the context below it.",
        ],
    },
}
