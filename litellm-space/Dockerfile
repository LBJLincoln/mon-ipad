FROM ghcr.io/berriai/litellm:main-stable

# Copy config
COPY litellm_config.yaml /app/config.yaml

# HF Spaces requires port 7860
ENV PORT=7860
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:7860/health/liveliness || exit 1

# Run LiteLLM proxy — no database needed
CMD ["--config", "/app/config.yaml", "--port", "7860", "--host", "0.0.0.0", "--detailed_debug"]
