FROM ghcr.io/berriai/litellm:main-stable

# Copy config
COPY litellm-config.yaml /app/config.yaml

# HF Spaces requires port 7860
ENV PORT=7860
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -f http://localhost:7860/health || exit 1

CMD ["--config", "/app/config.yaml", "--port", "7860", "--host", "0.0.0.0"]
