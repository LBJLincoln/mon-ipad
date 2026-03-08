#!/usr/bin/env python3
"""Create Stripe products + payment links for Nomos AI digital products."""
import os
import stripe

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

PRODUCTS = [
    {
        "name": "RAG Debug Playbook",
        "description": (
            "79 battle-tested fixes from 80+ production debugging sessions. "
            "3 diagnostic flowcharts, 12 anti-patterns, LLM behavior profiles. "
            "The definitive guide to fixing RAG pipelines in production."
        ),
        "price_cents": 4700,  # $47
        "currency": "usd",
    },
    {
        "name": "AI Agent Context Kit",
        "description": (
            "Production-grade context files for AI coding agents. "
            "RAG architecture reference, debug context, prompt templates. "
            "Drop into any repo and let Claude/Cursor/Copilot understand your stack instantly."
        ),
        "price_cents": 2700,  # $27
        "currency": "usd",
    },
]


def create_products():
    results = []
    for prod_spec in PRODUCTS:
        # Create the product
        product = stripe.Product.create(
            name=prod_spec["name"],
            description=prod_spec["description"],
            metadata={"source": "nomos-ai", "type": "digital"},
        )
        print(f"✓ Product created: {product.name} (id: {product.id})")

        # Create a price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=prod_spec["price_cents"],
            currency=prod_spec["currency"],
        )
        print(f"  Price: ${prod_spec['price_cents']/100:.0f} (id: {price.id})")

        # Create a Payment Link (instant checkout, no storefront needed)
        payment_link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            after_completion={"type": "redirect", "redirect": {"url": "https://nomos42.gumroad.com"}},
            metadata={"product": prod_spec["name"]},
        )
        print(f"  Payment Link: {payment_link.url}")
        print()

        results.append({
            "product_id": product.id,
            "price_id": price.id,
            "payment_link": payment_link.url,
            "name": prod_spec["name"],
            "price": f"${prod_spec['price_cents']/100:.0f}",
        })

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("NOMOS AI — Stripe Product Setup")
    print("=" * 60)
    print()

    if not stripe.api_key:
        print("ERROR: STRIPE_SECRET_KEY not set. Run: source .env.local")
        exit(1)

    results = create_products()

    print("=" * 60)
    print("SUMMARY — Share these links to sell immediately:")
    print("=" * 60)
    for r in results:
        print(f"  {r['name']} ({r['price']}): {r['payment_link']}")
    print()
    print("No storefront needed. Each link = full Stripe Checkout.")
    print("Customers pay → you get paid to your Stripe account.")
