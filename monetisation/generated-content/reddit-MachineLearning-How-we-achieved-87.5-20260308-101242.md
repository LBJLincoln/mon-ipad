TITLE: We hit 87.5% accuracy on 10K RAG questions using only free tools - here's how

BODY:
Hey ML community,

Thought I'd share our recent experiment with Retrieval-Augmented Generation (RAG) systems. We wanted to see how far we could push accuracy without spending a dime on infrastructure.

The setup:
- 10,000 RAG evaluation questions from a public benchmark
- 100% free infrastructure (no paid APIs, no premium services)
- Focus on optimization rather than raw compute

Results:
- 87.5% overall accuracy
- 95.2% on quantitative questions (math, stats, numerical reasoning)
- 82.1% on qualitative questions (open-ended, conceptual)

The interesting part? We achieved these numbers using entirely free tools:
- Open-source embedding models
- Free vector databases
- Public datasets for training
- Community-hosted models

What worked surprisingly well:
- Smart chunking strategies (we found optimal chunk sizes that reduced context switching)
- Hybrid search combining keyword and semantic matching
- Temperature tuning for different question types

What didn't:
- Trying to fine-tune on small datasets (actually hurt performance)
- Complex multi-hop reasoning chains (overfitting on training data)

The key insight was that for many RAG applications, you don't need massive infrastructure - you need the right architecture and optimization.

We've open-sourced everything, including our evaluation framework and configuration files. If you're working on RAG systems or just curious about pushing free tools to their limits, check it out:

https://github.com/LBJLincoln/mon-ipad/releases/tag/v1.0.0-products

Would love to hear your thoughts or similar experiences with free infrastructure!

What's the best accuracy you've achieved without paid services?