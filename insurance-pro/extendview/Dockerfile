FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Pre-warm HuggingFace (Depth-Anything-V2-Small + SAM2.1-Hiera-Small) & TorchHub (DSINE)
# so GCP Cloud Run cold starts never download checkpoints at request time.
RUN python -c "from transformers import AutoImageProcessor, AutoModelForDepthEstimation, Sam2Processor, Sam2Model; \
    AutoImageProcessor.from_pretrained('depth-anything/Depth-Anything-V2-Small-hf'); \
    AutoModelForDepthEstimation.from_pretrained('depth-anything/Depth-Anything-V2-Small-hf'); \
    Sam2Processor.from_pretrained('facebook/sam2.1-hiera-small'); \
    Sam2Model.from_pretrained('facebook/sam2.1-hiera-small')"

COPY . .

ENV PORT=8501
ENV EXTENDVIEW_ENTRY=app.py

EXPOSE 8501

CMD ["sh", "-c", "streamlit run ${EXTENDVIEW_ENTRY} --server.port=${PORT} --server.address=0.0.0.0"]
