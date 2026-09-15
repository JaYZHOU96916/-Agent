FROM python:3.11-slim

# Runtime image deliberately contains only the Python standard library in Phase 0.
# Later phases add pinned analytics dependencies after vulnerability review.
USER 65534:65534
WORKDIR /workspace
ENTRYPOINT ["python"]
