# Minimal devcontainer image for Plex-Organizer
# Ubuntu base + ffmpeg for faster-whisper.

FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    openjdk-25-jre-headless \
    pciutils \
    python-is-python3 \
    python3 \
    python3-pip \
    python3-venv \
    # --- GPU/NPU support (runtime detection) ---
    # Detect and enable all available GPU/NPU options: NVIDIA, Intel, AMD, Qualcomm (Adreno/Hexagon NPU)
    && set -e; \
    # NVIDIA GPU support (if present, requires host runtime)
    if lspci | grep -i nvidia; then \
    apt-get update && apt-get install -y --no-install-recommends \
    nvidia-cuda-toolkit nvidia-utils-535; \
    echo 'NVIDIA GPU detected, CUDA toolkit installed.'; \
    else \
    echo 'No NVIDIA GPU detected.'; \
    fi; \
    # Intel GPU support (if present)
    if lspci | grep -i 'VGA.*Intel'; then \
    apt-get update && apt-get install -y --no-install-recommends \
    clinfo intel-media-va-driver-non-free intel-opencl-icd; \
    echo 'Intel GPU detected, OpenCL/VAAPI installed.'; \
    else \
    echo 'No Intel GPU detected.'; \
    fi; \
    # AMD GPU support (if present)
    if lspci | grep -i 'VGA.*AMD\|VGA.*ATI'; then \
    apt-get update && apt-get install -y --no-install-recommends \
    mesa-opencl-icd ocl-icd-libopencl1; \
    echo 'AMD GPU detected, OpenCL installed.'; \
    else \
    echo 'No AMD GPU detected.'; \
    fi; \
    # Qualcomm Adreno GPU/Hexagon NPU support (if present)
    if lscpu | grep -qi 'qualcomm'; then \
    echo 'Qualcomm ARM CPU detected.'; \
    if lspci | grep -i 'adreno'; then \
    echo 'Qualcomm Adreno GPU detected. TODO: Install Adreno GPU drivers here when available.'; \
    else \
    echo 'No Adreno GPU detected.'; \
    fi; \
    if lspci | grep -i 'hexagon\|npu\|neural'; then \
    echo 'Qualcomm Hexagon NPU detected. TODO: Install Hexagon NPU drivers here when available.'; \
    else \
    echo 'No Hexagon NPU detected.'; \
    fi; \
    else \
    echo 'No Qualcomm ARM CPU detected.'; \
    fi; \
    # Generic NPU/AI accelerator stub (customize for your hardware)
    if lspci | grep -i 'neural\|npu'; then \
    echo 'NPU detected. Please install your NPU drivers here.'; \
    else \
    echo 'No NPU detected.'; \
    fi; \
    # Clean up
    && apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*