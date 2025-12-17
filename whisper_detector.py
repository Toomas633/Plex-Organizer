"""Whisper-based language detection.

This module provides a small wrapper around the `faster-whisper` backend to
infer the spoken language of an audio file.

Notes:
    - This implementation targets CPU execution.
    - The returned probability is model-provided and should be treated as a
      heuristic confidence rather than a calibrated score.
    - Requires the `faster-whisper` package.
"""

from typing import Any, Dict, Optional, Tuple
from faster_whisper import WhisperModel

from config import get_whisper_model_size


class WhisperDetector:
    """Detect spoken language in audio via Whisper.

    The detector eagerly initializes a `faster_whisper.WhisperModel` (currently
    pinned to the small `tiny` model size) and exposes a single
    `detect_language()` helper that returns the detected language and a
    confidence-ish probability.

    Attributes:
        _backend: Name of the initialized backend (currently "faster-whisper")
            or `None` if initialization failed.
    """

    def __init__(
        self,
        *,
        compute_type: str = "int8",
        cpu_threads: Optional[int] = None,
    ):
        """Create a Whisper language detector.

        Args:
            compute_type: Compute type passed through to `WhisperModel`.
                Common values are "int8" (fast, low memory) and "float32"
                (more accurate, slower).
            cpu_threads: Optional thread count for CPU inference. When `None`,
                the backend chooses a default.

        Notes:
            The model is created eagerly in the constructor. If initialization
            fails (for example, missing dependencies), `_backend` remains
            `None`.
        """
        self._backend = None
        self._compute_type = compute_type
        self._cpu_threads = cpu_threads
        self._model = None

        self._backend = "faster-whisper"
        kwargs: Dict[str, Any] = {
            "device": "cpu",
            "compute_type": compute_type,
        }
        if cpu_threads is not None:
            kwargs["cpu_threads"] = cpu_threads

        try:
            model = get_whisper_model_size()
            self._model = WhisperModel(model, **kwargs)
        except (OSError, RuntimeError, ValueError):
            self._backend = None

    def is_available(self) -> bool:
        """Return True if the detector backend initialized successfully."""

        return bool(self._backend) and self._model is not None

    def detect_language(self, wav_path: str) -> Tuple[Optional[str], float]:
        """Detect the most likely language for the given audio.

        Args:
            wav_path: Path to a WAV (or generally audio) file supported by the
                backend.

        Returns:
            A tuple `(language, probability)` where:

            - `language` is an ISO 639-1/2 language code (for example "en") or
              `None` if the backend did not provide one.
            - `probability` is a float in $[0, 1]$ representing Whisper's
              estimated language probability.

        Notes:
            - This uses a low beam size and VAD filtering to keep detection
              fast.
            - The probability is not guaranteed to be calibrated; treat it as
              a relative confidence signal.
        """
        model = self._model
        if model is None:
            raise RuntimeError(
                "WhisperDetector backend is unavailable (model initialization failed)."
            )

        segments, info = model.transcribe(
            wav_path,
            beam_size=1,
            vad_filter=True,
            temperature=0,
        )

        try:
            next(iter(segments))
        except StopIteration:
            pass

        lang = getattr(info, "language", None)
        prob = float(getattr(info, "language_probability", 0.0) or 0.0)
        return (lang, prob)
