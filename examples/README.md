# Notebooks

| notebook | what it shows | needs |
|---|---|---|
| [`tutorial.ipynb`](tutorial.ipynb) | the whole library, step by step: data and splits, the registry, every probe (E, U, K, S, A, E2E), a real model, the report, further analyses | the dataset download; a GPU for the model (else a simulated model) |
| [`evaluate_model.ipynb`](evaluate_model.ipynb) | `evaluate_model` in one call: general score, score of each step, robustness to the wording of the prompts, and the LLM evaluation (a deterministic judge) next to the automatic one | a GPU |
| [`quickstart.ipynb`](quickstart.ipynb) | a short tour | the dataset download |

## Running them locally

From the root of the repository:

```bash
conda env create -f environment.yml            # Python 3.11, the kit in editable mode, transformers, torch, jupyterlab
conda activate medcalc-kit
python -m ipykernel install --user --name medcalc-kit --display-name "Python (medcalc-kit)"
cd examples && jupyter lab                     # then pick the kernel "Python (medcalc-kit)"
```

To update the environment after a change of `pyproject.toml`: `conda env update -f environment.yml --prune`. The kit is
installed in editable mode, so changes to `src/` are seen after restarting the kernel.

To execute a notebook from the command line (outputs saved in the file):

```bash
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=10800 tutorial.ipynb
```

Models and the dataset are downloaded once into the Hugging Face cache (`~/.cache/huggingface`); Llama models need an
accepted licence and `huggingface-cli login`. Everything the notebooks write (generations, reports, the judge's verdicts) goes to `examples/outputs/`, which git ignores: it contains benchmark notes, which are not redistributed.
