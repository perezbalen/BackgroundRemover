# Model Quality Notes

Phase 2 uses `rembg[cpu]` for CPU-first background removal. `rembg` downloads models on first use and stores them in the configured model cache. The upstream README currently lists the Phase 2 candidate models and recommends reusing a session for batch processing.

Source: https://github.com/danielgatis/rembg

## Candidate Models

| Model | Intended Use | Initial Role |
| --- | --- | --- |
| `isnet-anime` | Anime/stylized character segmentation | Default first test for sprite-like subjects |
| `birefnet-general-lite` | Lightweight general background removal | Quality/speed candidate for video-derived sprites |
| `isnet-general-use` | General use cases | General quality baseline |
| `u2netp` | Lightweight U2Net | Fast fallback |
| `silueta` | Reduced-size U2Net-style model | Fast fallback |

## Benchmark Command

Run all Phase 2 candidates against the sample still image:

```bash
background-remover benchmark-image images/susan.png output/model-benchmark
```

Run a smaller first smoke test:

```bash
background-remover remove-image images/susan.png output/susan.isnet-anime.png --model isnet-anime --mask-output output/susan.isnet-anime.mask.png
```

Model files are cached locally by default in `.cache/rembg-models` to avoid writing into the user home directory.

## Results

| Model | Time | Visual Notes |
| --- | ---: | --- |
| `isnet-anime` | `0.96s` | Output generated; visual review pending |
| `birefnet-general-lite` | `8.00s` | Output generated; visual review pending |
| `isnet-general-use` | `0.97s` | Output generated; visual review pending |
| `u2netp` | `0.23s` | Output generated; visual review pending |
| `silueta` | `1.01s` | Output generated; visual review pending |

The first run for each model may include download time. Record steady-state timing after the model is already cached.

The timings above are cached steady-state inference timings on `images/susan.png` at `1448x1086`. They exclude model download time and model-session construction time. After caching all five candidate models, `.cache/rembg-models` is about `599 MB`.

Generated benchmark files:

- `output/model-benchmark/isnet-anime.png`
- `output/model-benchmark/birefnet-general-lite.png`
- `output/model-benchmark/isnet-general-use.png`
- `output/model-benchmark/u2netp.png`
- `output/model-benchmark/silueta.png`
- matching `.mask.png` files for each model
