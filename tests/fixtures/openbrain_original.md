# What Is OpenBrain? The Personal AI Memory Database You Own and Control

MindStudio Team · March 14, 2026

## Why AI Still Doesn't Remember You

Every time you start a new conversation with an AI assistant, you begin from zero. No context about your projects, your preferences, or your past decisions. Each session is a blank slate — even if you had a highly productive one yesterday.

OpenBrain is a direct response to that problem. It's a personal AI memory database you own and control, built on Supabase and connected to AI tools through MCP (Model Context Protocol). The idea is straightforward: your context should travel with you across tools and sessions, not get locked inside a single platform's ecosystem.

This article explains what OpenBrain is, how it works technically, why owning your memory layer matters, and how to get started.

## What OpenBrain Actually Is

OpenBrain is an open-source personal knowledge and memory system. At its core, it's a structured database schema running on Supabase — a PostgreSQL-backed platform you can either self-host or run through Supabase's cloud. An MCP server sits on top of that database, exposing memory tools to any compatible AI assistant.

The name frames the concept well. "Open" because it's not locked to any single AI platform or company. "Brain" because it functions as a shared external memory store that AI assistants can read from and write to over time.

This is meaningfully different from the memory features built into individual AI products. Those keep your data in their systems. OpenBrain puts the data in yours.

### What Makes It Different from Platform Memory

Most major AI assistants now offer some form of persistent memory:

- **ChatGPT Memory** stores facts about you within OpenAI's infrastructure
- **Claude Projects** maintain persistent context within Anthropic's platform
- **Gemini** retains user-level preferences inside Google's ecosystem

These features are genuinely useful, but they share a fundamental limitation: the data lives with the company. You can't carry it to a different AI. You can't query it programmatically. And you can't combine context from multiple tools into one coherent picture.

OpenBrain bypasses all of this. Your memory database is a Supabase project in your own account, connected to whichever AI tools you choose. It works with Claude, ChatGPT via API, OpenClaw, and any other MCP-compatible client. If the ecosystem grows or shifts, your memory goes with you.

## The Two Pillars: Supabase and MCP

OpenBrain combines two technologies to deliver this cross-platform memory. Understanding each one makes the overall architecture clearer.

### Supabase: Your Database Backbone

