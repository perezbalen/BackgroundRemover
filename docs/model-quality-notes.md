# Model Quality Notes

Phase 2 uses `rembg[cpu]` for CPU-first background removal. `rembg` downloads models on first use and stores them in the configured model cache. The upstream README currently lists the model candidates and recommends reusing a session for batch processing.

Source: https://github.com/danielgatis/rembg

`bgbye` was reviewed as a model reference. Its UI lists Bria RMBG1.4,
InSPyReNet, U2Net, Tracer-B7, BASNet, DeepLabV3, U2Net Human, Open RMBG,
ISNET-DIS, and ISNET-Anime. Its backend uses CUDA-oriented code paths for
InSPyReNet and the CarveKit models, so this CLI only adopts the models that fit
the local CPU-first `rembg[cpu]` architecture.

Source: https://github.com/MangoLion/bgbye

## Candidate Models

| Model | Intended Use | Initial Role |
| --- | --- | --- |
| `isnet-anime` | Anime/stylized character segmentation | Default first test for sprite-like subjects |
| `isnet-general-use` | General use cases | General quality baseline |
| `bria-rmbg` | BRIA background removal through rembg | High-quality candidate; check license before commercial use |
| `birefnet-general-lite` | Lightweight general background removal | Quality/speed candidate for video-derived sprites |
| `birefnet-general` | General BiRefNet background removal | Higher-quality general candidate; expect slower CPU runtime |
| `birefnet-portrait` | Portrait foregrounds | Human/portrait candidate |
| `birefnet-dis` | Dichotomous image segmentation | Detailed object-boundary candidate |
| `birefnet-hrsod` | High-resolution salient object detection | High-resolution salient-object candidate |
| `birefnet-cod` | Concealed object detection | Difficult foreground/background separation candidate |
| `birefnet-massive` | General BiRefNet trained on a larger dataset | Highest-cost BiRefNet candidate |
| `u2net` | General U2Net background removal | bgbye-overlapping baseline |
| `u2netp` | Lightweight U2Net | Fast fallback |
| `u2net_human_seg` | Human segmentation | bgbye-overlapping human fallback |
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

The larger BiRefNet models and `bria-rmbg` can be much slower and larger than
the original five-model set on CPU. Use `--models` to benchmark a smaller subset
first when download size or runtime matters.

## Results

| Model | Time | Visual Notes |
| --- | ---: | --- |
| `isnet-anime` | `0.96s` | Output generated; visual review pending |
| `isnet-general-use` | `0.97s` | Output generated; visual review pending |
| `bria-rmbg` | TBD | Pending CPU benchmark |
| `birefnet-general-lite` | `8.00s` | Output generated; visual review pending |
| `birefnet-general` | TBD | Pending CPU benchmark |
| `birefnet-portrait` | TBD | Pending CPU benchmark |
| `birefnet-dis` | TBD | Pending CPU benchmark |
| `birefnet-hrsod` | TBD | Pending CPU benchmark |
| `birefnet-cod` | TBD | Pending CPU benchmark |
| `birefnet-massive` | TBD | Pending CPU benchmark |
| `u2net` | TBD | Pending CPU benchmark |
| `u2netp` | `0.23s` | Output generated; visual review pending |
| `u2net_human_seg` | TBD | Pending CPU benchmark |
| `silueta` | `1.01s` | Output generated; visual review pending |

The first run for each model may include download time. Record steady-state timing after the model is already cached.

The completed timings above are cached steady-state inference timings on `images/susan.png` at `1448x1086`. They exclude model download time and model-session construction time. After caching the original five candidate models, `.cache/rembg-models` was about `599 MB`.

Generated benchmark files:

- `output/model-benchmark/isnet-anime.png`
- `output/model-benchmark/isnet-general-use.png`
- `output/model-benchmark/bria-rmbg.png`
- `output/model-benchmark/birefnet-general-lite.png`
- `output/model-benchmark/birefnet-general.png`
- `output/model-benchmark/birefnet-portrait.png`
- `output/model-benchmark/birefnet-dis.png`
- `output/model-benchmark/birefnet-hrsod.png`
- `output/model-benchmark/birefnet-cod.png`
- `output/model-benchmark/birefnet-massive.png`
- `output/model-benchmark/u2net.png`
- `output/model-benchmark/u2netp.png`
- `output/model-benchmark/u2net_human_seg.png`
- `output/model-benchmark/silueta.png`
- matching `.mask.png` files for each model
