FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

# The Playwright image already ships a UID-1000 `pwuser`. Reuse it.
# HF Spaces require the container to run as a non-root user that owns the workdir.
RUN mkdir -p /app && chown -R pwuser:pwuser /app
USER pwuser
WORKDIR /app

ENV PATH=/home/pwuser/.local/bin:$PATH \
    DISPLAY=:99 \
    BROWSER_USE_HEADLESS=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    HOME=/home/pwuser

COPY --chown=pwuser:pwuser requirements.txt /app/
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=pwuser:pwuser app.py /app/

EXPOSE 7860
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