[Supabase](https://supabase.com) is an open-source backend platform built on PostgreSQL. It offers a hosted database, real-time subscriptions, authentication, and a REST/GraphQL API — all accessible from a free tier that's plenty for personal use.

For OpenBrain, Supabase is the persistent storage layer. When you set it up, a schema is provisioned in your Supabase project to handle different memory types: discrete facts, preferences, summaries, project context, task notes, and more.

Because it's standard PostgreSQL underneath, the data is queryable, exportable, and entirely portable. If you want to build something on top of it, run analytics against it, or migrate it somewhere else, you can. There's no proprietary format trapping you.

### MCP: The Protocol That Makes It Cross-Platform

MCP — Model Context Protocol — is an open standard for connecting AI models to external tools and data sources. Originally developed by Anthropic and now supported across a growing number of AI clients and platforms, MCP gives AI assistants a structured, predictable way to call external services mid-conversation.

Think of it as a standardized interface. An MCP server declares a set of tools — functions the AI can invoke. The client (Claude Desktop, for example) discovers those tools and can call them when relevant.

OpenBrain runs as an MCP server and exposes tools like:

- **Store memory** — save a piece of information with a category and tags
- **Search memory** — retrieve relevant entries by query
- **Get context** — pull recent or tagged context for a specific project or topic
- **Update memory** — modify an existing entry
- **Delete memory** — remove outdated or irrelevant information

A session in Claude writes your writing preferences to memory. The next day, a different AI client calls the search tool and retrieves them. Same database, different tool — the memory is persistent and portable.

## How OpenBrain Stores and Retrieves Memory

The system isn't just dumping raw text into a database. Memory entries are structured with metadata that makes retrieval practical and accurate.

### Memory Types and Structure

A typical OpenBrain instance organizes memory into categories:

**Facts** — Discrete, specific pieces of information. "Prefers concise bullet points over paragraphs." "Project deadline is end of Q3." "Uses Tailwind CSS for all front-end work."

**Summaries** — Condensed notes from longer conversations or research sessions. An AI can generate a summary at the end of a working session and save it for future reference.

**Decisions** — Records of choices made and why. Useful for ongoing projects where you don't want to re-explain tradeoffs.

**Project context** — Goals, constraints, stakeholders, current status. The background information an AI needs before being useful on a specific project.

**Custom categories** — Because you control the schema, you can extend it to fit your workflow.

### Semantic Search vs. Keyword Search

OpenBrain supports semantic search through Supabase's pgvector extension. When memories are stored, they can be embedded — converted into vector representations — so retrieval is based on meaning rather than exact keyword matches.

In practice, this means you can ask an AI to "find anything related to my content strategy" and get relevant results even if none of the stored memories use those exact words. The system finds entries with similar meaning.

If you're not using embeddings, PostgreSQL's built-in full-text search handles most use cases adequately.

## Setting Up Your Own OpenBrain

Getting OpenBrain running takes a few steps, but none of them require writing substantial custom code. Here's the general process:

**Step 1: Create a Supabase project.** Set up a new project at Supabase. The free tier is sufficient to start. Keep your project URL and API keys handy.

**Step 2: Run the schema migration.** OpenBrain provides a SQL script that creates the memory tables, indexes, and optional pgvector setup. Run it through the Supabase SQL editor.

**Step 3: Deploy the MCP server.** Clone the OpenBrain repository, install dependencies via npm, add your Supabase credentials to an environment file, and start the server. It runs locally and exposes the MCP tools on localhost.

**Step 4: Connect your AI clients.** Add the MCP server to your clients of choice. For Claude Desktop, this means a short entry in the MCP configuration file. For API-based workflows, point the MCP client connection at your local server address.

### What You'll Need

- A free Supabase account
- Node.js installed locally
- An MCP-compatible AI client
- Comfort running terminal commands and setting environment variables

Total setup time is usually under an hour. This isn't a one-click install, but it's accessible to anyone comfortable with basic developer tooling.

## Practical Uses for OpenBrain

The value of OpenBrain depends on how you integrate it into your actual workflow. A few patterns that work well in practice:

**Preference storage** — Store how you want things done. Writing tone, formatting style, technical preferences, communication habits. Any connected AI can retrieve these before drafting something on your behalf.

**Ongoing project context** — Keep a living brief for each active project: goals, constraints, key stakeholders, decisions made. Instead of re-explaining a project at the start of every session, the AI loads the context automatically.

**Research accumulation** — Use AI to research topics and store synthesized summaries in OpenBrain. Over time, you build up a searchable personal knowledge base rather than a pile of chat logs.

**Conversation continuity** — At the end of a complex working session, ask the AI to store a summary of what was covered and decided. Future sessions can pick up where you left off.

**Domain-specific instructions** — Store instructions keyed to specific contexts. "When working on client A, use this tone." "For this codebase, follow this architecture." The right instructions get retrieved based on what you're doing.

## Cross-Platform Memory in Practice

The broader promise of OpenBrain is what happens when multiple tools share the same memory layer.

A realistic workflow might look like:

1. You research a topic with Claude and ask it to store key findings in OpenBrain.
2. The next day, you open a different AI interface to draft a report. It queries OpenBrain and finds your research notes.
3. A background AI agent runs an automated email draft. It pulls your communication preferences from OpenBrain before composing.

Each of these tools is separate. But they're working from the same memory base — yours. That's the practical difference between platform memory and a personal memory database you control.

As more AI clients adopt MCP support, OpenBrain's usefulness grows without requiring any changes to your database setup.

## How MindStudio Fits Into Your AI Memory Setup

If you want to build AI agents or automated workflows on top of a personal memory layer — rather than just use chat interfaces — this is where [MindStudio](https://mindstudio.ai) connects naturally to the OpenBrain approach.

MindStudio is a no-code platform for building AI agents and workflows. It includes direct Supabase integration, which means you can build agents that read from and write to a personal memory database without running a local MCP server or managing infrastructure manually.

A basic memory-aware agent in MindStudio might:

- Accept text input from a user
- Query a Supabase memory table for relevant context
- Use that context to inform an AI-generated response
- Store new facts or summaries back to the database at the end of the session

You configure this visually using MindStudio's workflow builder. The [Supabase integration](https://mindstudio.ai/integrations) handles the data layer, and the AI reasoning step handles the generation. No code needed for the core flow.

MindStudio also supports agentic MCP servers — you can expose your MindStudio agents to other AI systems through MCP, or build agents that consume external MCP servers like OpenBrain. If you want to extend an existing OpenBrain setup with scheduled background agents or webhook-triggered workflows, MindStudio's agent types can connect directly to your setup.

The result is the same data ownership model OpenBrain is built around — your Supabase project, your schema, your data — combined with more flexibility in what you build around it.

You can try MindStudio free at [mindstudio.ai](https://mindstudio.ai).

## Frequently Asked Questions

### What is OpenBrain?

OpenBrain is an open-source personal AI memory database built on Supabase and exposed through MCP (Model Context Protocol). It lets MCP-compatible AI clients — including Claude, ChatGPT via API, OpenClaw, and others — read and write persistent memory stored in a database you own. Unlike built-in platform memory features, OpenBrain keeps your data in your own infrastructure and isn't tied to any single AI product.

### How is OpenBrain different from ChatGPT Memory?

ChatGPT Memory is a proprietary feature managed by OpenAI. The data lives in OpenAI's systems, you can't access it programmatically, and it only works within ChatGPT. OpenBrain stores memory in your own Supabase database — which you own, can query directly, and can connect to any MCP-compatible AI. It's platform-agnostic by design, and the data is fully portable.

### Do I need to know how to code to use OpenBrain?

You need comfort with developer basics — running terminal commands, configuring environment variables, and using npm. You don't need to write custom code from scratch. If you want a fully no-code path to similar functionality, you can achieve the core pattern (AI agents reading and writing to a Supabase memory table) using a platform like MindStudio, which handles the infrastructure layer visually.

### What is MCP and why does it matter for AI memory?

MCP (Model Context Protocol) is an open standard for connecting AI models to external tools and data. It provides a structured way for AI clients to discover and call tool functions — like storing or retrieving memory entries. MCP matters for AI memory because it means a single memory server can work with multiple different AI clients without a separate integration for each one. As more tools adopt MCP, a database like OpenBrain becomes more versatile without needing to change.

### Is my data secure with OpenBrain?

Your OpenBrain data lives in your own Supabase project. Security depends on how you configure it — including Row Level Security policies, API key management, and network access settings. Supabase follows standard cloud database security practices. Owning the database means you're not depending on a third party to protect your AI memory, but you're also responsible for securing it yourself. That's the core tradeoff of self-hosted personal data.

### Can OpenBrain work with automated agents, not just chat interfaces?

Yes. Because OpenBrain exposes tools through MCP, any system that can act as an MCP client — including automated background agents and orchestration frameworks — can read from and write to it. Memory isn't limited to interactive conversations. Scheduled agents, webhook-triggered workflows, and multi-step pipelines can all interact with the same memory database.

## Key Takeaways

- **OpenBrain** is a personal AI memory database built on Supabase and connected to AI tools via MCP — the open standard for AI tool access.
- Unlike platform memory features, OpenBrain stores your data in a database you own and control, with no vendor lock-in.
- MCP compatibility means any supporting AI client — Claude, ChatGPT, OpenClaw, and others — can read and write to the same memory layer.
- The system supports semantic search via pgvector, structured memory categories, and a flexible schema you can extend.
- For teams and builders who want to extend this into full AI workflows without local infrastructure, MindStudio provides a no-code path to building memory-aware agents on top of Supabase.

If persistent AI memory matters to how you work, [MindStudio](https://mindstudio.ai) is a practical place to start building around it — no infrastructure management required.
